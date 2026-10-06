from datetime import datetime, timedelta, timezone

from app.producers.intraday import IntradayPoller
from app.producers.kafka import Publisher
from app.sources.yahoo import Bar
from tests.fakes import FakeProducer

OPEN = datetime(2026, 10, 6, 13, 30, tzinfo=timezone.utc)   # 09:30 ET


def bars(symbol, minutes):
    return [Bar(symbol, "1m", OPEN + timedelta(minutes=m), 100.0, 101.0, 99.0, 100.5, 10) for m in minutes]


def fake_fetch(calls):
    def fetch(symbol, interval, start, end):
        calls.append((symbol, start))
        # Yahoo returns everything from start to now, including the minute still forming.
        last = int((end - OPEN).total_seconds() // 60)
        first = max(0, int((start - OPEN).total_seconds() // 60))
        return bars(symbol, range(first, last + 1))
    return fetch


def test_only_new_finished_bars_are_sent():
    fake, calls = FakeProducer(), []
    poller = IntradayPoller(Publisher("unused", producer=fake), fetch=fake_fetch(calls))

    poller.poll_once(now=OPEN + timedelta(minutes=3, seconds=20))   # minutes 0,1,2 done; 3 still forming
    assert [(k, v["payload"]["ts"]) for _, k, v in fake.sent if k == "SPX"] == [
        ("SPX", "2026-10-06T13:30:00Z"), ("SPX", "2026-10-06T13:31:00Z"), ("SPX", "2026-10-06T13:32:00Z")]
    assert calls[0] == ("SPX", OPEN)                                 # first poll starts at the session open

    fake.sent.clear()
    poller.poll_once(now=OPEN + timedelta(minutes=5, seconds=5))    # overlapping fetch
    assert [v["payload"]["ts"] for _, k, v in fake.sent if k == "SPX"] == ["2026-10-06T13:33:00Z", "2026-10-06T13:34:00Z"]


def test_messages_are_keyed_by_symbol_and_wrapped():
    fake = FakeProducer()
    IntradayPoller(Publisher("unused", producer=fake), fetch=fake_fetch([])).poll_once(now=OPEN + timedelta(minutes=2))
    topics_keys = {(t, k) for t, k, _ in fake.sent}
    assert topics_keys == {("market.bars.1m", "SPX"), ("market.bars.1m", "VIX")}
    env = fake.sent[0][2]
    assert (env["schema"], env["source"], env["delay_minutes"], env["payload"]["interval"]) == ("bars.v1", "yahoo", 15, "1m")
