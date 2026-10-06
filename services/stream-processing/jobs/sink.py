"""Idempotent Postgres upserts for each micro-batch.

Spark may run a micro-batch again after a crash (it replays from the last
checkpoint), so every write here is an upsert: writing the same rows twice
leaves the table exactly as writing them once ("exactly-once-ish").

Functions take an open connection and don't commit; the caller commits once
per micro-batch so a batch lands completely or not at all.
"""

from datetime import date, datetime, timezone
from typing import Iterable, Optional, Sequence

from psycopg2.extras import execute_values

UPSERT_CHAIN = """
    INSERT INTO option_chain_snapshots (
        symbol, snapshot_date, expiry_date, strike, option_type, underlying_price,
        bid, ask, last, open_interest, volume, vendor_iv, vendor_delta, quoted_at, source)
    VALUES %s
    ON CONFLICT (symbol, snapshot_date, expiry_date, strike, option_type, source) DO UPDATE SET
        underlying_price = EXCLUDED.underlying_price, bid = EXCLUDED.bid, ask = EXCLUDED.ask,
        last = EXCLUDED.last, open_interest = EXCLUDED.open_interest, volume = EXCLUDED.volume,
        vendor_iv = EXCLUDED.vendor_iv, vendor_delta = EXCLUDED.vendor_delta, quoted_at = EXCLUDED.quoted_at
    -- newest quote wins; a replayed or late older capture never overwrites a newer one
    WHERE option_chain_snapshots.quoted_at IS NULL OR EXCLUDED.quoted_at >= option_chain_snapshots.quoted_at
"""

UPSERT_UNDERLYING = """
    INSERT INTO underlying_daily (symbol, date, open, high, low, close, volume) VALUES %s
    ON CONFLICT (symbol, date) DO UPDATE SET
        open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
        close = EXCLUDED.close, volume = EXCLUDED.volume
"""

UPSERT_VIX = """
    INSERT INTO vix_daily (date, close) VALUES %s
    ON CONFLICT (date) DO UPDATE SET close = EXCLUDED.close
"""

UPSERT_RATES = """
    INSERT INTO rates_daily (date, rate) VALUES %s
    ON CONFLICT (date) DO UPDATE SET rate = EXCLUDED.rate
"""

# Annualised close-to-close vol over the last 30 log returns, like scripts/populate_us_data.py
# (pandas rolling std = sample std = stddev_samp). Recomputed from `since` on; the 90-day lookback
# gives the first recomputed rows a full window. Rows without 30 returns behind them are left alone.
RECOMPUTE_HV = """
    WITH r AS (
        SELECT date, ln(close::float8 / lag(close::float8) OVER (ORDER BY date)) AS lr
        FROM underlying_daily
        WHERE symbol = %(symbol)s AND date >= %(since)s::date - 90
    ), hv AS (
        SELECT date,
               stddev_samp(lr) OVER w * sqrt(252) AS hv,
               count(lr) OVER w AS n
        FROM r
        WINDOW w AS (ORDER BY date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW)
    )
    UPDATE underlying_daily u
    SET historical_volatility = round(hv.hv::numeric, 4)
    FROM hv
    WHERE u.symbol = %(symbol)s AND u.date = hv.date AND hv.date >= %(since)s AND hv.n = 30
"""


def utc(ts: Optional[datetime]) -> Optional[datetime]:
    """Spark hands back naive datetimes in the session time zone (UTC here); make them explicit for timestamptz."""
    if ts is None or ts.tzinfo is not None:
        return ts
    return ts.replace(tzinfo=timezone.utc)


def write_chain(conn, rows: Sequence[tuple]) -> int:
    """Rows in UPSERT_CHAIN column order; quoted_at is index 13."""
    if not rows:
        return 0
    rows = [r[:13] + (utc(r[13]),) + r[14:] for r in rows]
    with conn.cursor() as cur:
        execute_values(cur, UPSERT_CHAIN, rows, page_size=1000)
    return len(rows)


def write_daily(conn, underlying: Sequence[tuple], vix: Sequence[tuple], rates: Sequence[tuple]) -> int:
    with conn.cursor() as cur:
        if underlying:
            execute_values(cur, UPSERT_UNDERLYING, underlying)
            for symbol, since in _earliest_per_symbol(underlying):
                cur.execute(RECOMPUTE_HV, {"symbol": symbol, "since": since})
        if vix:
            execute_values(cur, UPSERT_VIX, vix)
        if rates:
            execute_values(cur, UPSERT_RATES, rates)
    return len(underlying) + len(vix) + len(rates)


def _earliest_per_symbol(rows: Iterable[tuple]):
    earliest = {}
    for symbol, day, *_ in rows:
        if symbol not in earliest or day < earliest[symbol]:
            earliest[symbol] = day
    return sorted(earliest.items())
