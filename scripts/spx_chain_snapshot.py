#!/usr/bin/env python3
"""Save today's listed SPX option chains (delayed quotes from Yahoo Finance).

Run once a day after the 16:00 ET close. Each run stores the next N expiries
for strikes near the money in option_chain_snapshots, so a history of real
quotes builds up over time; the market service prefers these rows over its
Black-Scholes chains whenever a snapshot exists for the requested date.

Usage:
    export DATABASE_URL=postgresql://quantisti:quantisti@localhost:5432/quantisti
    python scripts/spx_chain_snapshot.py --expiries 10 --moneyness 0.10

Requirements:
    pip install yfinance pandas psycopg2-binary
"""

import argparse
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch

try:
    import yfinance as yf
except ImportError:
    print("Error: yfinance not installed. Run: pip install yfinance")
    sys.exit(1)

SYMBOL = "SPX"
YAHOO_OPTIONS_TICKER = "^SPX"
SOURCE = "yahoo"
NEW_YORK = ZoneInfo("America/New_York")


def _num(value):
    return None if pd.isna(value) else float(value)


def _int(value):
    return None if pd.isna(value) else int(value)


def collect(expiry_count: int, moneyness: float) -> tuple[float, list[tuple]]:
    ticker = yf.Ticker(YAHOO_OPTIONS_TICKER)
    spot = float(ticker.history(period="1d")["Close"].iloc[-1])
    snapshot_date = datetime.now(NEW_YORK).date()
    lo, hi = spot * (1 - moneyness), spot * (1 + moneyness)

    rows: list[tuple] = []
    for expiry in ticker.options[:expiry_count]:
        chain = ticker.option_chain(expiry)
        for option_type, frame in (("C", chain.calls), ("P", chain.puts)):
            near = frame[(frame["strike"] >= lo) & (frame["strike"] <= hi)]
            for r in near.itertuples():
                rows.append((
                    SYMBOL, snapshot_date, expiry, float(r.strike), option_type, spot,
                    _num(r.bid), _num(r.ask), _num(r.lastPrice), _num(r.impliedVolatility),
                    _int(r.openInterest), _int(r.volume), SOURCE,
                ))
        print(f"  {expiry}: {sum(1 for row in rows if row[2] == expiry)} contracts")
    return spot, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Snapshot SPX option chains into Postgres")
    parser.add_argument("--expiries", type=int, default=10, help="Number of nearest expiries to save")
    parser.add_argument("--moneyness", type=float, default=0.10, help="Keep strikes within +/-this fraction of spot")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    args = parser.parse_args()

    if not args.database_url:
        sys.exit("Set DATABASE_URL or pass --database-url")

    print(f"Fetching {YAHOO_OPTIONS_TICKER} chains ...")
    spot, rows = collect(args.expiries, args.moneyness)
    if not rows:
        sys.exit("No contracts returned; Yahoo may be rate-limiting or the market data is unavailable.")

    conn = psycopg2.connect(args.database_url)
    try:
        with conn.cursor() as cur:
            execute_batch(cur, """
                INSERT INTO option_chain_snapshots (
                    symbol, snapshot_date, expiry_date, strike, option_type, underlying_price,
                    bid, ask, last, implied_volatility, open_interest, volume, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol, snapshot_date, expiry_date, strike, option_type, source) DO UPDATE SET
                    underlying_price = EXCLUDED.underlying_price, bid = EXCLUDED.bid, ask = EXCLUDED.ask,
                    last = EXCLUDED.last, implied_volatility = EXCLUDED.implied_volatility,
                    open_interest = EXCLUDED.open_interest, volume = EXCLUDED.volume
            """, rows, page_size=1000)
        conn.commit()
    finally:
        conn.close()

    print(f"Saved {len(rows)} contracts (spot {spot:,.2f})")


if __name__ == "__main__":
    main()
