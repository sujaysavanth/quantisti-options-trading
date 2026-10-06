from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.producers.schedule import eod_due, is_market_open, latest_session

ET = ZoneInfo("America/New_York")


def et(*args):
    return datetime(*args, tzinfo=ET)


def test_market_hours():
    assert is_market_open(et(2026, 10, 6, 10, 0))            # Tuesday morning
    assert is_market_open(et(2026, 10, 6, 9, 30))            # the open itself
    assert not is_market_open(et(2026, 10, 6, 9, 29))
    assert not is_market_open(et(2026, 10, 6, 16, 0))       # the close itself
    assert not is_market_open(et(2026, 10, 3, 11, 0))       # Saturday
    assert not is_market_open(et(2026, 11, 27, 13, 30))     # day after Thanksgiving closes at 13:00
    assert is_market_open(et(2026, 11, 27, 12, 59))


def test_end_of_day_runs_once_between_close_and_overnight_session():
    assert eod_due(et(2026, 10, 6, 16, 5), None) is None           # closing quotes not out yet (15 min delay)
    assert eod_due(et(2026, 10, 6, 16, 25), None) == date(2026, 10, 6)
    assert eod_due(et(2026, 10, 6, 16, 25), date(2026, 10, 6)) is None   # already done
    assert eod_due(et(2026, 10, 6, 20, 30), None) is None          # overnight quotes belong to tomorrow
    assert eod_due(et(2026, 11, 27, 13, 25), None) == date(2026, 11, 27)  # early close
    assert eod_due(et(2026, 10, 3, 17, 0), None) is None           # Saturday


def test_latest_session_steps_back_over_weekends():
    assert latest_session(et(2026, 10, 4, 12, 0)) == date(2026, 10, 2)   # Sunday -> Friday
    assert latest_session(et(2026, 10, 6, 8, 0)) == date(2026, 10, 5)    # Tuesday before the open -> Monday
    assert latest_session(et(2026, 10, 6, 9, 30)) == date(2026, 10, 6)
