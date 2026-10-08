"""Chronos-2 (Amazon, 2025): a pretrained time-series model, used zero-shot as a contender.

For each test week it is given the weekly return series up to that anchor (ret_1w: the return of the week
that just closed, a feature known at the anchor) and predicts the quantiles of the next weekly return. The
"_cov" variant also sees covariates known at each anchor: VIX, VIX9D/VIX, VIX/VIX3M and 20-day realised vol.
The two together show whether the market data helps it.

It is pretrained, so `fit` only remembers the history; nothing is learned from our labels. Context is built
from feature columns of rows up to and including each anchor, never from a label.

Needs the optional research install (torch, chronos-forecasting): pip install -e ".[research]". The model
(amazon/chronos-2, ~120M parameters) downloads from Hugging Face on first use and runs on CPU.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence

import numpy as np
import pandas as pd

from ..evaluation.metrics import QUANTILES

MODEL_ID = "amazon/chronos-2"
COVARIATES = ("vix_close", "vix9d_ratio", "vix_term", "rv_20d")


@lru_cache(maxsize=1)
def pipeline():
    from chronos import Chronos2Pipeline
    return Chronos2Pipeline.from_pretrained(MODEL_ID, device_map="cpu")


class Chronos2Forecaster:
    def __init__(self, covariates: Sequence[str] = (), name: str = "chronos2"):
        self.covariates, self.name = list(covariates), name

    def fit(self, train: pd.DataFrame, ctx) -> None:
        self.history = train[["anchor_date", "ret_1w", *self.covariates]].copy()

    def inputs(self, test: pd.DataFrame) -> list:
        """One context per test week: every row up to and including its anchor (features only)."""
        rows = pd.concat([self.history, test[["anchor_date", "ret_1w", *self.covariates]]], ignore_index=True)
        rows = rows.drop_duplicates("anchor_date", keep="last").sort_values("anchor_date").reset_index(drop=True)
        position = {a: i for i, a in enumerate(rows["anchor_date"])}
        out = []
        for anchor in test["anchor_date"]:
            upto = rows.iloc[: position[anchor] + 1]
            item = {"target": upto["ret_1w"].to_numpy(dtype=np.float32)}
            if self.covariates:
                item["past_covariates"] = {c: upto[c].to_numpy(dtype=np.float32) for c in self.covariates}
            out.append(item)
        return out

    def predict(self, test: pd.DataFrame, ctx) -> np.ndarray:
        quantiles, _ = pipeline().predict_quantiles(self.inputs(test), prediction_length=1,
                                                    quantile_levels=list(QUANTILES))
        q = np.stack([t[0, 0, :].numpy() for t in quantiles]).astype(float)   # (weeks, quantiles)
        return np.sort(q, axis=1)


def contenders():
    return [Chronos2Forecaster(name="chronos2"), Chronos2Forecaster(COVARIATES, name="chronos2_cov")]
