"""Price and expiry helpers for market-stream quotes, shared by live strategies and paper trades."""

from __future__ import annotations

from typing import Dict, List, Optional


def leg_price(leg: Optional[Dict]) -> float:
    """The bid/ask mid when the quote is two-sided; otherwise the last trade, then whichever side exists.

    The last trade can be hours old on a thin strike, so it is only a fallback.
    """
    if not leg:
        return 0.0
    bid, ask = leg.get("bid"), leg.get("ask")
    if bid and ask and ask >= bid > 0:
        return round((bid + ask) / 2, 4)
    for key in ("last", "bid", "ask"):
        value = leg.get(key)
        if value not in (None, 0):
            return float(value)
    return 0.0


def available_expiries(quote: Dict) -> List[str]:
    return sorted({str(leg["expiry"]) for leg in quote.get("legs") or [] if leg.get("expiry")})


def select_expiry(quote: Dict, requested: Optional[str] = None) -> Optional[str]:
    """`requested` if the quote has it (else None); with no request, the quote's default or nearest expiry."""
    available = available_expiries(quote)
    if requested:
        return requested if requested in available else None
    default = quote.get("default_expiry")
    if default and str(default) in available:
        return str(default)
    return available[0] if available else None
