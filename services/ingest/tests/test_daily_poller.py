from datetime import date, datetime, timezone

import pandas as pd

from app.producers.daily import DailyPoller
from app.producers.kafka import Publisher
from app.sources.cboe import DailyClose
from app.sources.fred import DailyRate
from app.sources.yahoo import DailyBar, fetch_daily
from tests.fakes import FakeProducer


def spx(symbol, start, end):
    return [DailyBar(date(2026, 10, 5), 6690.0, 6720.0, 6680.0, 6710.0, 2_500_000_000),
            DailyBar(date(2026, 10, 6), 6710.0, 6715.0, 6700.0, 6705.0, 900_000_000)]


def vix(start, end):
    return [DailyClose(date(2026, 10, 5), 16.4)]


def rates(start, end):
    return [DailyRate(date(2026, 10, 2), 0.0412)]


def run(now):
    fake = FakeProducer()
    DailyPoller(Publisher("unused", producer=fake), spx, vix, rates).poll_once(now=now)
    return fake.sent


def test_three_datasets_with_keys_and_sources():
    sent = run(datetime(2026, 10, 6, 21, 0, tzinfo=timezone.utc))      # 17:00 ET, after the close
    assert [(k, v["source"], v["payload"]["date"]) for _, k, v in sent] == [
        ("underlying:SPX", "yahoo", "2026-10-05"), ("underlying:SPX", "yahoo", "2026-10-06"),
        ("vix:VIX", "cboe", "2026-10-05"), ("rates:DGS3MO", "fred", "2026-10-02")]
    assert all(t == "market.daily" and v["schema"] == "daily.v1" and v["delay_minutes"] == 0 for t, _, v in sent)
    assert sent[3][2]["payload"]["rate"] == 0.0412


def test_todays_bar_is_held_back_until_the_close():
    sent = run(datetime(2026, 10, 6, 18, 0, tzinfo=timezone.utc))      # 14:00 ET
    assert [v["payload"]["date"] for _, k, v in sent if k == "underlying:SPX"] == ["2026-10-05"]


def test_fetch_daily_parses_yahoo_frame():
    idx = pd.DatetimeIndex(["2026-10-02", "2026-10-05"])
    cols = pd.MultiIndex.from_product([["Open", "High", "Low", "Close", "Volume"], ["^GSPC"]])
    df = pd.DataFrame([[1.0, 2.0, 0.5, 1.5, 10], [1.5, 2.5, 1.0, 2.0, None]], index=idx, columns=cols)
    calls = []
    bars = fetch_daily("SPX", date(2026, 10, 3), date(2026, 10, 5), download=lambda **kw: calls.append(kw) or df)
    assert bars == [DailyBar(date(2026, 10, 5), 1.5, 2.5, 1.0, 2.0, 0)]     # 10-02 is before start
    assert calls[0]["tickers"] == "^GSPC" and calls[0]["end"] == date(2026, 10, 6)   # Yahoo's end is exclusive
