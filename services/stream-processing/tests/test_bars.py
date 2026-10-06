import json
from datetime import datetime, timedelta

import pytest

from jobs.dlq import dlq_frame
from jobs.schemas import BAR_PAYLOAD
from jobs.transforms import five_minute_bars, latest_bars, parse_envelopes, validate_bars

OPEN = datetime(2026, 10, 5, 13, 30)    # 09:30 ET, as UTC


def bar(minute=0, symbol="SPX", o=100.0, h=101.0, l=99.0, c=100.5, v=10, interval="1m",
        produced_at="2026-10-06T05:06:59.695072Z"):
    ts = (OPEN + timedelta(minutes=minute)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"schema": "bars.v1", "source": "yahoo", "delay_minutes": 15, "produced_at": produced_at,
            "payload": {"symbol": symbol, "interval": interval, "ts": ts,
                        "open": o, "high": h, "low": l, "close": c, "volume": v}}


def validated(kafka_df, *messages):
    valid, unparsed = parse_envelopes(kafka_df(*messages), BAR_PAYLOAD, "bars.v1")
    good, bad = validate_bars(valid)
    return good, bad, unparsed


@pytest.mark.parametrize("message,reason", [
    (bar(symbol="NDX"), "unknown symbol"),
    (bar(interval="2m"), "unknown interval"),
    (bar(o=None), "missing price"),
    (bar(l=-1.0), "non-positive price"),
    (bar(h=1.0, l=5.0, o=3.0, c=3.0), "high < low"),
    (bar(o=102.0), "open/close outside high-low"),
    (bar(v=-3), "negative volume"),
])
def test_each_rule_has_a_reason(kafka_df, message, reason):
    good, bad, _ = validated(kafka_df, bar(), message)
    assert good.count() == 1
    assert [r.reason for r in bad.collect()] == [reason]
    assert json.loads(bad.first().json)["payload"]["symbol"] == message["payload"]["symbol"]   # original kept


def test_duplicates_in_a_batch_collapse(kafka_df):
    good, _, _ = validated(kafka_df, bar(0), bar(0, produced_at="2026-10-06T06:00:00Z", c=100.7), bar(1))
    rows = sorted(latest_bars(good).collect(), key=lambda r: r.ts)
    assert [(r.ts, r.close) for r in rows] == [(OPEN, 100.7), (OPEN + timedelta(minutes=1), 100.5)]


def test_five_minute_window(kafka_df):
    minutes = [bar(m, o=100 + m, h=110 + m, l=90 - m, c=101 + m, v=10) for m in range(6)]   # 09:30..09:35
    good, _, _ = validated(kafka_df, *minutes)
    windows = sorted(five_minute_bars(good).collect(), key=lambda r: r.ts)
    first, second = windows
    assert first.ts == OPEN and first.bars == 5
    assert (first.open, first.high, first.low, first.close, first.volume) == (100.0, 114.0, 86.0, 105.0, 50)
    assert second.ts == OPEN + timedelta(minutes=5) and second.bars == 1      # 09:35 starts a new window


def test_windows_are_per_symbol(kafka_df):
    good, _, _ = validated(kafka_df, bar(0), bar(1), bar(0, symbol="VIX", o=16, h=16.5, l=15.8, c=16.2))
    counts = {r.symbol: r.bars for r in five_minute_bars(good).collect()}
    assert counts == {"SPX": 2, "VIX": 1}


def test_dlq_message_shape(kafka_df):
    _, bad, unparsed = validated(kafka_df, bar(h=1.0, l=5.0, o=3.0, c=3.0), "not json")
    rows = dlq_frame(unparsed.unionByName(bad), "bars_1m", "market.bars.1m").collect()
    assert {r.key for r in rows} == {"market.bars.1m"}
    messages = {json.loads(r.value)["reason"]: json.loads(r.value) for r in rows}
    assert set(messages) == {"high < low", "unparseable message"}
    assert messages["unparseable message"]["value"] == "not json"
    assert messages["high < low"]["job"] == "bars_1m" and messages["high < low"]["failed_at"].endswith("Z")
