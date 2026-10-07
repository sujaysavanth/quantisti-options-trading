"""FRED daily series. Free, no API key (the public fredgraph.csv download).

- DGS3MO, the 3-month Treasury bill rate: the risk-free rate for option pricing (stored as a decimal).
- Index series for the forecast's features (stored in FRED's own units, percent points): BAA10Y (Moody's
  Baa corporate yield minus the 10-year Treasury, a credit-stress gauge) and T10Y2Y (10-year minus
  2-year Treasury, the yield curve). See app/sources/indexes.py.

FRED can be slow to answer: the first request for a series sometimes takes over a minute.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date
from typing import Callable, List, Optional

import httpx

SERIES_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
DGS3MO_URL = SERIES_URL.format(series="DGS3MO")
TIMEOUT_SECONDS = 150


@dataclass(frozen=True)
class DailyRate:
    date: date
    rate: float   # decimal: 0.0419 means 4.19%


@dataclass(frozen=True)
class DailyValue:
    date: date
    value: float  # in the series' own units


def parse_series(text: str, start: Optional[date] = None, end: Optional[date] = None) -> List[DailyValue]:
    """FRED's CSV: observation_date, <SERIES>. Bond-market holidays are blank (or '.' in older files)."""
    rows = []
    for row in csv.reader(io.StringIO(text)):
        if not row or not row[0][:1].isdigit():   # header
            continue
        day, value = date.fromisoformat(row[0]), row[1].strip()
        if value in ("", ".") or (start and day < start) or (end and day > end):
            continue
        rows.append(DailyValue(day, float(value)))
    return rows


def parse_rates(text: str, start: Optional[date] = None, end: Optional[date] = None) -> List[DailyRate]:
    """DGS3MO is published in percent; rates are stored as decimals."""
    return [DailyRate(r.date, round(r.value / 100, 6)) for r in parse_series(text, start, end)]


def _get_text(url: str) -> str:
    return httpx.get(url, timeout=TIMEOUT_SECONDS, follow_redirects=True).raise_for_status().text


def fetch_series(series: str, start: Optional[date] = None, end: Optional[date] = None,
                 get_text: Callable[[str], str] | None = None) -> List[DailyValue]:
    return parse_series((get_text or _get_text)(SERIES_URL.format(series=series)), start, end)


def fetch_rates(start: Optional[date] = None, end: Optional[date] = None,
                get_text: Callable[[str], str] | None = None) -> List[DailyRate]:
    return parse_rates((get_text or _get_text)(DGS3MO_URL), start, end)
