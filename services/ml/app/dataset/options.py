"""Option-market features at each weekly anchor, from the chain for next week's expiry.

Input: quotes from option_chain_snapshots taken on the anchor date for the next anchor's expiry, strikes within
5% of spot (store.load_anchor_chains). One source per anchor, best first: CBOE (live, has open interest),
OptionsDX (2010-2023 end-of-day files), Yahoo. Between 2024 and live collection (Oct 2026) there are no real
chains, so these features are missing there; models must cope with that.

    atm_iv_1w        annualised implied vol of next week's ATM straddle: mid / spot / sqrt(2/pi), scaled to a year
    skew_25d         IV of the 25-delta put minus IV of the 25-delta call (vendor IV and delta): crash-hedge demand
    pc_volume_ratio  put volume / call volume for that expiry: the day's hedging flow

Pure functions; no database access.
"""

from __future__ import annotations

import math
from typing import Dict, Optional

import numpy as np
import pandas as pd

SOURCE_PRIORITY = ("cboe", "optionsdx", "yahoo")
ATM_BAND = 0.01          # the straddle strike must be within 1% of spot
DELTA_TOLERANCE = 0.10   # accept 0.15..0.35 as "25 delta"
MIN_VOLUME = 100         # total contracts below this: too thin for a put/call ratio
OPTION_FEATURE_COLUMNS = ("atm_iv_1w", "skew_25d", "pc_volume_ratio")


def preferred_source(quotes: pd.DataFrame) -> Optional[str]:
    have = set(quotes["source"])
    ranked = [s for s in SOURCE_PRIORITY if s in have] + sorted(have - set(SOURCE_PRIORITY))
    return ranked[0] if ranked else None


def two_sided(quotes: pd.DataFrame) -> pd.DataFrame:
    q = quotes[(quotes["bid"] > 0) & (quotes["ask"] >= quotes["bid"])].copy()
    q["mid"] = (q["bid"] + q["ask"]) / 2
    return q


def straddle_sigma_week(quotes: pd.DataFrame) -> Optional[float]:
    """Weekly sigma implied by the ATM straddle: E|move| = sigma * sqrt(2/pi) for a normal move."""
    q = two_sided(quotes)
    if q.empty:
        return None
    spot = float(q["underlying_price"].iloc[0])
    pairs = q.pivot_table(index="strike", columns="option_type", values="mid", aggfunc="first")
    if not {"C", "P"} <= set(pairs.columns):
        return None
    pairs = pairs.dropna()
    if pairs.empty:
        return None
    k = pairs.index[np.argmin(np.abs(pairs.index.to_numpy() - spot))]
    if abs(k - spot) / spot > ATM_BAND:
        return None
    return float((pairs.loc[k, "C"] + pairs.loc[k, "P"]) / spot / math.sqrt(2 / math.pi))


def skew_25d(quotes: pd.DataFrame) -> Optional[float]:
    q = two_sided(quotes).dropna(subset=["vendor_iv", "vendor_delta"])
    q = q[q["vendor_iv"] > 0]
    put = q[q["option_type"] == "P"].assign(gap=lambda d: (d["vendor_delta"] + 0.25).abs())
    call = q[q["option_type"] == "C"].assign(gap=lambda d: (d["vendor_delta"] - 0.25).abs())
    if put.empty or call.empty:
        return None
    put, call = put.nsmallest(1, "gap").iloc[0], call.nsmallest(1, "gap").iloc[0]
    if put["gap"] > DELTA_TOLERANCE or call["gap"] > DELTA_TOLERANCE:
        return None
    return float(put["vendor_iv"] - call["vendor_iv"])


def pc_volume_ratio(quotes: pd.DataFrame) -> Optional[float]:
    vol = quotes.dropna(subset=["volume"]).groupby("option_type")["volume"].sum()
    calls, puts = float(vol.get("C", 0)), float(vol.get("P", 0))
    if calls <= 0 or calls + puts < MIN_VOLUME:
        return None
    return puts / calls


def anchor_features(quotes: pd.DataFrame, sessions: int) -> Dict[str, Optional[float]]:
    """The three features for one anchor's chain (already one source, one expiry)."""
    sigma = straddle_sigma_week(quotes)
    return {
        "atm_iv_1w": sigma * math.sqrt(252 / sessions) if sigma and sessions else None,
        "skew_25d": skew_25d(quotes),
        "pc_volume_ratio": pc_volume_ratio(quotes),
    }


def option_features(chains: pd.DataFrame, sessions_by_anchor: Dict) -> pd.DataFrame:
    """chains: anchor_date, source, strike, option_type, bid, ask, vendor_iv, vendor_delta, volume, underlying_price.
    Returns one row per anchor that has a usable chain: anchor_date, source, atm_iv_1w, skew_25d, pc_volume_ratio."""
    rows = []
    for anchor, g in chains.groupby("anchor_date"):
        source = preferred_source(g)
        feats = anchor_features(g[g["source"] == source], sessions_by_anchor.get(anchor, 5))
        if any(v is not None for v in feats.values()):
            rows.append({"anchor_date": anchor, "source": source, **feats})
    return pd.DataFrame(rows, columns=["anchor_date", "source", *OPTION_FEATURE_COLUMNS])
