"""Greeks of a set of positions, priced against the live market-stream quote.

Each expiry is priced at its chain's own moment, the way the stream bridge computes the quote's IVs: spot is that
expiry's put-call-parity forward discounted back (F e^-(r-q)T), T runs from the chain's `quoted_at` to the expiry
close. So the delta per contract here equals the quote's own delta, and quotes ~15 minutes old aren't mixed with a
newer index price.

IV: the leg's own IV from the quote; when it has none (no bid, too far out), the IV of the nearest strike with one
in the same expiry (`iv_source` says which). A position whose expiry isn't on the quote, or has no IV anywhere in
its expiry, is listed in `unpriced` and left out of the totals.

Position figures are in dollars for the signed quantity (+ long, - short), x100 per contract:
    delta      P&L per 1 SPX point                 delta_1pct  P&L per 1% SPX move (delta only)
    gamma      change in `delta` per 1 SPX point   gamma_1pct  P&L from gamma alone for a 1% move: 0.5 gamma (1% S)^2
    vega       P&L per 1 volatility point          theta       P&L per calendar day
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from .. import market_spec
from .pricing import greeks

MULTIPLIER = 100
FIELDS = ("delta", "gamma", "vega", "theta", "delta_1pct", "gamma_1pct")


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _mid(leg: Mapping[str, Any]) -> Optional[float]:
    bid, ask = leg.get("bid"), leg.get("ask")
    return (bid + ask) / 2 if bid and ask and ask >= bid > 0 else None


def _iv(legs: Sequence[Mapping[str, Any]], strike: float, option_type: str):
    """(iv, source) for one contract from that expiry's quote legs."""
    for leg in legs:
        if float(leg["strike"]) == strike and leg["option_type"] == option_type and leg.get("iv"):
            return float(leg["iv"]), "quote", leg
    with_iv = [leg for leg in legs if leg.get("iv")]
    if not with_iv:
        return None, None, None
    near = min(with_iv, key=lambda leg: (abs(float(leg["strike"]) - strike), leg["option_type"] != option_type))
    own = next((leg for leg in legs if float(leg["strike"]) == strike and leg["option_type"] == option_type), None)
    return float(near["iv"]), f"nearest strike {float(near['strike']):g} {near['option_type']}", own


def _zero() -> Dict[str, float]:
    return {f: 0.0 for f in FIELDS}


@dataclass(frozen=True)
class LegInputs:
    """What a contract is priced from: its expiry's implied spot and time, and an IV."""
    spot: float
    T: float
    iv: float
    iv_source: str
    as_of: datetime
    mid: Optional[float]


class Market:
    """The live quote, indexed for pricing contracts at each expiry's own moment (see the module docstring)."""

    def __init__(self, quote: Mapping[str, Any], rate: float):
        self.rate = rate
        self.spot = float(quote["last_price"])
        self.quoted_at = quote.get("quoted_at")
        self.summaries = {e["expiry"]: e for e in quote.get("expiries", [])}
        self.legs: Dict[str, List[Mapping[str, Any]]] = {}
        for leg in quote.get("legs", []):
            self.legs.setdefault(leg["expiry"], []).append(leg)

    def inputs(self, expiry: str, strike: float, option_type: str) -> Union[LegInputs, str]:
        """LegInputs, or the reason the contract can't be priced."""
        summary = self.summaries.get(expiry)
        if summary is None:
            return "expiry not on the live quote (settled or not collected)"
        iv, iv_source, own = _iv(self.legs.get(expiry, []), strike, option_type)
        if iv is None:
            return "no implied vol in this expiry"
        as_of = _parse(summary.get("quoted_at") or self.quoted_at)
        T = market_spec.year_fraction(as_of, date.fromisoformat(expiry))
        forward = summary.get("forward")
        s = forward * math.exp(-(self.rate - market_spec.DIVIDEND_YIELD) * T) if forward else self.spot
        return LegInputs(s, T, iv, iv_source, as_of, _mid(own) if own else None)


def portfolio_greeks(positions: Sequence[Mapping[str, Any]], quote: Mapping[str, Any], rate: float) -> Dict[str, Any]:
    return market_greeks(positions, Market(quote, rate))


def market_greeks(positions: Sequence[Mapping[str, Any]], market: Market) -> Dict[str, Any]:
    rate = market.rate
    pct = market.spot / 100

    rows, unpriced = [], []
    totals, by_expiry = _zero(), {}
    for pos in positions:
        expiry, strike, kind, qty = str(pos["expiry"]), float(pos["strike"]), pos["option_type"], int(pos["quantity"])
        x = market.inputs(expiry, strike, kind)
        if isinstance(x, str):
            unpriced.append({**_key(pos), "reason": x})
            continue
        g = greeks(x.spot, strike, x.T, rate, x.iv, market_spec.DIVIDEND_YIELD, kind)
        size = qty * MULTIPLIER
        row = {**_key(pos), "iv": x.iv, "iv_source": x.iv_source, "spot": round(x.spot, 2), "as_of": x.as_of,
               "days_to_expiry": x.T * 365, "model_price": g.price, "mid": x.mid,
               "delta_per_contract": g.delta,
               "delta": g.delta * size, "gamma": g.gamma * size, "vega": g.vega * size, "theta": g.theta * size,
               "delta_1pct": g.delta * size * pct, "gamma_1pct": 0.5 * g.gamma * size * pct * pct}
        rows.append(row)
        bucket = by_expiry.setdefault(expiry, _zero())
        for f in FIELDS:
            bucket[f] += row[f]
            totals[f] += row[f]

    return {
        "spot": market.spot,
        "rate": rate,
        "quoted_at": market.quoted_at,
        "totals": totals,
        "by_expiry": [{"expiry": e, **v} for e, v in sorted(by_expiry.items())],
        "positions": rows,
        "unpriced": unpriced,
    }


def _key(pos: Mapping[str, Any]) -> Dict[str, Any]:
    return {"expiry": str(pos["expiry"]), "strike": float(pos["strike"]), "option_type": pos["option_type"],
            "quantity": int(pos["quantity"])}
