#!/usr/bin/env python3
"""Load US market data for SPX option pricing.

Sources (all free, no API key):
  - S&P 500 daily OHLCV        Yahoo Finance ^GSPC (via yfinance)   -> underlying_daily
  - VIX daily close            CBOE VIX_History.csv                 -> vix_daily
  - 3-month T-bill rate        FRED DGS3MO                          -> rates_daily

Every table is upserted, so re-running refreshes recent rows without duplicates.

Usage:
    export DATABASE_URL=postgresql://quantisti:quantisti@localhost:5432/quantisti
    python scripts/populate_us_data.py --start-date 2015-01-01

Requirements:
    pip install yfinance pandas psycopg2-binary
"""

import argparse
import os
import sys
from datetime import date, datetime

import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch

try:
    import yfinance as yf
except ImportError:
    print("Error: yfinance not installed. Run: pip install yfinance")
    sys.exit(1)

SYMBOL = "SPX"
YAHOO_TICKER = "^GSPC"
VIX_CSV_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS3MO"
HV_WINDOW = 30


def load_underlying(start: date, end: date) -> pd.DataFrame:
    print(f"Downloading {YAHOO_TICKER} {start} -> {end} ...")
    # Fetch a little extra history so the first rows already have a volatility value.
    warmup_start = pd.Timestamp(start) - pd.Timedelta(days=HV_WINDOW * 2)
    df = yf.download(YAHOO_TICKER, start=warmup_start, end=pd.Timestamp(end) + pd.Timedelta(days=1),
                     progress=False, auto_adjust=False)
    if df.empty:
        raise RuntimeError("No index data returned; check the date range and network access.")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower).reset_index().rename(columns={"Date": "date"})
    df["date"] = pd.to_datetime(df["date"]).dt.date

    log_returns = np.log(df["close"]).diff()
    df["historical_volatility"] = (log_returns.rolling(HV_WINDOW).std() * np.sqrt(252)).round(4)
    df = df[df["date"] >= start]
    return df[["date", "open", "high", "low", "close", "volume", "historical_volatility"]]


def load_vix(start: date, end: date) -> pd.DataFrame:
    print("Downloading CBOE VIX history ...")
    df = pd.read_csv(VIX_CSV_URL)
    df.columns = [c.strip().lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"], format="%m/%d/%Y").dt.date
    df = df[(df["date"] >= start) & (df["date"] <= end)]
    return df[["date", "close"]].dropna()


def load_rates(start: date, end: date) -> pd.DataFrame:
    print("Downloading FRED DGS3MO ...")
    df = pd.read_csv(FRED_CSV_URL, na_values=["."])
    df.columns = [c.strip().lower() for c in df.columns]
    date_col = "observation_date" if "observation_date" in df.columns else "date"
    df["date"] = pd.to_datetime(df[date_col]).dt.date
    df["rate"] = df["dgs3mo"] / 100.0  # FRED publishes percent
    df = df[(df["date"] >= start) & (df["date"] <= end)]
    return df[["date", "rate"]].dropna()


def upsert(conn, sql: str, rows: list[tuple]) -> None:
    with conn.cursor() as cur:
        execute_batch(cur, sql, rows, page_size=1000)
    conn.commit()


def nullable(value):
    return None if pd.isna(value) else float(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load SPX, VIX and T-bill data for option pricing")
    parser.add_argument("--start-date", default="2015-01-01", help="YYYY-MM-DD")
    parser.add_argument("--end-date", default=date.today().isoformat(), help="YYYY-MM-DD")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    args = parser.parse_args()

    if not args.database_url:
        sys.exit("Set DATABASE_URL or pass --database-url, e.g. postgresql://quantisti:quantisti@localhost:5432/quantisti")

    start = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end = datetime.strptime(args.end_date, "%Y-%m-%d").date()

    underlying = load_underlying(start, end)
    vix = load_vix(start, end)
    rates = load_rates(start, end)

    conn = psycopg2.connect(args.database_url)
    try:
        upsert(conn, """
            INSERT INTO underlying_daily (symbol, date, open, high, low, close, volume, historical_volatility)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol, date) DO UPDATE SET
                open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low, close = EXCLUDED.close,
                volume = EXCLUDED.volume, historical_volatility = EXCLUDED.historical_volatility
        """, [
            (SYMBOL, r.date, float(r.open), float(r.high), float(r.low), float(r.close),
             int(r.volume) if pd.notna(r.volume) else 0, nullable(r.historical_volatility))
            for r in underlying.itertuples()
        ])
        upsert(conn, """
            INSERT INTO vix_daily (date, close) VALUES (%s, %s)
            ON CONFLICT (date) DO UPDATE SET close = EXCLUDED.close
        """, [(r.date, float(r.close)) for r in vix.itertuples()])
        upsert(conn, """
            INSERT INTO rates_daily (date, rate) VALUES (%s, %s)
            ON CONFLICT (date) DO UPDATE SET rate = EXCLUDED.rate
        """, [(r.date, float(r.rate)) for r in rates.itertuples()])

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*), MIN(date), MAX(date), MAX(close) FROM underlying_daily WHERE symbol = %s", (SYMBOL,))
            n, lo, hi, last = cur.fetchone()
            cur.execute("SELECT COUNT(*), MAX(date) FROM vix_daily")
            vn, vhi = cur.fetchone()
            cur.execute("SELECT COUNT(*), MAX(date) FROM rates_daily")
            rn, rhi = cur.fetchone()
    finally:
        conn.close()

    print(f"underlying_daily  {n:>6} rows  {lo} -> {hi}")
    print(f"vix_daily         {vn:>6} rows  -> {vhi}")
    print(f"rates_daily       {rn:>6} rows  -> {rhi}")


if __name__ == "__main__":
    main()
