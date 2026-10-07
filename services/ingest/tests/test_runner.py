from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import Settings
from app.producers.kafka import Publisher
from app.producers.runner import Runner
from tests.fakes import FakeProducer

ET = ZoneInfo("America/New_York")


class Poller:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def poll_once(self, now, force=False):
        self.calls.append((now, force))
        if self.fail:
            raise RuntimeError("source down")
        return 1


def runner(fail_chain=False):
    r = Runner(Settings(), Publisher("unused", producer=FakeProducer()),
               intraday=Poller(), chain=Poller(fail=fail_chain), daily=Poller())
    return r


def test_polls_on_their_intervals_during_market_hours():
    r = runner()
    start = datetime(2026, 10, 6, 10, 0, tzinfo=ET)
    for s in range(0, 181, 5):                                  # three minutes of ticks
        r.tick(start + timedelta(seconds=s))
    assert len(r.intraday.calls) == 4                           # 0, 60, 120, 180 s
    assert len(r.chain.calls) == 3                              # 0, 90, 180 s
    assert r.daily.calls == []


def test_end_of_day_runs_once_with_forced_chain():
    r = runner()
    for minute in (25, 26, 40):
        r.tick(datetime(2026, 10, 6, 16, minute, tzinfo=ET))
    assert len(r.daily.calls) == 1 and r.chain.calls[0][1] is True
    assert r.eod_done == date(2026, 10, 6)


def test_nothing_runs_on_a_weekend():
    r = runner()
    r.tick(datetime(2026, 10, 3, 12, 0, tzinfo=ET))
    assert r.intraday.calls == r.chain.calls == r.daily.calls == []


def test_a_failing_poller_is_recorded_not_fatal():
    r = runner(fail_chain=True)
    r.tick(datetime(2026, 10, 6, 10, 0, tzinfo=ET))
    assert r.status["chain"]["error"] == "source down"
    assert r.status["intraday"]["sent"] == 1
