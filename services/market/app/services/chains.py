"""Option chain construction for SPX.

Two sources, both pure functions so they can be tested without a database:

- `build_synthetic_chain`: Black-Scholes prices from the day's close, VIX and
  T-bill rate, with a simple SPX-shaped volatility smile. Used for any date,
  which is what backtests need.
- `build_snapshot_chain`: real listed quotes captured by
  scripts/spx_chain_snapshot.py. Free delayed feeds report implied vols and an
  underlying price that are not consistent with the option quotes, so both are
  ignored: the forward is inferred from put-call parity and IV is recomputed
  from each mid price.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Iterable, List, Optional

from scipy.optimize import brentq

from .. import market_spec
from ..models.options import OptionData, OptionType
from .black_scholes import BlackScholesCalculator
from .greeks import GreeksCalculator

bs = BlackScholesCalculator()
greeks_calc = GreeksCalculator()

VIX_TENOR_YEARS = 30 / 365
MIN_IV, MAX_IV = 0.03, 3.0


# ---------------------------------------------------------------- volatility model

def atm_vol(vix: float, T: float) -> float:
    """At-the-money vol for maturity T from the VIX level (vol points).

    VIX is a 30-day measure; shorter maturities usually trade a little below it
    in calm markets, so apply a mild power-law term structure.
    """
    return max(MIN_IV, vix / 100.0 * (max(T, 1e-6) / VIX_TENOR_YEARS) ** 0.05)


def smile_vol(atm: float, strike: float, forward: float, T: float) -> float:
    """SPX-style skew: higher vol for downside strikes, a little curvature.

    Moneyness is measured in standard deviations so the smile scales sensibly
    from 0DTE to monthly expiries.
    """
    x = math.log(strike / forward) / (atm * math.sqrt(max(T, 1e-6)))
    return min(MAX_IV, max(MIN_IV, atm * (1 - 0.10 * x + 0.02 * x * x)))


# ---------------------------------------------------------------- helpers

def tick(price: float) -> float:
    """SPX minimum increment: 0.05 below $3, 0.10 at or above."""
    step = 0.05 if price < 3 else 0.10
    return round(round(price / step) * step, 2)


def implied_vol(price: float, spot: float, strike: float, T: float, rate: float, q: float, option_type: str) -> Optional[float]:
    """Black-Scholes implied vol from a premium, or None when the premium is outside no-arbitrage bounds."""
    if price is None or T <= 0:
        return None
    pricer = bs.call_price if option_type == "C" else bs.put_price
    lo_price, hi_price = pricer(spot, strike, T, rate, MIN_IV, q), pricer(spot, strike, T, rate, MAX_IV, q)
    if not (lo_price < price < hi_price):
        return None
    return brentq(lambda v: pricer(spot, strike, T, rate, v, q) - price, MIN_IV, MAX_IV, xtol=1e-6)


def _option(strike: float, option_type: str, expiry: date, spot: float, T: float, rate: float, q: float,
            iv: float, price: float, bid: float, ask: float, oi: int, volume: int) -> OptionData:
    intrinsic = bs.intrinsic_value(spot, strike, option_type)
    return OptionData(
        strike=strike,
        option_type=OptionType.CALL if option_type == "C" else OptionType.PUT,
        expiry_date=expiry,
        price=round(price, 2),
        bid=round(bid, 2),
        ask=round(ask, 2),
        greeks=greeks_calc.calculate_greeks(spot, strike, T, rate, iv, option_type, q),
        implied_volatility=round(iv, 4),
        open_interest=oi,
        volume=volume,
        intrinsic_value=round(intrinsic, 2),
        time_value=round(max(price - intrinsic, 0.0), 2),
        in_the_money=intrinsic > 0,
    )


def _summary(spot: float, as_of: date, expiry: date, options: List[OptionData], source: str, atm_iv: float) -> Dict[str, Any]:
    call_oi = sum(o.open_interest or 0 for o in options if o.option_type == OptionType.CALL)
    put_oi = sum(o.open_interest or 0 for o in options if o.option_type == OptionType.PUT)
    return {
        "spot_price": round(spot, 2),
        "date": as_of,
        "expiry_date": expiry,
        "options": options,
        "total_call_oi": call_oi,
        "total_put_oi": put_oi,
        "pcr": round(put_oi / call_oi, 2) if call_oi else None,
        "atm_iv": round(atm_iv, 4),
        "source": source,
    }


# ---------------------------------------------------------------- synthetic

def build_synthetic_chain(spot: float, as_of: date, expiry: date, T: float, rate: float, vix: float,
                          strike_range: int, q: float = market_spec.DIVIDEND_YIELD) -> Dict[str, Any]:
    forward = spot * math.exp((rate - q) * T)
    atm = atm_vol(vix, T)
    centre = market_spec.round_to_strike(spot)
    strikes = [centre + i * market_spec.STRIKE_STEP for i in range(-strike_range, strike_range + 1)]

    options: List[OptionData] = []
    for strike in strikes:
        iv = smile_vol(atm, strike, forward, T)
        # Open interest clusters at round strikes and near the money; puts carry more.
        roundness = 3.0 if strike % 100 == 0 else 1.6 if strike % 25 == 0 else 1.0
        nearness = math.exp(-abs(math.log(strike / spot)) / (atm * math.sqrt(T) + 1e-9) / 2)
        for option_type in ("C", "P"):
            price = (bs.call_price if option_type == "C" else bs.put_price)(spot, strike, T, rate, iv, q)
            half_spread = max(0.05, 0.01 * price) / 2
            oi = int(4000 * roundness * nearness * (1.3 if option_type == "P" else 1.0))
            options.append(_option(strike, option_type, expiry, spot, T, rate, q, iv,
                                   price=price, bid=tick(max(price - half_spread, 0.0)), ask=tick(price + half_spread),
                                   oi=oi, volume=int(oi * 0.4)))
    return _summary(spot, as_of, expiry, options, "synthetic", atm)


# ---------------------------------------------------------------- snapshot

@dataclass
class Quote:
    strike: float
    option_type: str  # 'C' or 'P'
    bid: Optional[float]
    ask: Optional[float]
    last: Optional[float]
    open_interest: Optional[int]
    volume: Optional[int]

    @property
    def mid(self) -> Optional[float]:
        if self.bid and self.ask and self.ask >= self.bid > 0:
            return (self.bid + self.ask) / 2
        return None


# Best first: CBOE (live collection, has open interest), OptionsDX (historical end-of-day files),
# then Yahoo (no reliable OI). Anything else ranks after these, alphabetically.
SNAPSHOT_SOURCE_PRIORITY = ("cboe", "optionsdx", "yahoo")


def preferred_snapshot_source(sources: Iterable[str]) -> Optional[str]:
    """The one source to read a day's snapshot from when several captured it."""
    available = sorted(set(sources))
    if not available:
        return None
    rank = {name: i for i, name in enumerate(SNAPSHOT_SOURCE_PRIORITY)}
    return min(available, key=lambda s: (rank.get(s, len(rank)), s))


def infer_forward(quotes: Iterable[Quote], T: float, rate: float, spot_hint: float, n: int = 5) -> Optional[float]:
    """Forward price from put-call parity, F = K + e^{rT} (C - P), using the n strikes nearest spot_hint."""
    by_strike: Dict[float, Dict[str, float]] = {}
    for qt in quotes:
        if qt.mid is not None:
            by_strike.setdefault(qt.strike, {})[qt.option_type] = qt.mid
    pairs = sorted((k for k, v in by_strike.items() if "C" in v and "P" in v), key=lambda k: abs(k - spot_hint))[:n]
    if not pairs:
        return None
    growth = math.exp(rate * T)
    return statistics.median(k + growth * (by_strike[k]["C"] - by_strike[k]["P"]) for k in pairs)


def build_snapshot_chain(quotes: List[Quote], spot_hint: float, as_of: date, expiry: date, T: float, rate: float,
                         strike_range: int, q: float = market_spec.DIVIDEND_YIELD) -> Optional[Dict[str, Any]]:
    forward = infer_forward(quotes, T, rate, spot_hint)
    if forward is None:
        return None
    spot = forward * math.exp(-(rate - q) * T)  # spot consistent with the option quotes

    strikes = sorted({qt.strike for qt in quotes}, key=lambda k: abs(k - spot))[: 2 * strike_range + 1]
    keep = set(strikes)
    options: List[OptionData] = []
    atm_ivs: List[float] = []
    for qt in sorted(quotes, key=lambda x: (x.strike, x.option_type)):
        if qt.strike not in keep or qt.mid is None:
            continue
        iv = implied_vol(qt.mid, spot, qt.strike, T, rate, q, qt.option_type)
        if iv is None:
            continue
        if abs(qt.strike - spot) <= 2 * market_spec.STRIKE_STEP:
            atm_ivs.append(iv)
        options.append(_option(qt.strike, qt.option_type, expiry, spot, T, rate, q, iv,
                               price=qt.mid, bid=qt.bid, ask=qt.ask,
                               oi=qt.open_interest or 0, volume=qt.volume or 0))
    if not options:
        return None
    atm = statistics.median(atm_ivs) if atm_ivs else statistics.median(o.implied_volatility for o in options)
    return _summary(spot, as_of, expiry, options, "snapshot", atm)
