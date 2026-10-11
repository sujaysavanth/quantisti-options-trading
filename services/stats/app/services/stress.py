"""Stress scenarios for the open paper trades: full revaluation of every leg under SPX and volatility shocks.

Each leg starts from the same inputs as its Greeks (exposure.Market: its expiry's implied spot and time, the quote's
IV) and is repriced with Black-Scholes after the shock:
    spot  x (1 + SPX move)            IV  + shift in vol points (floored at 1%)
    time  - horizon in calendar days  (an expiry that passes settles at intrinsic on the shocked spot)
P&L is shocked model value - current model value, so the unshocked scenario is exactly 0 and every number is the
shock's effect alone (the current mark-to-market is in the account figures).

Grid: SPX_MOVES x IV_SHIFTS x HORIZONS. History: the largest SPX daily falls and rises in underlying_daily, each
with that day's VIX change applied as the IV shift and one day passing. VIX is 30-day implied vol; short-dated IV
usually moves more than VIX on the same day, so these replays understate the vol shock for weekly options.

Capital after a shock comes from the simulator (POST /v1/paper/capital-held): defined risk keeps its max loss,
uncovered shorts' CBOE margin follows the shocked spot and marks. available after = available now + capital held
now - capital held after; `short_of_capital` flags scenarios where that goes below zero (a margin call).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .. import market_spec
from .exposure import LegInputs, Market
from .pricing import bs_price, intrinsic

MULTIPLIER = 100
SPX_MOVES = (-0.10, -0.07, -0.05, -0.03, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03, 0.05, 0.07, 0.10)
IV_SHIFTS = (-5.0, 0.0, 5.0, 10.0)        # volatility points
HORIZONS = (0, 1)                          # calendar days
MIN_IV = 0.01


@dataclass(frozen=True)
class Scenario:
    name: str
    spx_move: float
    iv_shift: float
    days: int
    date: Optional[str] = None             # historical replays: the day replayed


@dataclass
class PricedLeg:
    trade: int
    leg: int
    strike: float
    option_type: str
    signed_qty: int
    inputs: Optional[LegInputs]            # None: not on the quote
    entry_price: float


def book(trades: Sequence[Mapping[str, Any]], market: Market):
    """(priced legs, unpriced list) for the open trades (the simulator's /v1/paper/orders shape)."""
    legs, unpriced = [], []
    for i, t in enumerate(trades):
        for j, leg in enumerate(t["legs"]):
            x = market.inputs(str(leg["expiry"]), float(leg["strike"]), leg["option_type"])
            if isinstance(x, str):
                unpriced.append({"trade_id": t["id"], "expiry": str(leg["expiry"]), "strike": float(leg["strike"]),
                                 "option_type": leg["option_type"], "reason": x})
                x = None
            sign = 1 if leg["side"] == "BUY" else -1
            legs.append(PricedLeg(i, j, float(leg["strike"]), leg["option_type"], sign * int(leg["quantity"]), x,
                                  float(leg.get("entry_price") or 0.0)))
    return legs, unpriced


def _value(x: LegInputs, strike: float, kind: str, rate: float, move: float, shift: float, days: int) -> float:
    spot = x.spot * (1 + move)
    T = x.T - days / 365
    if T <= 0:
        return intrinsic(kind, strike, spot)
    return bs_price(spot, strike, T, rate, max(x.iv + shift / 100, MIN_IV), market_spec.DIVIDEND_YIELD, kind)


def revalue(legs: Sequence[PricedLeg], n_trades: int, rate: float, s: Scenario):
    """(P&L in dollars, marks per trade per leg). Unpriced legs add nothing and keep no mark (the simulator then
    uses their entry price)."""
    pnl = 0.0
    marks: List[List[Optional[float]]] = [[] for _ in range(n_trades)]
    for leg in legs:
        if leg.inputs is None:
            marks[leg.trade].append(None)
            continue
        base = _value(leg.inputs, leg.strike, leg.option_type, rate, 0.0, 0.0, 0)
        shocked = _value(leg.inputs, leg.strike, leg.option_type, rate, s.spx_move, s.iv_shift, s.days)
        pnl += leg.signed_qty * MULTIPLIER * (shocked - base)
        marks[leg.trade].append(shocked)
    return pnl, marks


def grid() -> List[Scenario]:
    return [Scenario(f"SPX {m:+.0%}, IV {v:+g} pts, +{d}d", m, v, d)
            for d in HORIZONS for v in IV_SHIFTS for m in SPX_MOVES]


def historical(days: Sequence[Mapping[str, Any]]) -> List[Scenario]:
    """`days`: {date, spx_return, vix_change} rows (vix_change in points, None if VIX is missing that day)."""
    return [Scenario(f"{d['date']}: SPX {d['spx_return']:+.1%}, VIX {d['vix_change'] or 0:+.1f}", float(d["spx_return"]),
                     float(d["vix_change"] or 0.0), 1, str(d["date"])) for d in days]


def capital_request(trades: Sequence[Mapping[str, Any]], spot: float, scenarios: Sequence[Scenario],
                    marks: Sequence[List[List[Optional[float]]]]) -> Dict[str, Any]:
    """Body for the simulator's POST /v1/paper/capital-held."""
    return {
        "trades": [{"legs": [{"strike": float(leg["strike"]), "option_type": leg["option_type"], "side": leg["side"],
                              "quantity": int(leg["quantity"]), "entry_price": float(leg.get("entry_price") or 0.0)}
                             for leg in t["legs"]]} for t in trades],
        "scenarios": [{"spot": spot * (1 + s.spx_move), "marks": m} for s, m in zip(scenarios, marks)],
    }


def results(scenarios: Sequence[Scenario], pnls: Sequence[float], held_after: Sequence[Optional[float]],
            account: Mapping[str, Any]) -> List[Dict[str, Any]]:
    value, held_now, available = (float(account[k]) for k in ("account_value", "capital_held", "available"))
    rows = []
    for s, pnl, held in zip(scenarios, pnls, held_after):
        after = None if held is None else available + held_now - held
        rows.append({"name": s.name, "date": s.date, "spx_move": s.spx_move, "iv_shift": s.iv_shift, "days": s.days,
                     "pnl": pnl, "pct_of_account": pnl / value if value else None,
                     "account_value_after": value + pnl, "capital_held_after": held, "available_after": after,
                     "short_of_capital": after is not None and after < 0})
    return rows


def summary(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {"worst": None, "best": None, "margin_calls": 0}
    worst = min(rows, key=lambda r: r["pnl"])
    best = max(rows, key=lambda r: r["pnl"])
    return {"worst": {"name": worst["name"], "pnl": worst["pnl"]}, "best": {"name": best["name"], "pnl": best["pnl"]},
            "margin_calls": sum(r["short_of_capital"] for r in rows)}
