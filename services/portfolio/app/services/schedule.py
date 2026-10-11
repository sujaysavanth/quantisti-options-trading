"""When the portfolio is snapshotted, from the NYSE calendar in market_spec.

- intraday: every 15 minutes while the regular session is open (09:30 ET to the close, 13:00 on early closes),
  stamped at the start of the 15-minute bucket.
- close: once per session, stamped at the close, taken between CLOSE_DELAY after the close and 20:15 ET. Quotes are
  ~15 minutes delayed, so the closing marks only arrive around 16:15; after 20:15 CBOE's overnight session starts
  and quotes belong to the next day (same window as ingest's end-of-day run). A close missed in that window stays
  missing rather than being taken at the wrong prices.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from .. import market_spec

REGULAR_OPEN = time(9, 30)
OVERNIGHT_OPEN = time(20, 15)
INTRADAY_EVERY = timedelta(minutes=15)
CLOSE_DELAY = timedelta(minutes=20)


@dataclass(frozen=True)
class Due:
    kind: str                # intraday | close
    taken_at: datetime       # bucket start or session close (aware, UTC)
    session: date


def _at(day: date, t: time) -> datetime:
    return datetime.combine(day, t, market_spec.TZ).astimezone(timezone.utc)


def due(now: datetime) -> Optional[Due]:
    """The snapshot that belongs to `now`, or None outside both windows."""
    day = now.astimezone(market_spec.TZ).date()
    if not market_spec.is_trading_day(day):
        return None
    opens, closes = _at(day, REGULAR_OPEN), market_spec.session_close(day)
    if opens <= now < closes:
        return Due("intraday", opens + (now - opens) // INTRADAY_EVERY * INTRADAY_EVERY, day)
    if closes + CLOSE_DELAY <= now < _at(day, OVERNIGHT_OPEN):
        return Due("close", closes, day)
    return None
