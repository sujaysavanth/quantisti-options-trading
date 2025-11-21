#!/usr/bin/env python3
"""Fetch Nifty option chain from NSE and push leg quotes to market-stream."""

import argparse
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests

NSE_OPTION_CHAIN_URL = "https://www.nseindia.com/api/option-chain-indices"
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; QuantistiCollector/1.0)",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9"
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("nse_option_chain_collector")


def fetch_option_chain(symbol: str) -> Dict:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    session.get("https://www.nseindia.com", timeout=10)
    response = session.get(NSE_OPTION_CHAIN_URL, params={"symbol": symbol}, timeout=30)
    response.raise_for_status()
    return response.json()


def _parse_expiry(expiry_str: str) -> Optional[str]:
    try:
        # e.g., "28-Nov-2025"
        return datetime.strptime(expiry_str, "%d-%b-%Y").date().isoformat()
    except Exception:
        logger.debug("Could not parse expiry %s", expiry_str)
        return None


def extract_leg_quotes(raw: Dict, max_legs: int) -> List[Dict]:
    legs: List[Dict] = []
    records = raw.get("records", {}).get("data", [])
    underlying = raw.get("records", {}).get("underlyingValue")
    if underlying is not None:
        records = sorted(records, key=lambda entry: abs(entry.get("strikePrice", 0) - underlying))
    for entry in records:
        strike = entry.get("strikePrice")
        expiry = entry.get("expiryDate")
        expiry_iso = _parse_expiry(expiry) if expiry else None
        for option_type in ("CE", "PE"):
            option = entry.get(option_type)
            if not option:
                continue
            identifier = option.get("identifier") or f"NIFTY{expiry}{strike}{option_type}"
            legs.append({
                "identifier": identifier,
                "strike": float(strike),
                "option_type": "CALL" if option_type == "CE" else "PUT",
                "expiry": expiry_iso or datetime.now().date().isoformat(),
                "bid": option.get("bidprice"),
                "ask": option.get("askPrice"),
                "last": option.get("lastPrice"),
                "iv": option.get("impliedVolatility"),
            })
            if len(legs) >= max_legs:
                return legs
    return legs


def push_payload(payload: Dict, market_stream_url: str):
    response = requests.post(f"{market_stream_url.rstrip('/')}/v1/quotes", json=payload, timeout=20)
    if response.status_code >= 400:
        logger.error("Market stream error %s: %s", response.status_code, response.text)
    response.raise_for_status()
    logger.info("Pushed %s with %d legs", payload["symbol"], len(payload["legs"]))


def main():
    parser = argparse.ArgumentParser(description="NSE option chain collector -> market-stream")
    parser.add_argument("--symbol", default="NIFTY")
    parser.add_argument("--market-stream-url", default="http://localhost:8090")
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--max-legs", type=int, default=200, help="Limit number of legs per push to reduce payload size")
    parser.add_argument("--oneshot", action="store_true")
    args = parser.parse_args()

    while True:
        try:
            chain = fetch_option_chain(args.symbol)
            legs = extract_leg_quotes(chain, args.max_legs)
            payload = {
                "symbol": args.symbol,
                "last_price": chain.get("records", {}).get("underlyingValue"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "legs": legs
            }
            push_payload(payload, args.market_stream_url)
        except requests.HTTPError as exc:
            logger.error("HTTP error: %s", exc)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Unexpected error: %s", exc)

        if args.oneshot:
            break
        time.sleep(max(args.poll_seconds, 30))


if __name__ == "__main__":
    main()
