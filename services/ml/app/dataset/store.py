"""Postgres I/O for the weekly dataset: read the daily history, write weekly_features / weekly_labels.

The daily tables are small (one row per session since 2010), so a build reads them whole and
recomputes every week in one pass; that keeps rolling windows and EMAs identical whether a week
was built years ago or today.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from psycopg2.extras import Json, RealDictCursor, execute_values

from . import features as F
from . import labels as L
from . import oi_levels as OI
from . import options as O
from .weeks import anchor_of_week, complete_anchors, monday_of, sessions_next_week

SYMBOL = "SPX"   # underlying_daily also has a symbol column, but only SPX is loaded
OI_COLUMNS = ("spot", "put_wall", "call_wall", "max_pain", "gex", "contracts")


def _frame(conn, sql, params=()) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [c.name for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def load_market(conn, symbol: str = SYMBOL) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(daily OHLCV, VIX closes, 3-month T-bill rates) as DataFrames, oldest first."""
    daily = _frame(conn, "SELECT date, open, high, low, close, volume FROM underlying_daily WHERE symbol = %s ORDER BY date",
                   (symbol,))
    vix = _frame(conn, "SELECT date, close FROM vix_daily ORDER BY date")
    rates = _frame(conn, "SELECT date, rate FROM rates_daily ORDER BY date")
    return daily, vix, rates


def load_indexes(conn) -> pd.DataFrame:
    """index_daily (VIX9D, VIX3M, VVIX, SKEW, BAA10Y, T10Y2Y); empty if the table doesn't exist yet."""
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('index_daily') IS NOT NULL")
        if not cur.fetchone()[0]:
            return pd.DataFrame(columns=["symbol", "date", "close"])
    return _frame(conn, "SELECT symbol, date, close FROM index_daily ORDER BY symbol, date")


def next_expiries(anchors) -> List[Tuple[date, date]]:
    """(anchor, next week's anchor = expiry) from the calendar, so the latest week has one too."""
    return [(a, n) for a in anchors if (n := anchor_of_week(a + timedelta(days=7))) is not None]


def build(conn, symbol: str = SYMBOL) -> Tuple[pd.DataFrame, pd.DataFrame]:
    daily, vix, rates = load_market(conn, symbol)
    anchors = complete_anchors(daily["date"])
    pairs = next_expiries(anchors)
    chains = load_anchor_chains(conn, pairs, symbol)
    sessions = {a: sessions_next_week(a) for a in anchors}
    options = O.option_features(chains, sessions)
    features = F.build_features(daily, vix, rates, anchors, indexes=load_indexes(conn), options=options)
    return features, L.build_labels(daily, anchors)


def build_oi_levels(conn, symbol: str = SYMBOL) -> pd.DataFrame:
    """Open-interest levels for next week's expiry at every anchor with live CBOE open interest."""
    daily, _, rates = load_market(conn, symbol)
    pairs = next_expiries(complete_anchors(daily["date"]))
    chains = load_anchor_chains(conn, pairs, symbol, sources=("cboe",))
    rate_by_day = dict(zip(rates["date"], rates["rate"].astype(float)))
    rows = []
    for (anchor, expiry), g in chains.groupby(["anchor_date", "expiry_date"]):
        years = (expiry - anchor).days / 365
        levels = OI.oi_levels(g, years, rate_by_day.get(anchor, 0.04))
        if levels:
            rows.append({"anchor_date": anchor, "expiry_date": expiry, "source": "cboe", **levels})
    return pd.DataFrame(rows, columns=["anchor_date", "expiry_date", "source", *OI_COLUMNS])


def save_oi_levels(conn, levels: pd.DataFrame, symbol: str = SYMBOL) -> int:
    cols = ["symbol", "anchor_date", "expiry_date", "source", *OI_COLUMNS]
    rows = [tuple(_clean(v) for v in (symbol, *r)) for r in levels[cols[1:]].itertuples(index=False)]
    if rows:
        with conn.cursor() as cur:
            execute_values(cur, f"""
                INSERT INTO weekly_oi_levels ({", ".join(cols)}) VALUES %s
                ON CONFLICT (symbol, anchor_date) DO UPDATE SET
                    {", ".join(f"{c} = EXCLUDED.{c}" for c in cols[2:])}, updated_at = now()""", rows)
    return len(rows)


def _clean(value):
    """numpy/NaN -> plain Python for psycopg2."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if isinstance(value, dict):
        return Json(value)
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


FORECAST_COLUMNS = ("anchor_date", "expiry_date", "method", "role", "origin", "spot", "vix_close",
                    "q05", "q10", "q50", "q90", "q95", "trained_through", "details", "explanation")


def save_forecasts(conn, forecasts: pd.DataFrame, symbol: str = SYMBOL) -> int:
    """Insert forecasts; an anchor + method that already has one is left as it was (forecasts are made once)."""
    forecasts = forecasts.assign(**{c: None for c in FORECAST_COLUMNS if c not in forecasts.columns})
    rows = [tuple(_clean(v) for v in (symbol, *r)) for r in forecasts[list(FORECAST_COLUMNS)].itertuples(index=False)]
    if not rows:
        return 0
    with conn.cursor() as cur:
        # RETURNING + fetch: cur.rowcount would only count execute_values' last page of 100 rows
        inserted = execute_values(cur, f"""
            INSERT INTO weekly_forecasts (symbol, {", ".join(FORECAST_COLUMNS)}) VALUES %s
            ON CONFLICT (symbol, anchor_date, method) DO NOTHING RETURNING 1""", rows, fetch=True)
        return len(inserted)


def save_explanation(conn, anchor: date, method: str, explanation: dict, symbol: str = SYMBOL) -> int:
    """Store an explanation for a forecast that has none (an existing one is never replaced)."""
    with conn.cursor() as cur:
        cur.execute("""UPDATE weekly_forecasts SET explanation = %s
                       WHERE symbol = %s AND anchor_date = %s AND method = %s AND explanation IS NULL""",
                    (Json(explanation), symbol, anchor, method))
        return cur.rowcount


def forecast_anchors(conn, symbol: str = SYMBOL) -> set:
    """Anchors that already have a forecast from every method."""
    with conn.cursor() as cur:
        cur.execute("""SELECT anchor_date FROM weekly_forecasts WHERE symbol = %s GROUP BY anchor_date
                       HAVING count(*) >= 3""", (symbol,))
        return {r[0] for r in cur.fetchall()}


def read_forecasts(conn, symbol: str = SYMBOL, anchor: Optional[date] = None) -> pd.DataFrame:
    """Stored forecasts with their outcomes (close_ret is empty until the following week has closed)."""
    where, params = ("AND f.anchor_date = %s", (symbol, anchor)) if anchor else ("", (symbol,))
    return _frame(conn, f"""
        SELECT f.*, l.close_ret
        FROM weekly_forecasts f
        LEFT JOIN weekly_labels l ON l.symbol = f.symbol AND l.anchor_date = f.anchor_date
        WHERE f.symbol = %s {where}
        ORDER BY f.anchor_date, f.method""", params)


EXPIRY_FORECAST_COLUMNS = ("origin_date", "expiry_date", "sessions", "method", "origin", "spot", "vix_close",
                           "q05", "q10", "q50", "q90", "q95", "sigma", "z", "variance_path", "path_dates", "trained_through")


def save_expiry_forecasts(conn, forecasts: pd.DataFrame, symbol: str = SYMBOL) -> int:
    """Insert expiry forecasts; an origin + expiry that already has one is left as it was."""
    if forecasts.empty:
        return 0
    rows = [tuple(_clean(v) for v in (symbol, *r)) for r in forecasts[list(EXPIRY_FORECAST_COLUMNS)].itertuples(index=False)]
    with conn.cursor() as cur:
        inserted = execute_values(cur, f"""
            INSERT INTO expiry_forecasts (symbol, {", ".join(EXPIRY_FORECAST_COLUMNS)}) VALUES %s
            ON CONFLICT (symbol, origin_date, expiry_date, method) DO NOTHING RETURNING 1""", rows, page_size=1000, fetch=True)
        return len(inserted)


def expiry_origins(conn, symbol: str = SYMBOL) -> set:
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT origin_date FROM expiry_forecasts WHERE symbol = %s", (symbol,))
        return {r[0] for r in cur.fetchall()}


def read_expiry_forecasts(conn, symbol: str = SYMBOL, origin: Optional[date] = None) -> pd.DataFrame:
    """Stored expiry forecasts with outcomes: close_ret = ln(close at expiry / origin close), empty until then."""
    where, params = ("AND f.origin_date = %s", (symbol, origin)) if origin else ("", (symbol,))
    return _frame(conn, f"""
        SELECT f.*, ln(u.close / f.spot) AS close_ret
        FROM expiry_forecasts f
        LEFT JOIN underlying_daily u ON u.symbol = f.symbol AND u.date = f.expiry_date
        WHERE f.symbol = %s {where}
        ORDER BY f.origin_date, f.expiry_date""", params)


CHAIN_COLUMNS = ["anchor_date", "expiry_date", "source", "strike", "option_type", "bid", "ask",
                 "vendor_iv", "vendor_delta", "volume", "open_interest", "underlying_price"]


def load_anchor_chains(conn, pairs: Sequence[Tuple[date, date]], symbol: str = SYMBOL,
                       sources: Optional[Sequence[str]] = None, moneyness: float = 0.05) -> pd.DataFrame:
    """Quotes taken on each anchor date for the paired expiry (next week's), strikes within `moneyness` of spot,
    every source (or only `sources`). Real chains: OptionsDX 2010-2023, CBOE and Yahoo since October 2026."""
    if not pairs:
        return pd.DataFrame(columns=CHAIN_COLUMNS)
    with conn.cursor() as cur:
        values = ",".join(cur.mogrify("(%s::date, %s::date)", tuple(p)).decode() for p in pairs)   # quoted by psycopg2
        source_filter = "AND s.source = ANY(%s)" if sources else ""
        params = (symbol, moneyness, list(sources)) if sources else (symbol, moneyness)
        cur.execute(f"""
            WITH want(anchor_date, expiry_date) AS (VALUES {values})
            SELECT w.anchor_date, w.expiry_date, s.source, s.strike, s.option_type, s.bid, s.ask,
                   s.vendor_iv, s.vendor_delta, s.volume, s.open_interest, s.underlying_price
            FROM want w
            JOIN option_chain_snapshots s
              ON s.symbol = %s AND s.snapshot_date = w.anchor_date AND s.expiry_date = w.expiry_date
            WHERE abs(s.strike - s.underlying_price) <= %s * s.underlying_price {source_filter}""", params)
        rows = cur.fetchall()
    frame = pd.DataFrame(rows, columns=CHAIN_COLUMNS)
    for c in ("strike", "bid", "ask", "vendor_iv", "vendor_delta", "underlying_price"):
        frame[c] = frame[c].astype(float)
    for c in ("volume", "open_interest"):
        frame[c] = pd.to_numeric(frame[c])
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
