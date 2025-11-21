#!/usr/bin/env python3
"""Push mock quotes into the market-stream service."""

import argparse
import json
from datetime import datetime, timezone
from typing import List

import requests


def parse_leg(raw: str):
    """Parse leg string format SYMBOL:STRIKE:TYPE."""
    symbol, strike, option_type = raw.split(":")
    return {
        "identifier": f"{symbol}{strike:.0f}{option_type}",
        "strike": float(strike),
        "option_type": option_type,
        "expiry": datetime.now(timezone.utc).date().isoformat(),
        "bid": None,
        "ask": None,
        "last": None,
    }


def main():
    parser = argparse.ArgumentParser(description="Publish mock quotes to market-stream")
    parser.add_argument("--endpoint", default="http://localhost:8090/v1/quotes", help="Quote upsert endpoint")
    parser.add_argument("--symbol", default="NIFTY")
    parser.add_argument("--price", type=float, required=True)
    parser.add_argument("--legs", nargs="*", default=[], help="Option legs symbol:strike:CALL|PUT")

    args = parser.parse_args()
    legs = [parse_leg(leg) for leg in args.legs]

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
