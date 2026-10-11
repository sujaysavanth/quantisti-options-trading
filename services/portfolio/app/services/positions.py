"""Pure views over the simulator's paper trades (the JSON of GET /v1/paper/orders).

net_positions   open legs netted by contract (symbol, expiry, strike, type) across trades: a long call in one
                trade and a short of the same call in another cancel. Signed quantity (+ long, - short),
                average entry price of the net position, the current mid and unrealised P&L.
trade_rows      one row per leg of the trade history, for the CSV export.
"""

from __future__ import annotations

import csv
import io
from typing import Any, Dict, Iterable, List

MULTIPLIER = 100

Trade = Dict[str, Any]


def _sign(side: str) -> int:
    return 1 if side == "BUY" else -1


def net_positions(trades: Iterable[Trade]) -> List[Dict[str, Any]]:
    """Net open positions, nearest expiry first. Contracts that net to zero are left out."""
    book: Dict[tuple, Dict[str, Any]] = {}
    for trade in trades:
        if trade.get("status", "open") != "open":
            continue
        for leg in trade["legs"]:
            key = (trade["symbol"], leg["expiry"], float(leg["strike"]), leg["option_type"])
            row = book.setdefault(key, {"symbol": key[0], "expiry": key[1], "strike": key[2], "option_type": key[3],
                                        "quantity": 0, "cost": 0.0, "mark": None, "unrealised_pnl": 0.0,
                                        "trade_ids": []})
            qty = _sign(leg["side"]) * int(leg["quantity"])
            row["quantity"] += qty
            row["cost"] += qty * float(leg.get("entry_price") or 0.0)
            row["unrealised_pnl"] += float(leg.get("pnl") or 0.0)
            if leg.get("current_price") is not None:
                row["mark"] = float(leg["current_price"])
            if trade["id"] not in row["trade_ids"]:
                row["trade_ids"].append(trade["id"])

    out = []
    for row in book.values():
        qty = row.pop("quantity")
        cost = row.pop("cost")
        if qty == 0:
            continue
        mark = row["mark"]
        out.append({**row, "quantity": qty, "side": "LONG" if qty > 0 else "SHORT",
                    "avg_entry_price": cost / qty,
                    "market_value": qty * mark * MULTIPLIER if mark is not None else None})
    return sorted(out, key=lambda r: (r["expiry"], r["option_type"], r["strike"]))


TRADE_COLUMNS = ["trade_id", "nickname", "symbol", "status", "opened_at", "closed_at", "close_reason", "trade_pnl",
                 "expiry", "side", "quantity", "option_type", "strike", "entry_price", "exit_price", "leg_pnl"]


def trade_rows(trades: Iterable[Trade]) -> List[Dict[str, Any]]:
    rows = []
    for t in sorted(trades, key=lambda t: t["created_at"]):
        for leg in t["legs"]:
            rows.append({
                "trade_id": t["id"], "nickname": t.get("nickname"), "symbol": t["symbol"], "status": t["status"],
                "opened_at": t["created_at"], "closed_at": t.get("closed_at"), "close_reason": t.get("close_reason"),
                "trade_pnl": round(float(t["pnl"]), 2), "expiry": leg["expiry"], "side": leg["side"],
                "quantity": leg["quantity"], "option_type": leg["option_type"], "strike": leg["strike"],
                "entry_price": leg.get("entry_price"), "exit_price": leg.get("exit_price"),
                "leg_pnl": round(float(leg["pnl"]), 2)})
    return rows


def to_csv(rows: List[Dict[str, Any]]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=TRADE_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()
