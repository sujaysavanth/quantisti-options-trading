#!/usr/bin/env python3
"""Save the current SPX option chain to Postgres (free ~15-min-delayed quotes).

Uses the ingest service's chain sources (services/ingest/app/sources): CBOE by
default (includes open interest), Yahoo as a fallback. Rows are stamped with the
real quote time and the trading session it belongs to, so running this at any
hour gives correct dates. Best run shortly after the 16:00 ET close.

Usage:
    export DATABASE_URL=postgresql://quantisti:quantisti@localhost:5432/quantisti
    python scripts/spx_chain_snapshot.py --expiries 10 --moneyness 0.10

Requirements:
    pip install -e services/ingest psycopg2-binary
"""

import argparse
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_batch

# Use the ingest service's code straight from the repo (no install needed for its package).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "ingest"))
from app.sources import chain_source  # noqa: E402

UPSERT = """
    INSERT INTO option_chain_snapshots (
        symbol, snapshot_date, expiry_date, strike, option_type, underlying_price,
        bid, ask, last, open_interest, volume, vendor_iv, vendor_delta, quoted_at, source)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (symbol, snapshot_date, expiry_date, strike, option_type, source) DO UPDATE SET
        underlying_price = EXCLUDED.underlying_price, bid = EXCLUDED.bid, ask = EXCLUDED.ask,
        last = EXCLUDED.last, open_interest = EXCLUDED.open_interest, volume = EXCLUDED.volume,
        vendor_iv = EXCLUDED.vendor_iv, vendor_delta = EXCLUDED.vendor_delta, quoted_at = EXCLUDED.quoted_at
    -- newest quote wins; an older capture never overwrites a newer one
    WHERE option_chain_snapshots.quoted_at IS NULL OR EXCLUDED.quoted_at >= option_chain_snapshots.quoted_at
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Snapshot the SPX option chain into Postgres")
    parser.add_argument("--source", choices=["cboe", "yahoo"], default="cboe")
    parser.add_argument("--expiries", type=int, default=10, help="Number of nearest live expiries to save")
    parser.add_argument("--moneyness", type=float, default=0.10, help="Keep strikes within +/-this fraction of spot")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    args = parser.parse_args()

    if not args.database_url:
        sys.exit("Set DATABASE_URL or pass --database-url")

    snap = chain_source(args.source).fetch_chain(args.expiries, args.moneyness)
    if not snap.quotes:
        sys.exit(f"No contracts returned from {snap.source}; the source may be rate-limiting or unavailable.")

    rows = [
        (snap.symbol, snap.session_date, q.expiry, q.strike, q.option_type, snap.underlying_price,
         q.bid, q.ask, q.last, q.open_interest, q.volume, q.vendor_iv, q.vendor_delta, snap.quoted_at, snap.source)
        for q in snap.quotes
    ]
    conn = psycopg2.connect(args.database_url)
    try:
        with conn.cursor() as cur:
            execute_batch(cur, UPSERT, rows, page_size=1000)
        conn.commit()
    finally:
        conn.close()

    expiries = sorted({q.expiry for q in snap.quotes})
    print(f"Saved {len(rows)} contracts from {snap.source}: session {snap.session_date}, "
          f"quoted {snap.quoted_at:%Y-%m-%d %H:%M}Z, spot {snap.underlying_price:,.2f}, "
          f"expiries {expiries[0]} .. {expiries[-1]} ({len(expiries)})")


if __name__ == "__main__":
    main()
