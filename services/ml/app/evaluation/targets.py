"""What models are trained to predict, built from training rows only.

- next_week_variance: mean squared daily log return over next week's sessions. Less noisy than the single
  weekly return, so volatility models learn from it; it uses labels (next_anchor_date), so training rows only.
- vix_sigma: the weekly sigma VIX implies, known at the anchor. Quantile models predict the return in
  units of it (z = return / vix_sigma), i.e. how much to stretch or shrink VIX's range.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def next_week_variance(rows: pd.DataFrame, ctx) -> np.ndarray:
    start = ctx.index_of(rows["anchor_date"]) + 1
    end = ctx.index_of(rows["next_anchor_date"]) + 1
    return np.array([ctx.r2_day[s:e].mean() for s, e in zip(start, end)])


def vix_sigma(rows: pd.DataFrame) -> np.ndarray:
    return rows["vix_close"].to_numpy(dtype=float) / 100 * np.sqrt(rows["sessions_next"].to_numpy(dtype=float) / TRADING_DAYS)
