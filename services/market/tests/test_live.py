from datetime import date, datetime, timezone

from app.services.live import default_session, pick_spot, snapshot_as_of

DAY = date(2026, 10, 6)
CLOSE = datetime(2026, 10, 6, 20, 0, tzinfo=timezone.utc)                     # 16:00 ET


def test_daily_close_wins_when_stored():
    bar = {"ts": datetime(2026, 10, 6, 19, 59, tzinfo=timezone.utc), "interval": "1m", "close": 6701.3}
    spot = pick_spot(DAY, 6702.0, bar)
    assert (spot.price, spot.at, spot.source) == (6702.0, CLOSE, "close")


def test_session_in_progress_uses_the_last_bar():
    bar = {"ts": datetime(2026, 10, 6, 15, 42, tzinfo=timezone.utc), "interval": "1m", "close": 6688.25}
    spot = pick_spot(DAY, None, bar)
    assert (spot.price, spot.source) == (6688.25, "intraday")
    assert spot.at == datetime(2026, 10, 6, 15, 43, tzinfo=timezone.utc)      # end of the bar


def test_five_minute_bar_end_and_nothing_at_all():
    bar = {"ts": datetime(2026, 10, 6, 19, 55, tzinfo=timezone.utc), "interval": "5m", "close": 6700.0}
    assert pick_spot(DAY, None, bar).at == CLOSE
    assert pick_spot(DAY, None, None) is None


def test_default_session_is_the_latest_of_either_source():
    assert default_session(date(2026, 10, 5), date(2026, 10, 6)) == date(2026, 10, 6)   # market open, no close yet
    assert default_session(date(2026, 10, 6), date(2026, 10, 6)) == date(2026, 10, 6)
    assert default_session(date(2026, 10, 6), None) == date(2026, 10, 6)               # no intraday data
    assert default_session(None, None) is None


def test_snapshot_priced_at_its_quote_time():
    now = datetime(2026, 10, 6, 18, 0, tzinfo=timezone.utc)                  # 14:00 ET
    quoted = datetime(2026, 10, 6, 17, 45, tzinfo=timezone.utc)               # CBOE, 15 min delayed
    assert snapshot_as_of(now, quoted) == quoted
    assert snapshot_as_of(CLOSE, datetime(2026, 10, 6, 20, 14, 59, tzinfo=timezone.utc)) == CLOSE   # post-close capture
    assert snapshot_as_of(now, None) == now
