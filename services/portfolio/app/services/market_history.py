"""Read-only market history for the performance stats: SPX closes (underlying_daily) and the 3-month T-bill
(rates_daily), both loaded by the streaming pipeline."""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Tuple

from ..db.connection import get_db_connection, return_db_connection


def _rows(sql: str, args: tuple) -> list:
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return [tuple(r.values()) if isinstance(r, dict) else tuple(r) for r in cur.fetchall()]
    finally:
        return_db_connection(conn)


def spx_closes(start: date, end: date) -> Dict[date, float]:
    rows = _rows("SELECT date, close FROM underlying_daily WHERE symbol = 'SPX' AND date BETWEEN %s AND %s", (start, end))
    return {d: float(c) for d, c in rows}


def rates(start: date, end: date) -> List[Tuple[date, float]]:
    """Rates from a week before `start` (FRED lags), in date order."""
    rows = _rows("SELECT date, rate FROM rates_daily WHERE date BETWEEN %s::date - 7 AND %s ORDER BY date", (start, end))
    return [(d, float(r)) for d, r in rows]
