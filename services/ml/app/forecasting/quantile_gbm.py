"""Direct quantile model: gradient-boosted trees predict each quantile of z = return / VIX sigma.

z says how VIX's implied move should be stretched or shrunk this week (z_90 = 1.1: the 90% quantile sits
1.1 VIX-sigmas up). Learning z instead of the raw return keeps the target on one scale from 2011 to 2026 and
aims straight at the baselines' weakness: one fixed stretch for calm and stressed weeks alike.

Each quantile has its own model (pinball loss), so on some weeks they could cross (q10 above q50); the five
outputs are sorted, which is the standard fix and never makes the loss worse.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from ..evaluation.metrics import QUANTILES
from ..evaluation.targets import vix_sigma
from .sigma_models import DropEmptyColumns


class QuantileGBM:
    def __init__(self, features: Sequence[str], name: str = "gbm_quantile"):
        self.name, self.features = name, list(features)

    def _x(self, rows: pd.DataFrame) -> np.ndarray:
        return rows[self.features].to_numpy(dtype=float)

    def fit(self, train: pd.DataFrame, ctx) -> None:
        from sklearn.ensemble import HistGradientBoostingRegressor
        x = self._x(train)
        z = train["close_ret"].to_numpy(dtype=float) / vix_sigma(train)
        self.models = [
            DropEmptyColumns(HistGradientBoostingRegressor(
                loss="quantile", quantile=t, max_depth=2, learning_rate=0.03, max_iter=200, min_samples_leaf=40,
                l2_regularization=1.0, random_state=0)).fit(x, z)
            for t in QUANTILES
        ]

    def predict(self, test: pd.DataFrame, ctx) -> np.ndarray:
        x = self._x(test)
        z = np.sort(np.column_stack([m.predict(x) for m in self.models]), axis=1)
        return z * vix_sigma(test)[:, None]
