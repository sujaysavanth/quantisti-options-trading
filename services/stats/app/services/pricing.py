"""Black-Scholes-Merton price and Greeks with a continuous dividend yield, without scipy.

Price and delta are the same maths as the stream bridge (services/ingest/app/bridge/pricing.py), which computes the
IVs this service uses, so delta here equals the delta on the live quote for the same inputs. option_type is
'CALL' or 'PUT'. Greeks are per unit of the index (one contract is x100):
    delta  dPrice / dSpot
    gamma  dDelta / dSpot
    vega   dPrice per 1 volatility point (0.01)
    theta  dPrice per calendar day (time passing, everything else fixed)
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def _cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _pdf(x: float) -> float:
    return math.exp(-x * x / 2) / math.sqrt(2 * math.pi)


def intrinsic(option_type: str, strike: float, spot: float) -> float:
    return max(spot - strike, 0.0) if option_type == "CALL" else max(strike - spot, 0.0)


def bs_price(spot: float, strike: float, T: float, rate: float, vol: float, q: float, option_type: str) -> float:
    if T <= 0 or vol <= 0:
        return intrinsic(option_type, strike, spot)
    sd = vol * math.sqrt(T)
    d1 = (math.log(spot / strike) + (rate - q + 0.5 * vol * vol) * T) / sd
    d2 = d1 - sd
    disc_s, disc_k = spot * math.exp(-q * T), strike * math.exp(-rate * T)
    if option_type == "CALL":
        return disc_s * _cdf(d1) - disc_k * _cdf(d2)
    return disc_k * _cdf(-d2) - disc_s * _cdf(-d1)


@dataclass(frozen=True)
class Greeks:
    price: float
    delta: float
    gamma: float
    vega: float
    theta: float


def greeks(spot: float, strike: float, T: float, rate: float, vol: float, q: float, option_type: str) -> Greeks:
    if T <= 0 or vol <= 0:
        itm = spot > strike if option_type == "CALL" else spot < strike
        delta = (1.0 if option_type == "CALL" else -1.0) if itm else 0.0
        return Greeks(intrinsic(option_type, strike, spot), delta, 0.0, 0.0, 0.0)
    sqrt_t = math.sqrt(T)
    d1 = (math.log(spot / strike) + (rate - q + 0.5 * vol * vol) * T) / (vol * sqrt_t)
    d2 = d1 - vol * sqrt_t
    carry, disc = math.exp(-q * T), math.exp(-rate * T)
    decay = -spot * carry * _pdf(d1) * vol / (2 * sqrt_t)
    if option_type == "CALL":
        delta = carry * _cdf(d1)
        theta = decay - rate * strike * disc * _cdf(d2) + q * spot * carry * _cdf(d1)
    else:
        delta = carry * (_cdf(d1) - 1)
        theta = decay + rate * strike * disc * _cdf(-d2) - q * spot * carry * _cdf(-d1)
    return Greeks(
        price=bs_price(spot, strike, T, rate, vol, q, option_type),
        delta=delta,
        gamma=carry * _pdf(d1) / (spot * vol * sqrt_t),
        vega=spot * carry * _pdf(d1) * sqrt_t / 100,
        theta=theta / 365,
    )
