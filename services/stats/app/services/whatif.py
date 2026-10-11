"""What a candidate trade would do to the open book's risk, before it is placed.

The candidate is priced as the paper account would fill it: each leg at its mid on the live quote (the model price
when the leg has no two-sided quote; `price_source` says which). Then the same measures are computed for the book
as it is and with the candidate added:
    Greeks             dollar delta, gamma per 1% move, vega, theta (exposure.py units)
    VaR / shortfall    filtered historical, 95% and 99% (var.py's headline method)
    stress             the worst SPX x IV grid scenario and the worst replayed SPX day (P&L only)
Capital is the simulator's rule for the candidate on its own (each paper trade holds its own capital), checked
against what the account has available: the order would be refused if it needs more.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from . import stress as st
from . import var
from .exposure import Market, market_greeks
from .pricing import bs_price
from .. import market_spec

CANDIDATE_ID = "candidate"
METRICS = ("delta", "gamma_1pct", "vega", "theta", "var95", "var99", "es99", "worst_stress", "worst_day")


def candidate_trade(legs: Sequence[Mapping[str, Any]], market: Market) -> Dict[str, Any]:
    """The candidate in the simulator's trade shape, or {"errors": [...]} when a leg can't be priced."""
    out, errors = [], []
    for leg in legs:
        expiry, strike, kind = str(leg["expiry"]), float(leg["strike"]), leg["option_type"]
        x = market.inputs(expiry, strike, kind)
        if isinstance(x, str):
            errors.append(f"{strike:g} {kind} {expiry}: {x}")
            continue
        price = x.mid if x.mid is not None else bs_price(x.spot, strike, x.T, market.rate, x.iv,
                                                          market_spec.DIVIDEND_YIELD, kind)
        out.append({"expiry": expiry, "strike": strike, "option_type": kind, "side": leg["side"],
                    "quantity": int(leg["quantity"]), "entry_price": price,
                    "price_source": "mid" if x.mid is not None else "model"})
    if errors:
        return {"errors": errors}
    return {"id": CANDIDATE_ID, "status": "open", "legs": out}


def _positions(trades: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Signed positions for exposure.portfolio_greeks (no netting needed: Greeks add up)."""
    return [{"expiry": str(leg["expiry"]), "strike": float(leg["strike"]), "option_type": leg["option_type"],
             "quantity": (1 if leg["side"] == "BUY" else -1) * int(leg["quantity"])}
            for t in trades for leg in t["legs"]]


def measure(trades: Sequence[Mapping[str, Any]], market: Market, rate: float, moves: Sequence[var.Move],
            sigma_now: Optional[float], days: Sequence[Mapping[str, Any]]) -> Dict[str, Optional[float]]:
    totals = market_greeks(_positions(trades), market)["totals"]
    legs, _ = st.book(trades, market)
    out: Dict[str, Optional[float]] = {k: totals[k] for k in ("delta", "gamma_1pct", "vega", "theta")}
    out.update(var95=None, var99=None, es99=None)
    if moves:
        filtered, _, _ = var.filtered_moves(moves, sigma_now)
        pnl = [st.revalue(legs, len(trades), rate, st.Scenario("", r, dv, 1))[0] for r, dv in filtered]
        out["var95"] = var.var_es(pnl, 0.95)[0]
        out["var99"], out["es99"] = var.var_es(pnl, 0.99)
    grid = [st.revalue(legs, len(trades), rate, s)[0] for s in st.grid()]
    history = [st.revalue(legs, len(trades), rate, s)[0] for s in st.historical(days)]
    out["worst_stress"] = min(grid) if grid else None
    out["worst_day"] = min(history) if history else None
    return out


def compare(before: Mapping[str, Optional[float]], after: Mapping[str, Optional[float]]) -> List[Dict[str, Any]]:
    return [{"metric": k, "before": before.get(k), "after": after.get(k),
             "change": None if before.get(k) is None or after.get(k) is None else after[k] - before[k]}
            for k in METRICS]


def capital_check(required: Optional[float], basis: Optional[str], available: float) -> Dict[str, Any]:
    return {"required": required, "basis": basis, "available_now": available,
            "available_after": None if required is None else available - required,
            "fits": None if required is None else required <= available + 1e-6}
