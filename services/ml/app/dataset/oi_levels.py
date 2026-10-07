"""Open-interest levels for next week's expiry: recorded every week, not yet a model feature.

OptionsDX has no open interest, and only CBOE's live collection (from October 2026) does, so there is no
history to train on. These are stored in weekly_oi_levels from now on; once about a year has accumulated
they can be tested as features in the walk-forward harness.

    put_wall   strike at or below spot with the most put open interest (often read as support)
    call_wall  strike at or above spot with the most call open interest (often read as resistance)
    max_pain   settlement price at which option holders' total payout would be smallest
    gex        naive dealer gamma exposure, $ per 1% move: sum of gamma * OI * 100 * spot^2 * 1%, calls positive and
               puts negative (assumes dealers are long the calls and short the puts customers trade; a common
               convention, not a measurement of real dealer positions)

Only the strikes in the collected chain count (CBOE collection keeps strikes within 5% of spot), so walls further
out are not seen.
"""

from __future__ import annotations

import math
from typing import Dict, Optional

import numpy as np
import pandas as pd


def _gamma(spot: float, strike: np.ndarray, t: float, rate: float, iv: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        d1 = (np.log(spot / strike) + (rate + iv ** 2 / 2) * t) / (iv * math.sqrt(t))
        g = np.exp(-d1 ** 2 / 2) / math.sqrt(2 * math.pi) / (spot * iv * math.sqrt(t))
    return np.nan_to_num(g)


def oi_levels(quotes: pd.DataFrame, years_to_expiry: float, rate: float = 0.04) -> Optional[Dict]:
    """quotes: strike, option_type, open_interest, vendor_iv, underlying_price for one expiry, one source."""
    q = quotes.dropna(subset=["open_interest"])
    q = q[q["open_interest"] > 0]
    if q.empty or not {"C", "P"} <= set(q["option_type"]):
        return None
    spot = float(q["underlying_price"].iloc[0])
    calls, puts = q[q["option_type"] == "C"], q[q["option_type"] == "P"]
    below, above = puts[puts["strike"] <= spot], calls[calls["strike"] >= spot]

    strikes = np.sort(q["strike"].unique())
    k_c, oi_c = calls["strike"].to_numpy(), calls["open_interest"].to_numpy(dtype=float)
    k_p, oi_p = puts["strike"].to_numpy(), puts["open_interest"].to_numpy(dtype=float)
    payout = [(np.clip(s - k_c, 0, None) * oi_c).sum() + (np.clip(k_p - s, 0, None) * oi_p).sum() for s in strikes]

    with_iv = q.dropna(subset=["vendor_iv"])
    with_iv = with_iv[with_iv["vendor_iv"] > 0]
    gex = None
    if not with_iv.empty and years_to_expiry > 0:
        g = _gamma(spot, with_iv["strike"].to_numpy(dtype=float), years_to_expiry, rate,
                   with_iv["vendor_iv"].to_numpy(dtype=float))
        sign = np.where(with_iv["option_type"].to_numpy() == "C", 1.0, -1.0)
        gex = float((sign * g * with_iv["open_interest"].to_numpy(dtype=float) * 100 * spot ** 2 * 0.01).sum())

    return {
        "spot": spot,
        "put_wall": float(below.loc[below["open_interest"].idxmax(), "strike"]) if not below.empty else None,
        "call_wall": float(above.loc[above["open_interest"].idxmax(), "strike"]) if not above.empty else None,
        "max_pain": float(strikes[int(np.argmin(payout))]),
        "gex": gex,
        "contracts": int(q["open_interest"].sum()),
    }
