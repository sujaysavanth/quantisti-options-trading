"""Black-Scholes pieces the bridge needs, without scipy.

Same maths as services/market/app/services/chains.py (`infer_forward`,
`implied_vol`). Free delayed feeds report an underlying price and IVs that
don't match their own option quotes, so the forward is taken from put-call
parity and IV is recomputed from each mid against it.
"""

from __future__ import annotations

import math
import statistics
from typing import Dict, Iterable, Optional, Tuple

MIN_IV, MAX_IV = 0.03, 3.0


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs_price(spot: float, strike: float, T: float, rate: float, vol: float, q: float, option_type: str) -> float:
    """European option price; option_type 'C' or 'P'."""
    if T <= 0:
        return max(spot - strike, 0.0) if option_type == "C" else max(strike - spot, 0.0)
    sd = vol * math.sqrt(T)
    d1 = (math.log(spot / strike) + (rate - q + 0.5 * vol * vol) * T) / sd
    d2 = d1 - sd
    disc_s, disc_k = spot * math.exp(-q * T), strike * math.exp(-rate * T)
    if option_type == "C":
        return disc_s * _norm_cdf(d1) - disc_k * _norm_cdf(d2)
    return disc_k * _norm_cdf(-d2) - disc_s * _norm_cdf(-d1)


def bs_delta(spot: float, strike: float, T: float, rate: float, vol: float, q: float, option_type: str) -> float:
    """dPrice/dSpot: 0..1 for calls, -1..0 for puts."""
    if T <= 0:
        itm = spot > strike if option_type == "C" else spot < strike
        return (1.0 if option_type == "C" else -1.0) if itm else 0.0
    d1 = (math.log(spot / strike) + (rate - q + 0.5 * vol * vol) * T) / (vol * math.sqrt(T))
    carry = math.exp(-q * T)
    return carry * _norm_cdf(d1) if option_type == "C" else carry * (_norm_cdf(d1) - 1)


def implied_vol(price: Optional[float], spot: float, strike: float, T: float, rate: float, q: float,
                option_type: str) -> Optional[float]:
    """Vol that reproduces `price`, or None when the price is outside no-arbitrage bounds.

    Bisection: the price rises with vol, so halve the [MIN_IV, MAX_IV] bracket until it is tiny.
    """
    if price is None or T <= 0:
        return None
    lo, hi = MIN_IV, MAX_IV
    if not (bs_price(spot, strike, T, rate, lo, q, option_type) < price < bs_price(spot, strike, T, rate, hi, q, option_type)):
        return None
    while hi - lo > 1e-6:
        mid = (lo + hi) / 2
        if bs_price(spot, strike, T, rate, mid, q, option_type) < price:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def infer_forward(mids: Iterable[Tuple[float, str, float]], T: float, rate: float, spot_hint: float,
                  n: int = 5) -> Optional[float]:
    """Forward from put-call parity, F = K + e^{rT} (C - P), median over the n strikes nearest spot_hint.

    `mids` is (strike, 'C'|'P', mid price).
    """
    by_strike: Dict[float, Dict[str, float]] = {}
    for strike, option_type, mid in mids:
        by_strike.setdefault(strike, {})[option_type] = mid
    pairs = sorted((k for k, v in by_strike.items() if "C" in v and "P" in v), key=lambda k: abs(k - spot_hint))[:n]
    if not pairs:
        return None
    growth = math.exp(rate * T)
    return statistics.median(k + growth * (by_strike[k]["C"] - by_strike[k]["P"]) for k in pairs)
