#!/usr/bin/env python3
"""Push mock quotes into the market-stream service."""

import argparse
import json
from datetime import date, datetime, timezone

import requests


def occ_symbol(root: str, expiry: date, option_type: str, strike: float) -> str:
    """OCC contract symbol, e.g. SPXW261002C06600000."""
    return f"{root}{expiry:%y%m%d}{option_type[0]}{round(strike * 1000):08d}"


def parse_leg(raw: str, expiry: date):
    """Parse leg string format ROOT:STRIKE:CALL|PUT, e.g. SPXW:6600:CALL."""
    root, strike_text, option_type = raw.split(":")
    strike = float(strike_text)
    return {
        "identifier": occ_symbol(root, expiry, option_type, strike),
        "strike": strike,
        "option_type": option_type,
        "expiry": expiry.isoformat(),
        "bid": None,
        "ask": None,
        "last": None,
    }


def main():
    parser = argparse.ArgumentParser(description="Publish mock quotes to market-stream")
    parser.add_argument("--endpoint", default="http://localhost:8090/v1/quotes", help="Quote upsert endpoint")
    parser.add_argument("--symbol", default="SPX")
    parser.add_argument("--price", type=float, required=True)
    parser.add_argument("--expiry", type=date.fromisoformat, default=datetime.now(timezone.utc).date(),
                        help="Leg expiry YYYY-MM-DD (default: today, i.e. 0DTE)")
    parser.add_argument("--legs", nargs="*", default=[], help="Option legs ROOT:STRIKE:CALL|PUT, e.g. SPXW:6600:CALL")

    args = parser.parse_args()
    legs = [parse_leg(leg, args.expiry) for leg in args.legs]

    payload = {
        "symbol": args.symbol.upper(),
        "last_price": args.price,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "legs": legs,
    }

    response = requests.post(args.endpoint, json=payload, timeout=10)
    response.raise_for_status()
    print(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    main()
