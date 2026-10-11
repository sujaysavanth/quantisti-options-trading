from datetime import date, datetime, timezone

from app.services.schedule import Due, due


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def test_intraday_buckets_start_at_the_open():
    # 2026-10-09 is a Friday, EDT (UTC-4): the session runs 13:30-20:00 UTC.
    assert due(utc(2026, 10, 9, 13, 29)) is None
    assert due(utc(2026, 10, 9, 13, 30)) == Due("intraday", utc(2026, 10, 9, 13, 30), date(2026, 10, 9))
    assert due(utc(2026, 10, 9, 13, 44, 59)) == Due("intraday", utc(2026, 10, 9, 13, 30), date(2026, 10, 9))
    assert due(utc(2026, 10, 9, 19, 59)) == Due("intraday", utc(2026, 10, 9, 19, 45), date(2026, 10, 9))


def test_close_waits_for_the_delayed_quotes_and_ends_at_the_overnight_open():
    close = Due("close", utc(2026, 10, 9, 20, 0), date(2026, 10, 9))
    assert due(utc(2026, 10, 9, 20, 10)) is None                 # 16:10 ET: closing quotes not in yet
    assert due(utc(2026, 10, 9, 20, 20)) == close                 # 16:20 ET
    assert due(utc(2026, 10, 10, 0, 14)) == close                 # 20:14 ET
    assert due(utc(2026, 10, 10, 0, 15)) is None                  # 20:15 ET: overnight session, next day's quotes


def test_early_close_and_holidays():
    # 2026-11-27, day after Thanksgiving: closes 13:00 EST (18:00 UTC).
    assert due(utc(2026, 11, 27, 17, 59)).kind == "intraday"
    assert due(utc(2026, 11, 27, 18, 5)) is None
    assert due(utc(2026, 11, 27, 18, 20)) == Due("close", utc(2026, 11, 27, 18, 0), date(2026, 11, 27))
    assert due(utc(2026, 11, 26, 16, 0)) is None                  # Thanksgiving
    assert due(utc(2026, 10, 10, 15, 0)) is None                  # Saturday
