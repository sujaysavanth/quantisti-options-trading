from datetime import date, datetime, timedelta, timezone

import httpx
import pytest

from app.producers.chain import ChainPoller
from app.producers.kafka import Publisher
from app.sources.base import ChainQuote, ChainSnapshot
from tests.fakes import FakeProducer

NOW = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
EXPIRIES = [date(2026, 10, 6), date(2026, 10, 7), date(2026, 10, 9)]


def snapshot():
    quotes = [ChainQuote(e, t, k, 10.0, 10.5, 10.2, 3, 100) for e in EXPIRIES for k in (6700.0, 6705.0) for t in "CP"]
    return ChainSnapshot("SPX", "cboe", 15, NOW - timedelta(minutes=15), date(2026, 10, 6), 6702.0, quotes)


class Source:
    name, delay_minutes = "cboe", 15

    def __init__(self, results):
        self.results = list(results)

    def fetch_chain(self, expiries, moneyness):
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def too_many_requests():
    request = httpx.Request("GET", "https://cdn-api.cboe.com/x")
    return httpx.HTTPStatusError("429", request=request, response=httpx.Response(429, request=request))


def test_one_message_per_expiry_keyed_by_expiry():
    fake = FakeProducer()
    sent = ChainPoller(Publisher("unused", producer=fake), Source([snapshot()]), 5, 0.05).poll_once(now=NOW)
    assert sent == 3
    assert [k for _, k, _ in fake.sent] == ["SPX:2026-10-06", "SPX:2026-10-07", "SPX:2026-10-09"]
    env = fake.sent[0][2]
    assert (env["schema"], env["source"], env["delay_minutes"]) == ("chain.v1", "cboe", 15)
    assert env["payload"]["underlying_price"] == 6702.0 and len(env["payload"]["quotes"]) == 4
    assert {q["option_type"] for q in env["payload"]["quotes"]} == {"C", "P"}


def test_429_backs_off_and_doubles():
    source = Source([too_many_requests(), too_many_requests(), snapshot()])
    poller = ChainPoller(Publisher("unused", producer=FakeProducer()), source, 5, 0.05)

    assert poller.poll_once(now=NOW) == 0 and poller.backoff == timedelta(seconds=90)
    assert poller.poll_once(now=NOW + timedelta(seconds=60)) == 0          # still paused: source not called
    assert len(source.results) == 2
    assert poller.poll_once(now=NOW + timedelta(seconds=91)) == 0 and poller.backoff == timedelta(seconds=180)
    assert poller.poll_once(now=NOW + timedelta(seconds=91 + 181)) == 3 and poller.backoff is None


def test_other_errors_are_raised():
    poller = ChainPoller(Publisher("unused", producer=FakeProducer()), Source([RuntimeError("bad json")]), 5, 0.05)
    with pytest.raises(RuntimeError):
        poller.poll_once(now=NOW)
