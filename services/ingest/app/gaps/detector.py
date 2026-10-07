"""Find missing data by comparing what's stored with the NYSE calendar.

`find_gaps` is pure: it takes a `Coverage` (what the database holds, loaded by store.py) and
the current time, and returns the gaps. Rules per dataset:

- daily SPX:  a row per session since 2010-01-04.
- VIX:        the same, except the latest session (CBOE's history file can lag a day).
- rates:      only runs of more than RATES_MAX_RUN missing sessions; FRED posts late and
              the bond market closes on some NYSE sessions (Columbus Day, Veterans Day).
- index:      each series in sources/indexes.py from its start date, by its gap_rule: CBOE series
              like VIX, FRED series like rates.
- intraday:  per symbol and bar size, only sessions Yahoo still serves; a session with
              fewer than 98% of its bars is a gap (see expected.py).
- chain:      the OptionsDX years (2010-2023) and every session since live collection began.
              The years in between have no free source; they are KNOWN, not gaps.

Known ranges are reported once (GET /v1/gaps -> known) instead of as a row per day.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from ..sources.indexes import INDEX_SERIES
from .expected import closed_sessions, expected_bars, in_source_window, min_bars

DAILY_START = date(2010, 1, 4)          # first session in underlying_daily / vix_daily / rates_daily
OPTIONSDX_END = date(2023, 12, 29)      # last session in the OptionsDX import
SYMBOLS = ("SPX", "VIX")
INTERVALS = ("1m", "5m", "1h")
RATES_MAX_RUN = 3


@dataclass(frozen=True)
class Gap:
    dataset: str        # daily | vix | rates | intraday | chain  (ingest_gaps.dataset)
    symbol: str         # SPX, VIX, DGS3MO, or "SPX:1m" for intraday
    gap_date: date
    detail: str


@dataclass(frozen=True)
class KnownRange:
    dataset: str
    start: date
    end: date
    reason: str

    def covers(self, dataset: str, day: date) -> bool:
        return dataset == self.dataset and self.start <= day <= self.end


@dataclass
class Coverage:
    daily: Set[date] = field(default_factory=set)
    vix: Set[date] = field(default_factory=set)
    rates: Set[date] = field(default_factory=set)
    bars: Dict[Tuple[str, str], Dict[date, int]] = field(default_factory=dict)   # (symbol, interval) -> bars per session
    chain: Set[date] = field(default_factory=set)
    collection_start: Optional[date] = None   # first chain session not from OptionsDX
    indexes: Dict[str, Set[date]] = field(default_factory=dict)   # index_daily: symbol -> dates stored


# Edit this list when the data changes (e.g. a missing OptionsDX month gets downloaded and imported).
FIXED_KNOWN = (
    KnownRange("chain", date(2010, 1, 27), date(2010, 2, 5), "OptionsDX files are blank for these sessions"),
)


def known_ranges(cov: Coverage, today: date) -> List[KnownRange]:
    """FIXED_KNOWN plus the synthetic-only years between OptionsDX and live collection."""
    synthetic_end = cov.collection_start - timedelta(days=1) if cov.collection_start else today
    return [*FIXED_KNOWN,
            KnownRange("chain", date(2024, 1, 1), synthetic_end,
                       "no free source for these chains; the market service prices them with Black-Scholes from VIX")]


def _missing_runs(sessions: List[date], have: Set[date]) -> List[List[date]]:
    """Consecutive missing sessions, grouped."""
    runs, run = [], []
    for d in sessions:
        if d in have:
            if run:
                runs.append(run)
            run = []
        else:
            run.append(d)
    if run:
        runs.append(run)
    return runs


def find_gaps(cov: Coverage, now: datetime) -> List[Gap]:
    sessions = closed_sessions(DAILY_START, now)
    if not sessions:
        return []
    known = known_ranges(cov, sessions[-1])
    gaps: List[Gap] = []

    gaps += [Gap("daily", "SPX", d, "no daily row") for d in sessions if d not in cov.daily]
    gaps += [Gap("vix", "VIX", d, "no VIX close") for d in sessions[:-1] if d not in cov.vix]
    for run in _missing_runs(sessions, cov.rates):
        if len(run) > RATES_MAX_RUN:
            gaps += [Gap("rates", "DGS3MO", d, f"rate missing {len(run)} sessions in a row") for d in run]

    for series in INDEX_SERIES:
        have = cov.indexes.get(series.symbol, set())
        own = [d for d in sessions if d >= series.start]
        if series.gap_rule == "session":                                    # like VIX: the latest may lag
            gaps += [Gap("index", series.symbol, d, f"no {series.symbol} close") for d in own[:-1] if d not in have]
        else:                                                               # like rates: only long runs
            for run in _missing_runs(own, have):
                if len(run) > RATES_MAX_RUN:
                    gaps += [Gap("index", series.symbol, d, f"{series.symbol} missing {len(run)} sessions in a row")
                             for d in run]

    for symbol in SYMBOLS:
        for interval in INTERVALS:
            counts = cov.bars.get((symbol, interval), {})
            for d in sessions:
                if not in_source_window(d, interval, now):
                    continue
                n = counts.get(d, 0)
                if n < min_bars(d, interval):
                    gaps.append(Gap("intraday", f"{symbol}:{interval}", d, f"bars {n}/{expected_bars(d, interval)}"))

    chain_days = [d for d in sessions if d <= OPTIONSDX_END
                  or (cov.collection_start is not None and d >= cov.collection_start)]
    gaps += [Gap("chain", "SPX", d, "no chain snapshot") for d in chain_days
             if d not in cov.chain and not any(k.covers("chain", d) for k in known)]
    return gaps
