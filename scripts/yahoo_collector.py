#!/usr/bin/env python3
"""Fetch intraday candles from Yahoo Finance and forward to market-stream."""

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import requests

YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("yahoo_collector")

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; QuantistiCollector/1.0)",
    "Accept": "application/json",
}


def fetch_latest(symbol: str, interval: str = "1m", range_: str = "1d") -> Optional[tuple[datetime, float]]:
    params = {
        "interval": interval,
        "range": range_,
    }
    response = requests.get(
        YAHOO_URL.format(symbol=symbol),
        params=params,
        headers=DEFAULT_HEADERS,
        timeout=30
    )
    response.raise_for_status()
    payload = response.json()

    result = payload.get("chart", {}).get("result")
    if not result:
        logger.error("Yahoo payload missing data: %s", json.dumps(payload))
        return None

    data = result[0]
    timestamps = data.get("timestamp")
    indicators = data.get("indicators", {}).get("quote", [])
    if not timestamps or not indicators:
        logger.warning("No timestamps/quotes in response.")
        return None

    prices = indicators[0].get("close")
    if not prices:
        return None

    # Last non-null price
    for ts, price in reversed(list(zip(timestamps, prices))):
        if price is not None:
            timestamp = datetime.fromtimestamp(ts, tz=timezone.utc)
            return timestamp, float(price)
    return None


def push(symbol: str, timestamp: datetime, price: float, market_stream_url: str):
    payload = {
        "symbol": symbol.upper(),
        "last_price": price,
        "timestamp": timestamp.isoformat(),
        "legs": []
    }
    response = requests.post(f"{market_stream_url.rstrip('/')}/v1/quotes", json=payload, timeout=15)
    response.raise_for_status()
    logger.info("Pushed %s @ %s", symbol.upper(), price)


def main():
    parser = argparse.ArgumentParser(description="Yahoo Finance minute collector -> market-stream")
    parser.add_argument("--symbol", default="^NSEI", help="Yahoo ticker (default: ^NSEI)")
    parser.add_argument("--interval", default="1m", help="Yahoo interval (1m,5m,15m, etc.)")
    parser.add_argument("--range", default="1d", help="Yahoo range (1d,5d,1mo, etc.)")
    parser.add_argument("--market-stream-url", default="http://localhost:8090")
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--oneshot", action="store_true")
    args = parser.parse_args()

    while True:
        try:
            latest = fetch_latest(args.symbol, args.interval, args.range)
            if latest:
                push(args.symbol, latest[0], latest[1], args.market_stream_url)
            else:
                logger.warning("No latest price available.")
        except requests.HTTPError as exc:
            logger.error("HTTP error: %s", exc)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Unexpected error: %s", exc)

        if args.oneshot:
            break
        time.sleep(max(args.poll_seconds, 30))


if __name__ == "__main__":
    main()
