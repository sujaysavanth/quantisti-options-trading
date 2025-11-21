#!/usr/bin/env python3
"""Fetch minute-level quotes from Alpha Vantage and push them to the market-stream service."""

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

ALPHAVANTAGE_URL = "https://www.alphavantage.co/query"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("alpha_vantage_collector")


def load_env_files():
    """Load key=value pairs from .env files into os.environ."""
    repo_root = Path(__file__).resolve().parents[1]
    candidates = [repo_root / ".env", repo_root / ".env.development", repo_root / ".env.production"]
    for env_path in candidates:
        if not env_path.exists():
            continue
        with env_path.open(encoding="utf-8") as file:
            for line in file:
                if not line or line.strip().startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, value = line.rstrip().split("=", 1)
                os.environ.setdefault(key, value)


def fetch_latest_price(symbol: str, api_key: str, interval: str) -> Optional[tuple[datetime, float]]:
    """Fetch the most recent intraday bar."""
    params = {
        "function": "TIME_SERIES_INTRADAY",
        "symbol": symbol,
        "interval": interval,
        "outputsize": "compact",
        "apikey": api_key,
    }
    response = requests.get(ALPHAVANTAGE_URL, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()

    time_series_key = next((key for key in payload.keys() if "Time Series" in key), None)
    if not time_series_key:
        logger.error("Unexpected response from Alpha Vantage: %s", payload)
        return None

    time_series = payload[time_series_key]
    if not time_series:
        logger.warning("No data returned for %s", symbol)
        return None

    latest_timestamp_str = sorted(time_series.keys())[-1]
    latest_bar = time_series[latest_timestamp_str]
    close_price = float(latest_bar["4. close"])
    timestamp = datetime.fromisoformat(latest_timestamp_str).replace(tzinfo=timezone.utc)
    return timestamp, close_price


def push_quote(
    symbol: str,
    timestamp: datetime,
    price: float,
    market_stream_url: str,
):
    payload = {
        "symbol": symbol.upper(),
        "last_price": price,
        "timestamp": timestamp.isoformat(),
        "legs": []
    }
    response = requests.post(f"{market_stream_url.rstrip('/')}/v1/quotes", json=payload, timeout=15)
    response.raise_for_status()
    logger.info("Pushed quote %s @ %.2f", symbol.upper(), price)


def main():
    load_env_files()
    parser = argparse.ArgumentParser(description="Alpha Vantage minute collector -> market-stream")
    parser.add_argument("--symbol", default="^NSEI", help="Ticker symbol on Alpha Vantage (default: ^NSEI)")
    parser.add_argument("--interval", default="1min", choices=["1min", "5min"], help="Alpha Vantage interval")
    parser.add_argument("--market-stream-url", default="http://localhost:8090", help="Market stream base URL")
    parser.add_argument("--poll-seconds", type=int, default=60, help="Delay between pulls (default 60)")
    parser.add_argument("--oneshot", action="store_true", help="Fetch once and exit")
    args = parser.parse_args()

    api_key = os.getenv("ALPHAVANTAGE_API_KEY")
    if not api_key:
        logger.error("ALPHAVANTAGE_API_KEY not set. Export it or add to your environment file.")
        sys.exit(1)

    while True:
        try:
            result = fetch_latest_price(args.symbol, api_key, args.interval)
            if result:
                timestamp, price = result
                push_quote(args.symbol, timestamp, price, args.market_stream_url)
            else:
                logger.warning("Skipped push because fetch returned no data.")
        except requests.HTTPError as exc:
            logger.error("HTTP error: %s", exc, exc_info=True)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Unexpected error: %s", exc)

        if args.oneshot:
            break
        time.sleep(max(args.poll_seconds, 5))


if __name__ == "__main__":
    main()
