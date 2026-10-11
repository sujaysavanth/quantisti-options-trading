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
from datetime import date, datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence

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


def portfolio_greeks(positions: Sequence[Mapping[str, Any]], quote: Mapping[str, Any], rate: float) -> Dict[str, Any]:
    q = market_spec.DIVIDEND_YIELD
    spot = float(quote["last_price"])
    pct = spot / 100
    summaries = {e["expiry"]: e for e in quote.get("expiries", [])}
    legs_by_expiry: Dict[str, List[Mapping[str, Any]]] = {}
    for leg in quote.get("legs", []):
        legs_by_expiry.setdefault(leg["expiry"], []).append(leg)

    rows, unpriced = [], []
    totals, by_expiry = _zero(), {}
    for pos in positions:
        expiry, strike, kind, qty = str(pos["expiry"]), float(pos["strike"]), pos["option_type"], int(pos["quantity"])
        summary = summaries.get(expiry)
        if summary is None:
            unpriced.append({**_key(pos), "reason": "expiry not on the live quote (settled or not collected)"})
            continue
        iv, iv_source, own = _iv(legs_by_expiry.get(expiry, []), strike, kind)
        if iv is None:
            unpriced.append({**_key(pos), "reason": "no implied vol in this expiry"})
            continue
        as_of = _parse(summary.get("quoted_at") or quote["quoted_at"])
        T = market_spec.year_fraction(as_of, date.fromisoformat(expiry))
        forward = summary.get("forward")
        s = forward * math.exp(-(rate - q) * T) if forward else spot
        g = greeks(s, strike, T, rate, iv, q, kind)
        size = qty * MULTIPLIER
        row = {**_key(pos), "iv": iv, "iv_source": iv_source, "spot": round(s, 2), "as_of": as_of,
               "days_to_expiry": T * 365, "model_price": g.price, "mid": _mid(own) if own else None,
               "delta_per_contract": g.delta,
               "delta": g.delta * size, "gamma": g.gamma * size, "vega": g.vega * size, "theta": g.theta * size,
               "delta_1pct": g.delta * size * pct, "gamma_1pct": 0.5 * g.gamma * size * pct * pct}
        rows.append(row)
        bucket = by_expiry.setdefault(expiry, _zero())
        for f in FIELDS:
            bucket[f] += row[f]
            totals[f] += row[f]

    return {
        "spot": spot,
        "rate": rate,
        "quoted_at": quote.get("quoted_at"),
        "totals": totals,
        "by_expiry": [{"expiry": e, **v} for e, v in sorted(by_expiry.items())],
        "positions": rows,
        "unpriced": unpriced,
    }


def _key(pos: Mapping[str, Any]) -> Dict[str, Any]:
    return {"expiry": str(pos["expiry"]), "strike": float(pos["strike"]), "option_type": pos["option_type"],
            "quantity": int(pos["quantity"])}
