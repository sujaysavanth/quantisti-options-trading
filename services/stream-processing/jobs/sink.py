"""Idempotent Postgres upserts for each micro-batch.

Spark may run a micro-batch again after a crash (it replays from the last
checkpoint), so every write here is an upsert: writing the same rows twice
leaves the table exactly as writing them once ("exactly-once-ish").

Functions take an open connection and don't commit; the caller commits once
per micro-batch so a batch lands completely or not at all.
"""

import csv
import io
from datetime import datetime, timezone
from typing import Iterable, Optional, Sequence

from psycopg2.extras import execute_values

CHAIN_COLUMNS = ("symbol, snapshot_date, expiry_date, strike, option_type, underlying_price, bid, ask, last, "
                 "open_interest, volume, vendor_iv, vendor_delta, quoted_at, source")

# Conflict rule for a contract already stored that session:
# - a capture older than the stored quote (a replayed batch, a late message) changes nothing;
# - open interest and volume take the newer values. (When a quote-less capture was kept out, quoted_at still
#   holds the older quote's time, so a replay of a quote-less capture in between can set them back slightly.)
# - the quote itself (bid/ask/last, vendor IV/delta, the spot it was taken against, and quoted_at, which
#   says when it was taken) is only replaced by a two-sided quote, or when the stored one isn't two-sided
#   either. CBOE sometimes publishes a capture with no bid/ask at all (2026-10-05 16:14 ET); without this,
#   that capture wiped out the day's real quotes.
_TWO_SIDED = "COALESCE({t}.bid > 0 AND {t}.ask >= {t}.bid, false)"
_REPLACE_QUOTE = f"({_TWO_SIDED.format(t='EXCLUDED')} OR NOT {_TWO_SIDED.format(t='option_chain_snapshots')})"
_QUOTE_COLUMNS = ("underlying_price", "bid", "ask", "last", "vendor_iv", "vendor_delta", "quoted_at")
_CHAIN_CONFLICT = (
    "ON CONFLICT (symbol, snapshot_date, expiry_date, strike, option_type, source) DO UPDATE SET\n        "
    + ",\n        ".join(
        [f"{c} = CASE WHEN {_REPLACE_QUOTE} THEN EXCLUDED.{c} ELSE option_chain_snapshots.{c} END" for c in _QUOTE_COLUMNS]
        + ["open_interest = EXCLUDED.open_interest", "volume = EXCLUDED.volume"])
    + "\n    WHERE option_chain_snapshots.quoted_at IS NULL OR EXCLUDED.quoted_at >= option_chain_snapshots.quoted_at"
)

UPSERT_CHAIN = f"""
    INSERT INTO option_chain_snapshots ({CHAIN_COLUMNS})
    VALUES %s
    {_CHAIN_CONFLICT}
"""

# Bulk version of UPSERT_CHAIN for historical imports: COPY into a temp table (far faster than
# INSERT ... VALUES for millions of rows), then one INSERT ... SELECT with the same conflict rule.
COPY_UPSERT_CHAIN = f"""
    INSERT INTO option_chain_snapshots ({CHAIN_COLUMNS})
    SELECT {CHAIN_COLUMNS} FROM chain_stage
    {_CHAIN_CONFLICT}
"""

UPSERT_BARS = """
    INSERT INTO intraday_bars (symbol, interval, ts, open, high, low, close, volume, source) VALUES %s
    ON CONFLICT (symbol, interval, ts) DO UPDATE SET
        open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low, close = EXCLUDED.close,
        volume = EXCLUDED.volume, source = EXCLUDED.source, ingested_at = now()
    -- A vendor's own bar is always a complete interval; our 'agg_1m' 5m bars can miss a minute.
    -- So vendor bars replace anything, while an aggregate only replaces an earlier aggregate.
    WHERE EXCLUDED.source <> 'agg_1m' OR intraday_bars.source = 'agg_1m'
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


def copy_chain(conn, rows: Iterable[tuple]) -> int:
    """Bulk upsert of chain rows (UPSERT_CHAIN column order) through COPY and a temp staging table."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    count = 0
    for r in rows:
        r = list(r)
        r[13] = utc(r[13]).isoformat() if r[13] is not None else None      # quoted_at
        writer.writerow(["" if v is None else v for v in r])
        count += 1
    if not count:
        return 0
    buf.seek(0)
    with conn.cursor() as cur:
        cur.execute(f"CREATE TEMP TABLE chain_stage AS SELECT {CHAIN_COLUMNS} FROM option_chain_snapshots WITH NO DATA")
        cur.copy_expert(f"COPY chain_stage ({CHAIN_COLUMNS}) FROM STDIN WITH (FORMAT csv, NULL '')", buf)
        cur.execute(COPY_UPSERT_CHAIN)
        cur.execute("DROP TABLE chain_stage")      # not ON COMMIT DROP: callers may run several per transaction
    return count


def write_bars(conn, rows: Sequence[tuple]) -> int:
    """Rows: (symbol, interval, ts, open, high, low, close, volume, source). A later write of the
    same bar replaces it, which is what lets a growing 5m window overwrite its earlier partial self."""
    if not rows:
        return 0
    rows = [r[:2] + (utc(r[2]),) + r[3:] for r in rows]
    with conn.cursor() as cur:
        execute_values(cur, UPSERT_BARS, rows, page_size=1000)
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
