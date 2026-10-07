"""Rules for pricing the session that is still in progress.

Daily rows arrive after the close (~16:20 ET), but intraday bars and option snapshots
stream in all day. These pure functions decide which one a chain uses:

- spot for a day: its daily close when stored, else the last intraday bar of that day.
  Past days always have a close, so backtests are unaffected.
- default day: the latest session from either source (today, once bars have arrived).
- valuation time for snapshot quotes: never later than the quotes themselves. CBOE's
  are ~15 min old; pricing them at "now" would understate time left on a 0DTE.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from .. import market_spec

BAR_LENGTH = {"1m": timedelta(minutes=1), "5m": timedelta(minutes=5), "1h": timedelta(hours=1)}


@dataclass(frozen=True)
class Spot:
    price: float
    at: datetime          # when this price was current (UTC)
    source: str           # 'close' | 'intraday'


def pick_spot(day: date, daily_close: Optional[float], last_bar: Optional[dict]) -> Optional[Spot]:
    """`last_bar` is an intraday_bars row (ts, interval, close) from `day`, or None."""
    if daily_close is not None:
        return Spot(daily_close, market_spec.session_close(day), "close")
    if last_bar is not None:
        return Spot(float(last_bar["close"]), last_bar["ts"] + BAR_LENGTH[last_bar["interval"]], "intraday")
    return None


def default_session(latest_daily: Optional[date], latest_intraday: Optional[date]) -> Optional[date]:
    days = [d for d in (latest_daily, latest_intraday) if d is not None]
    return max(days) if days else None


def snapshot_as_of(valuation: datetime, quoted_at: Optional[datetime]) -> datetime:
    """Price quotes at the time they were taken, unless that's after the valuation time (e.g. a post-close capture)."""
    return min(valuation, quoted_at) if quoted_at is not None else valuation
