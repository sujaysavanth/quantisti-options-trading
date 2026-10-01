from datetime import date, datetime, timezone

import pytest

from app import market_spec as m


def test_round_to_strike_uses_five_point_grid():
    assert m.round_to_strike(6612.4) == 6610.0
    assert m.round_to_strike(6612.6) == 6615.0


def test_holidays_are_not_trading_days_or_expiries():
    thanksgiving = date(2026, 11, 26)
    assert not m.is_trading_day(thanksgiving)
    assert not m.is_expiry(thanksgiving)
    assert m.expiries_between(date(2026, 11, 23), date(2026, 11, 27)) == [
        date(2026, 11, 23), date(2026, 11, 24), date(2026, 11, 25), date(2026, 11, 27),
    ]


def test_early_close_is_1pm_eastern():
    assert m.session_close(date(2026, 11, 27)) == datetime(2026, 11, 27, 18, 0, tzinfo=timezone.utc)


def test_expiry_schedule_follows_listing_history():
    assert m.expiries_between(date(2015, 3, 2), date(2015, 3, 6)) == [date(2015, 3, 6)]
    assert m.expiries_between(date(2019, 3, 4), date(2019, 3, 8)) == [date(2019, 3, 4), date(2019, 3, 6), date(2019, 3, 8)]
    assert len(m.expiries_between(date(2026, 9, 21), date(2026, 9, 25))) == 5


def test_good_friday_expiry_moves_to_thursday():
    assert date(2019, 4, 18) in m.expiries_between(date(2019, 4, 15), date(2019, 4, 19))


def test_monthly_expiry_is_third_friday():
    monthlies = [d for d in m.expiries_between(date(2026, 10, 1), date(2026, 10, 31)) if m.is_monthly_expiry(d)]
    assert monthlies == [date(2026, 10, 16)]


@pytest.mark.parametrize(
    "on, min_dte, offset, expected",
    [
        (date(2026, 11, 25), 0, 0, date(2026, 11, 25)),  # 0DTE allowed
        (date(2026, 11, 25), 1, 0, date(2026, 11, 27)),  # skips Thanksgiving
        (date(2026, 11, 25), 0, 2, date(2026, 11, 30)),
        (date(2015, 3, 2), 0, 0, date(2015, 3, 6)),      # Fridays only in 2015
    ],
)
def test_next_expiry(on, min_dte, offset, expected):
    assert m.next_expiry(on, min_dte=min_dte, offset=offset) == expected


def test_valuation_and_year_fraction():
    friday = date(2026, 9, 25)
    vt = m.valuation_time(friday, now=datetime(2026, 9, 30, 18, tzinfo=timezone.utc))
    assert vt == m.session_close(friday)
    assert m.year_fraction(vt, date(2026, 9, 28)) == pytest.approx(3 / 365)

    # Intraday on an expiry day: time remains until the 16:00 ET close.
    morning = datetime(2026, 9, 28, 14, 0, tzinfo=timezone.utc)  # 10:00 ET
    assert m.valuation_time(date(2026, 9, 28), now=morning) == morning
    assert m.year_fraction(morning, date(2026, 9, 28)) == pytest.approx(6 / (365 * 24))
