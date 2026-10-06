from datetime import date, datetime, timezone

import pytest

from app.sources.session import session_for


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


@pytest.mark.parametrize("quoted_at, expected, why", [
    (utc(2026, 10, 1, 5, 45), date(2026, 10, 1), "01:45 ET Thu: overnight GTH belongs to Thursday (the Module 2 bug)"),
    (utc(2026, 10, 2, 14, 0), date(2026, 10, 2), "10:00 ET Fri: regular hours"),
    (utc(2026, 10, 2, 20, 5), date(2026, 10, 2), "16:05 ET Fri: end-of-day capture"),
    (utc(2026, 10, 3, 1, 0), date(2026, 10, 2), "21:00 ET Fri: no Saturday session, still Friday's quotes"),
    (utc(2026, 10, 3, 16, 0), date(2026, 10, 2), "Saturday: last session was Friday"),
    (utc(2026, 10, 4, 23, 0), date(2026, 10, 2), "19:00 ET Sun: Monday's GTH hasn't opened yet"),
    (utc(2026, 10, 5, 1, 30), date(2026, 10, 5), "21:30 ET Sun: Monday's GTH is open"),
    (utc(2026, 11, 26, 15, 0), date(2026, 11, 25), "Thanksgiving: last session was Wednesday"),
    (utc(2026, 11, 27, 2, 0), date(2026, 11, 27), "21:00 ET Thanksgiving: Friday's GTH is open"),
])
def test_session_for(quoted_at, expected, why):
    assert session_for(quoted_at) == expected, why


def test_naive_datetime_rejected():
    with pytest.raises(ValueError):
        session_for(datetime(2026, 10, 2, 14, 0))
