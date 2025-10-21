#!/usr/bin/env python3
"""Populate Nifty historical data from Yahoo Finance.

This script downloads historical Nifty 50 index data and populates
the nifty_historical table in PostgreSQL.

Usage:
    python scripts/populate_nifty_data.py --start-date 2015-01-01 --end-date 2024-12-31

Requirements:
    pip install yfinance psycopg2-binary pandas numpy
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch

try:
    import yfinance as yf
except ImportError:
    print("Error: yfinance not installed. Run: pip install yfinance")
    sys.exit(1)


def calculate_historical_volatility(prices: pd.Series, window: int = 30) -> float:
    """Calculate annualized historical volatility.

    Args:
        prices: Series of closing prices
        window: Rolling window size (default 30 days)

    Returns:
        Annualized volatility as a decimal (e.g., 0.15 for 15%)
    """
    if len(prices) < window + 1:
        return None

    # Calculate daily returns
    returns = prices.pct_change().dropna()

    # Calculate rolling volatility
    volatility = returns.rolling(window=window).std().iloc[-1]

    # Annualize (assuming 252 trading days)
    annual_volatility = volatility * (252 ** 0.5)

    return round(annual_volatility, 4) if pd.notna(annual_volatility) else None


def download_nifty_data(start_date: str, end_date: str) -> pd.DataFrame:
    """Download Nifty 50 historical data from Yahoo Finance.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        DataFrame with OHLCV data
    """
    print(f"Downloading Nifty data from {start_date} to {end_date}...")

    # Yahoo Finance ticker for Nifty 50
    ticker = "^NSEI"

    try:
        df = yf.download(ticker, start=start_date, end=end_date, progress=True, auto_adjust=False)

        if df.empty:
            raise ValueError("No data downloaded. Check date range and internet connection.")

        # Reset index to make Date a column
        df.reset_index(inplace=True)

        # Handle MultiIndex columns (new yfinance behavior)
        if isinstance(df.columns, pd.MultiIndex):
            # Flatten MultiIndex - take just the first level
            df.columns = df.columns.get_level_values(0)

        # Standardize column names to lowercase
        df.columns = [col.lower().strip() if isinstance(col, str) else str(col).lower().strip()
                      for col in df.columns]

        # Map columns to our expected names
        column_mapping = {
            'date': 'date',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume',
            'adj close': 'adj_close'  # Handle 'Adj Close' if present
        }

        # Rename columns that exist
        df = df.rename(columns=column_mapping)

        # Select only the columns we need
        required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']

        # Verify all required columns exist
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}. Available: {df.columns.tolist()}")

        df = df[required_cols]

        # Calculate historical volatility for each row
        print("Calculating historical volatility...")
        df['historical_volatility'] = df['close'].expanding(min_periods=31).apply(
            lambda x: calculate_historical_volatility(x, window=30), raw=False
        )

        print(f"Downloaded {len(df)} rows of data")
        return df

    except Exception as e:
        print(f"Error downloading data: {e}")
        sys.exit(1)


def get_database_connection(database_url: Optional[str] = None) -> psycopg2.extensions.connection:
    """Get PostgreSQL database connection.

    Args:
        database_url: PostgreSQL connection string. If None, reads from DATABASE_URL env var.

    Returns:
        PostgreSQL connection object
    """
    if database_url is None:
        database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("Error: DATABASE_URL environment variable not set")
        print("Example: export DATABASE_URL=postgresql://quantisti:quantisti@localhost:5432/quantisti")
        sys.exit(1)

    try:
        conn = psycopg2.connect(database_url)
        print(f"Connected to database successfully")
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)


def populate_database(df: pd.DataFrame, conn: psycopg2.extensions.connection, batch_size: int = 1000):
    """Populate nifty_historical table with data.

    Args:
        df: DataFrame with Nifty historical data
        conn: PostgreSQL connection
        batch_size: Number of rows to insert per batch
    """
    print(f"Populating database with {len(df)} rows...")

    cursor = conn.cursor()

    # Prepare data for insertion
    rows = []
    for _, row in df.iterrows():
        rows.append((
            row['date'].date() if isinstance(row['date'], pd.Timestamp) else row['date'],
            float(row['open']),
            float(row['high']),
            float(row['low']),
            float(row['close']),
            int(row['volume']),
            float(row['historical_volatility']) if pd.notna(row['historical_volatility']) else None
        ))

    # Insert in batches
    insert_query = """
        INSERT INTO nifty_historical (date, open, high, low, close, volume, historical_volatility)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (date)
        DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            historical_volatility = EXCLUDED.historical_volatility,
            updated_at = now()
    """

    try:
        execute_batch(cursor, insert_query, rows, page_size=batch_size)
        conn.commit()
        print(f"✅ Successfully inserted/updated {len(rows)} rows")

        # Print summary stats
        cursor.execute("""
            SELECT
                COUNT(*) as total_rows,
                MIN(date) as earliest_date,
                MAX(date) as latest_date,
                ROUND(AVG(close), 2) as avg_close,
                ROUND(AVG(volume), 0) as avg_volume
            FROM nifty_historical
        """)
        stats = cursor.fetchone()
        print("\n📊 Database Summary:")
        print(f"   Total rows: {stats[0]}")
        print(f"   Date range: {stats[1]} to {stats[2]}")
        print(f"   Avg close: ₹{stats[3]:,.2f}")
        print(f"   Avg volume: {stats[4]:,.0f}")

    except Exception as e:
        conn.rollback()
        print(f"Error inserting data: {e}")
        sys.exit(1)
    finally:
        cursor.close()


def main():
    parser = argparse.ArgumentParser(description='Populate Nifty historical data')
    parser.add_argument('--start-date', type=str, default='2015-01-01',
                       help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, default=datetime.now().strftime('%Y-%m-%d'),
                       help='End date (YYYY-MM-DD)')
    parser.add_argument('--database-url', type=str, default=None,
                       help='PostgreSQL connection string (default: from DATABASE_URL env var)')

    args = parser.parse_args()

    print("=" * 60)
    print("Nifty Historical Data Population Script")
    print("=" * 60)

    # Download data
    df = download_nifty_data(args.start_date, args.end_date)

    # Connect to database
    conn = get_database_connection(args.database_url)

    # Populate database
    populate_database(df, conn)

    # Close connection
    conn.close()
    print("\n✅ Done!")


if __name__ == '__main__':
    main()
