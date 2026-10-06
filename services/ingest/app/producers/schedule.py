"""When the pollers should run, from the NYSE calendar in market_spec.

- Intraday bars and chains are polled while the regular session is open
  (09:30 ET to the close, 13:00 on early-close days).
- The end-of-day run (final bars, closing chain, daily rows) happens once per
  session, starting EOD_DELAY after the close: quotes are ~15 minutes delayed,
  so the closing chain only shows up around 16:15 ET. It must finish before
  the overnight session opens at 20:15 ET, after which CBOE quotes belong to
  the next day.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from .. import market_spec
from ..sources.session import GTH_OPEN

REGULAR_OPEN = time(9, 30)
EOD_DELAY = timedelta(minutes=20)


def session_open(day: date) -> datetime:
    return datetime.combine(day, REGULAR_OPEN, market_spec.TZ).astimezone(timezone.utc)


def latest_session(now: datetime) -> date:
    """The most recent session that has opened: today after 09:30 ET on a trading day, else an earlier one."""
    today = now.astimezone(market_spec.TZ).date()
    sessions = market_spec.trading_days(today - timedelta(days=10), today)
    return sessions[-1] if session_open(sessions[-1]) <= now else sessions[-2]


def is_market_open(now: datetime) -> bool:
    day = now.astimezone(market_spec.TZ).date()
    return market_spec.is_trading_day(day) and session_open(day) <= now < market_spec.session_close(day)


def eod_due(now: datetime, last_done: Optional[date]) -> Optional[date]:
    """The session whose end-of-day run is due now, or None."""
    day = now.astimezone(market_spec.TZ).date()
    if not market_spec.is_trading_day(day) or last_done == day:
        return None
    starts = market_spec.session_close(day) + EOD_DELAY
    ends = datetime.combine(day, GTH_OPEN, market_spec.TZ).astimezone(timezone.utc)
    return day if starts <= now < ends else None
