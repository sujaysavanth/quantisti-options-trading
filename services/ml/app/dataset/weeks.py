"""Weekly anchors on the NYSE calendar.

An anchor is the last session of a calendar week: Friday, or Thursday when Friday is a holiday
(Good Friday, some July 4ths). It is also the week's SPX expiry, so "next week's close" and
"next week's expiry settlement" are the same price.

Each row of the dataset sits on an anchor: features use data up to and including the anchor's
close; the label is the close at the next anchor.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, List, Optional

from .. import market_spec


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def anchor_of_week(day: date) -> Optional[date]:
    """Last NYSE session of the calendar week containing `day` (None for a week with no sessions)."""
    monday = monday_of(day)
    sessions = market_spec.trading_days(monday, monday + timedelta(days=6))
    return sessions[-1] if sessions else None


def sessions_in_week(day: date) -> int:
    monday = monday_of(day)
    return len(market_spec.trading_days(monday, monday + timedelta(days=6)))


def sessions_next_week(anchor: date) -> int:
    """Sessions in the week after `anchor`'s week: known in advance from the calendar (4 in holiday weeks)."""
    return sessions_in_week(monday_of(anchor) + timedelta(days=7))


def complete_anchors(stored: Iterable[date]) -> List[date]:
    """Anchors of the weeks whose last session has a stored close, oldest first.

    A week still in progress (its last session not closed yet) has no anchor, and a week whose last
    session is missing from the data is skipped rather than anchored on an earlier day.
    """
    days = set(stored)
    anchors = {anchor_of_week(monday) for monday in {monday_of(d) for d in days}}   # one calendar lookup per week
    return sorted(a for a in anchors if a is not None and a in days)
