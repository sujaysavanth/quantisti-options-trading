"""What a complete session looks like: which sessions can be checked yet, and how many bars each should have."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import List

from .. import market_spec
from ..producers.schedule import session_open
from ..sources import yahoo

BAR_MINUTES = {"1m": 1, "5m": 5, "1h": 60}

# A session counts as complete at 98% of its bars (rounded down). Yahoo routinely leaves out a bar or so:
# VIX 1m has 389 of 390, some 5m days 77 of 78, and on early closes SPX 1h drops the half-hour 12:30 bar (3 of 4).
COMPLETE = 0.98

# Data for a session arrives after its close: the end-of-day run starts 20 min later and Spark writes
# ~30s after that. Sessions are only checked once this much time has passed.
GRACE = timedelta(minutes=45)


def session_minutes(day: date) -> int:
    """390 on a normal day, 210 on a 13:00 early close."""
    return int((market_spec.session_close(day) - session_open(day)).total_seconds() // 60)


def expected_bars(day: date, interval: str) -> int:
    return math.ceil(session_minutes(day) / BAR_MINUTES[interval])


def min_bars(day: date, interval: str) -> int:
    """Fewest bars that still count as a complete session."""
    return math.floor(expected_bars(day, interval) * COMPLETE)


def in_source_window(day: date, interval: str, now: datetime) -> bool:
    """Whether Yahoo still serves `interval` bars for the whole session (an hour of margin inside its window)."""
    window, _ = yahoo.LIMITS[interval]
    return session_open(day) >= now - window + timedelta(hours=2)


def closed_sessions(start: date, now: datetime) -> List[date]:
    """Sessions from `start` whose close (plus GRACE) has passed by `now`."""
    today = now.astimezone(market_spec.TZ).date()
    return [d for d in market_spec.trading_days(start, today) if market_spec.session_close(d) + GRACE <= now]
