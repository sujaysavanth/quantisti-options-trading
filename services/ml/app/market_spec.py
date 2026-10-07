"""Contract and calendar rules for the traded underlying (S&P 500 index options, SPX).

Copy of services/market/app/market_spec.py (each service builds its own
image, so they cannot share a module). Keep the code identical; the test
services/ingest/tests/test_market_spec_copy.py fails if the copies drift.
The ml service uses it for week anchors and session counts.

Simplifications, stated so they are easy to revisit:
- Every expiry is treated as PM-settled at the 16:00 ET close (SPXW style),
  including the AM-settled third-Friday monthlies.
- Strikes are generated on a uniform 5-point grid; the real grid widens to
  25/50 points far from the money.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from typing import List
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd

SYMBOL = "SPX"
YAHOO_TICKER = "^GSPC"          # daily index history
YAHOO_OPTIONS_TICKER = "^SPX"   # listed option chains
CURRENCY = "USD"

STRIKE_STEP = 5
MULTIPLIER = 100
DIVIDEND_YIELD = 0.013          # trailing S&P 500 dividend yield, approx.
FALLBACK_RATE = 0.04            # used only when no FRED rate is stored for a date

TZ = ZoneInfo("America/New_York")
REGULAR_CLOSE = time(16, 0)
SECONDS_PER_YEAR = 365 * 24 * 60 * 60

# Weekdays with listed SPX expiries, by the date each was introduced (Mon=0 … Fri=4).
_EXPIRY_WEEKDAYS_SINCE = [
    (date(1900, 1, 1), {4}),            # Friday weeklies
    (date(2016, 8, 15), {0, 2, 4}),     # + Monday (Aug 2016) and Wednesday (Feb 2016)
    (date(2022, 5, 11), {0, 1, 2, 3, 4}),  # + Tuesday (Apr 2022) and Thursday (May 2022): daily
]


@lru_cache(maxsize=1)
def _calendar() -> xcals.ExchangeCalendar:
    return xcals.get_calendar("XNYS", start="1990-01-01")


def _expiry_weekdays(on: date) -> set[int]:
    weekdays: set[int] = set()
    for since, days in _EXPIRY_WEEKDAYS_SINCE:
        if on >= since:
            weekdays = days
    return weekdays


def round_to_strike(price: float, step: int = STRIKE_STEP) -> float:
    """Nearest listed strike to `price`."""
    return float(round(price / step) * step)


def is_trading_day(on: date) -> bool:
    return _calendar().is_session(pd.Timestamp(on))


def trading_days(start: date, end: date) -> List[date]:
    """NYSE sessions between `start` and `end`, inclusive."""
    if end < start:
        return []
    sessions = _calendar().sessions_in_range(pd.Timestamp(start), pd.Timestamp(end))
    return [s.date() for s in sessions]


def session_close(on: date) -> datetime:
    """Closing time of the session on `on` (handles 13:00 early closes), as an aware UTC datetime."""
    return _calendar().session_close(pd.Timestamp(on)).to_pydatetime()


def is_monthly_expiry(on: date) -> bool:
    """Third Friday of the month, or the Thursday before it when that Friday is a holiday."""
    third_friday = _third_friday(on.year, on.month)
    if is_trading_day(third_friday):
        return on == third_friday
    return on == third_friday - timedelta(days=1)


def _third_friday(year: int, month: int) -> date:
    first = date(year, month, 1)
    first_friday = first + timedelta(days=(4 - first.weekday()) % 7)
    return first_friday + timedelta(weeks=2)


def is_expiry(on: date) -> bool:
    """Whether SPX options were listed to expire on `on`."""
    if not is_trading_day(on):
        return False
    if on.weekday() in _expiry_weekdays(on):
        return True
    # A Friday expiry falling on a holiday (e.g. Good Friday) moves to Thursday.
    friday = on + timedelta(days=1)
    return on.weekday() == 3 and 4 in _expiry_weekdays(friday) and not is_trading_day(friday)


def expiries_between(start: date, end: date) -> List[date]:
    """Listed expiries in [start, end]."""
    return [d for d in trading_days(start, end) if is_expiry(d)]


def next_expiry(on: date, min_dte: int = 0, offset: int = 0) -> date:
    """First listed expiry at least `min_dte` calendar days after `on`, then `offset` expiries later.

    `min_dte=0` allows a same-day (0DTE) expiry when `on` is itself an expiry.
    """
    start = on + timedelta(days=min_dte)
    # Expiries are at most a week apart, so a window of a few weeks per step is ample.
    candidates = expiries_between(start, start + timedelta(days=21 + 7 * offset))
    if len(candidates) <= offset:
        raise ValueError(f"No listed expiry found after {start} with offset {offset}")
    return candidates[offset]


def valuation_time(on: date, now: datetime | None = None) -> datetime:
    """Moment an option chain for `on` is priced at.

    Historical dates are valued at their close (matching the daily close we
    store); today is valued at the current time while the market is open.
    """
    close = session_close(on) if is_trading_day(on) else datetime.combine(on, REGULAR_CLOSE, TZ).astimezone(timezone.utc)
    now = now or datetime.now(timezone.utc)
    if now.astimezone(TZ).date() == on and now < close:
        return now
    return close


def year_fraction(as_of: datetime, expiry: date) -> float:
    """Time from `as_of` to the expiry close, in years (calendar-time, 365-day basis)."""
    seconds = (session_close(expiry) - as_of).total_seconds()
    return max(seconds, 0.0) / SECONDS_PER_YEAR
