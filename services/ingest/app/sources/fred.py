"""FRED 3-month Treasury bill rate (DGS3MO): the risk-free rate for option pricing. Free, no API key."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date
from typing import Callable, List, Optional

import httpx

DGS3MO_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS3MO"


@dataclass(frozen=True)
class DailyRate:
    date: date
    rate: float   # decimal: 0.0419 means 4.19%


def parse_rates(text: str, start: Optional[date] = None, end: Optional[date] = None) -> List[DailyRate]:
    """FRED's CSV: observation_date, DGS3MO (percent). Bond-market holidays are blank (or '.' in older files)."""
    rows = []
    for row in csv.reader(io.StringIO(text)):
        if not row or not row[0][:1].isdigit():   # header
            continue
        day, value = date.fromisoformat(row[0]), row[1].strip()
        if value in ("", ".") or (start and day < start) or (end and day > end):
            continue
        rows.append(DailyRate(day, round(float(value) / 100, 6)))
    return rows


def fetch_rates(start: Optional[date] = None, end: Optional[date] = None,
                get_text: Callable[[str], str] | None = None) -> List[DailyRate]:
    get_text = get_text or (lambda url: httpx.get(url, timeout=60, follow_redirects=True).raise_for_status().text)
    return parse_rates(get_text(DGS3MO_URL), start, end)
