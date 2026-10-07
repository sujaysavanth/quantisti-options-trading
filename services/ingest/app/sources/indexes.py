"""Daily index series used as forecast features, stored in `index_daily` (one row per symbol and date).

One list, shared by the end-of-day poller, the history backfill, the gap detector and the backfill worker.

`gap_rule` says how the gap detector treats missing days:
- "session": a value per NYSE session, except the latest (CBOE's history files can lag a day), like VIX.
- "runs":    only runs of more than 3 missing sessions count, like the T-bill rate: FRED posts late and
             the bond market closes on some NYSE sessions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable, List, Optional

from . import cboe, fred


@dataclass(frozen=True)
class IndexSeries:
    symbol: str
    source: str            # "cboe" or "fred"
    start: date            # first date the gap detector expects a value
    gap_rule: str          # "session" or "runs"
    description: str


INDEX_SERIES = (
    IndexSeries("VIX9D", "cboe", date(2011, 1, 4), "session", "9-day implied volatility of SPX"),
    IndexSeries("VIX3M", "cboe", date(2010, 1, 4), "session", "3-month implied volatility of SPX"),
    IndexSeries("VVIX", "cboe", date(2010, 1, 4), "session", "volatility of VIX"),
    IndexSeries("SKEW", "cboe", date(2010, 1, 4), "session", "CBOE SKEW index: price of SPX tail protection"),
    IndexSeries("BAA10Y", "fred", date(2010, 1, 4), "runs", "Moody's Baa corporate yield minus 10y Treasury, %"),
    IndexSeries("T10Y2Y", "fred", date(2010, 1, 4), "runs", "10-year minus 2-year Treasury yield, %"),
)
BY_SYMBOL = {s.symbol: s for s in INDEX_SERIES}


@dataclass(frozen=True)
class IndexValue:
    symbol: str
    date: date
    close: float


def fetch_index(series: IndexSeries, start: Optional[date] = None, end: Optional[date] = None,
                get_text: Callable[[str], str] | None = None) -> List[IndexValue]:
    if series.source == "cboe":
        return [IndexValue(series.symbol, r.date, r.close)
                for r in cboe.fetch_index_history(series.symbol, start, end, get_text)]
    if series.source == "fred":
        return [IndexValue(series.symbol, r.date, r.value) for r in fred.fetch_series(series.symbol, start, end, get_text)]
    raise ValueError(f"unknown source {series.source!r} for {series.symbol}")
