"""Postgres I/O for the weekly dataset: read the daily history, write weekly_features / weekly_labels.

The daily tables are small (one row per session since 2010), so a build reads them whole and
recomputes every week in one pass; that keeps rolling windows and EMAs identical whether a week
was built years ago or today.
"""

from __future__ import annotations

from datetime import date
from typing import Optional, Tuple

import numpy as np
import pandas as pd
from psycopg2.extras import RealDictCursor, execute_values

from . import features as F
from . import labels as L
from .weeks import complete_anchors, monday_of

SYMBOL = "SPX"   # underlying_daily also has a symbol column, but only SPX is loaded


def load_market(conn, symbol: str = SYMBOL) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(daily OHLCV, VIX closes, 3-month T-bill rates) as DataFrames, oldest first."""
    def frame(sql, params=()):
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [c.name for c in cur.description]
            return pd.DataFrame(cur.fetchall(), columns=cols)
    daily = frame("SELECT date, open, high, low, close, volume FROM underlying_daily WHERE symbol = %s ORDER BY date",
                  (symbol,))
    vix = frame("SELECT date, close FROM vix_daily ORDER BY date")
    rates = frame("SELECT date, rate FROM rates_daily ORDER BY date")
    return daily, vix, rates


def build(conn, symbol: str = SYMBOL) -> Tuple[pd.DataFrame, pd.DataFrame]:
    daily, vix, rates = load_market(conn, symbol)
    anchors = complete_anchors(daily["date"])
    return F.build_features(daily, vix, rates, anchors), L.build_labels(daily, anchors)


def _clean(value):
    """numpy/NaN -> plain Python for psycopg2."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if np.isnan(value) else float(value)
    return value


def save(conn, features: pd.DataFrame, labels: pd.DataFrame, symbol: str = SYMBOL) -> Tuple[int, int]:
    """Upsert every week; re-running replaces rows with the same values. Caller commits."""
    fcols = ["symbol", *F.COLUMNS, "feature_version"]
    frows = [tuple(_clean(v) for v in (symbol, *row, F.FEATURE_VERSION))
             for row in features[list(F.COLUMNS)].itertuples(index=False)]
    lcols = ["symbol", *L.COLUMNS]
    lrows = [tuple(_clean(v) for v in (symbol, *row)) for row in labels[list(L.COLUMNS)].itertuples(index=False)]
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in fcols if c not in ("symbol", "week_start_date"))
    with conn.cursor() as cur:
        if frows:
            execute_values(cur, f"""
                INSERT INTO weekly_features ({", ".join(fcols)}) VALUES %s
                ON CONFLICT (week_start_date, symbol) DO UPDATE SET {updates}, updated_at = NOW()""",
                frows, page_size=500)
        if lrows:
            execute_values(cur, f"""
                INSERT INTO weekly_labels ({", ".join(lcols)}) VALUES %s
                ON CONFLICT (symbol, anchor_date) DO UPDATE SET
                    next_anchor_date = EXCLUDED.next_anchor_date, sessions = EXCLUDED.sessions,
                    close_ret = EXCLUDED.close_ret, high_ret = EXCLUDED.high_ret, low_ret = EXCLUDED.low_ret""",
                lrows, page_size=500)
    return len(frows), len(lrows)


def read_week(conn, symbol: str, day: date) -> Optional[dict]:
    """The stored week containing `day` (any day of it)."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM weekly_features WHERE symbol = %s AND week_start_date = %s", (symbol, monday_of(day)))
        return cur.fetchone()


def read_latest(conn, symbol: str) -> Optional[dict]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM weekly_features WHERE symbol = %s ORDER BY week_start_date DESC LIMIT 1", (symbol,))
        return cur.fetchone()


def load_straddle_quotes(conn, pairs, symbol: str = SYMBOL) -> pd.DataFrame:
    """Near-the-money OptionsDX quotes (strikes within 1% of spot) for each (anchor_date, expiry_date) pair:
    the chain at a week's close for next week's expiry. Real quotes exist for 2010-2023 only."""
    columns = ["anchor_date", "strike", "option_type", "bid", "ask", "underlying_price"]
    if not pairs:
        return pd.DataFrame(columns=columns)
    with conn.cursor() as cur:
        values = ",".join(cur.mogrify("(%s::date, %s::date)", tuple(p)).decode() for p in pairs)   # quoted by psycopg2
        cur.execute(f"""
            WITH want(anchor_date, expiry_date) AS (VALUES {values})
            SELECT w.anchor_date, s.strike, s.option_type, s.bid, s.ask, s.underlying_price
            FROM want w
            JOIN option_chain_snapshots s
              ON s.symbol = %s AND s.source = 'optionsdx'
             AND s.snapshot_date = w.anchor_date AND s.expiry_date = w.expiry_date
            WHERE abs(s.strike - s.underlying_price) <= 0.01 * s.underlying_price""", (symbol,))
        rows = cur.fetchall()
    frame = pd.DataFrame(rows, columns=columns)
    for c in ("strike", "bid", "ask", "underlying_price"):
        frame[c] = frame[c].astype(float)
    return frame


def read_dataset(conn, symbol: str = SYMBOL) -> pd.DataFrame:
    """Model features joined with labels: one row per anchor, label columns empty for the latest week."""
    cols = ", ".join(f"f.{c}" for c in ("week_start_date", "anchor_date", *F.MODEL_FEATURES))
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT {cols}, l.next_anchor_date, l.sessions, l.close_ret, l.high_ret, l.low_ret
            FROM weekly_features f
            LEFT JOIN weekly_labels l ON l.symbol = f.symbol AND l.anchor_date = f.anchor_date
            WHERE f.symbol = %s AND f.anchor_date IS NOT NULL
            ORDER BY f.anchor_date""", (symbol,))
        names = [c.name for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=names)
