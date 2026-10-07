from datetime import datetime, timedelta, timezone

from app.backfill.intraday import Range, backfill, backfill_range, plan_ranges
from app.producers.kafka import Publisher
from app.sources.yahoo import Bar
from tests.fakes import FakeProducer

NOW = datetime(2026, 10, 6, 21, 0, tzinfo=timezone.utc)


class YFRateLimitError(Exception):
    """Same class name as yfinance's, which is what is_rate_limited looks for."""


def test_max_plan_covers_each_yahoo_window():
    ranges = plan_ranges(NOW)
    assert {(r.symbol, r.interval) for r in ranges} == {(s, i) for s in ("SPX", "VIX") for i in ("1m", "5m", "1h")}
    span = {r.interval: NOW - r.start for r in ranges}
    assert timedelta(days=29) < span["1m"] < timedelta(days=30)
    assert timedelta(days=59) < span["5m"] < timedelta(days=60)
    assert timedelta(days=729) < span["1h"] < timedelta(days=730)
    assert all(r.end == NOW for r in ranges)
    assert [r.interval for r in ranges][:2] == ["1h", "1h"]          # longest history first


def test_days_caps_but_never_exceeds_the_window():
    ranges = {r.interval: r for r in plan_ranges(NOW, days=10, symbols=["SPX"])}
    assert ranges["1h"].start == NOW - timedelta(days=10)
    assert NOW - ranges["1m"].start == timedelta(days=10)
    assert {r.interval for r in plan_ranges(NOW, intervals=["5m"], days=365)} == {"5m"}
    assert NOW - plan_ranges(NOW, intervals=["5m"], days=365)[0].start < timedelta(days=60)


def bars(symbol, interval, n):
    start = datetime(2026, 10, 5, 13, 30, tzinfo=timezone.utc)
    step = {"1m": 1, "5m": 5, "1h": 60}[interval]
    return [Bar(symbol, interval, start + timedelta(minutes=step * i), 100.0, 101.0, 99.0, 100.5, 7) for i in range(n)]


def test_bars_published_with_their_interval_and_no_delay():
    fake = FakeProducer()
    rng = Range("VIX", "1h", NOW - timedelta(days=30), NOW)
    res = backfill_range(Publisher("x", producer=fake), rng, fetch=lambda s, i, a, b, download: bars(s, i, 3),
                         download=object(), sleep=lambda s: None)
    assert (res.bars, res.error) == (3, None)
    assert {(t, k) for t, k, _ in fake.sent} == {("market.bars.1m", "VIX")}
    env = fake.sent[0][2]
    assert (env["schema"], env["delay_minutes"], env["payload"]["interval"]) == ("bars.v1", 0, "1h")


def test_rate_limit_is_retried_with_backoff():
    calls, waits = [], []

    def fetch(symbol, interval, start, end, download):
        calls.append(1)
        if len(calls) < 3:
            raise YFRateLimitError("Too Many Requests")
        return bars(symbol, interval, 2)

    res = backfill_range(Publisher("x", producer=FakeProducer()), Range("SPX", "1m", NOW, NOW), fetch=fetch,
                         download=object(), sleep=waits.append, retry_waits=(30, 60, 120))
    assert res.bars == 2 and waits == [30, 60]


def test_failures_are_reported_and_the_rest_continue():
    def fetch(symbol, interval, start, end, download):
        if interval == "1m":
            raise ValueError("1m bars before 2026-09-07 are no longer available from Yahoo")
        return bars(symbol, interval, 1)

    results = backfill(Publisher("x", producer=FakeProducer()), plan_ranges(NOW, symbols=["SPX"]),
                       fetch=fetch, download=object(), sleep=lambda s: None)
    assert [(r.range.interval, r.bars, bool(r.error)) for r in results] == [("1h", 1, False), ("5m", 1, False), ("1m", 0, True)]


def test_rate_limit_that_never_clears_is_reported():
    def fetch(*args, **kwargs):
        raise YFRateLimitError("Too Many Requests")

    res = backfill_range(Publisher("x", producer=FakeProducer()), Range("SPX", "1m", NOW, NOW), fetch=fetch,
                         download=object(), sleep=lambda s: None, retry_waits=(1, 1))
    assert res.bars == 0 and res.error.startswith("YFRateLimitError")
