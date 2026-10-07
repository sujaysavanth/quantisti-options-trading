"""Volatility models: learn next week's volatility from the features, then map it to quantiles exactly as the
baselines do (q = sigma * z_q, z_q from the training weeks), so the comparison is like for like.

Target: log of next week's realised variance (mean squared daily return). The log keeps 2020-sized weeks from
dominating the fit; the empirical z mapping absorbs the bias of exponentiating a log forecast.

One trap: a flexible model's sigma on its own training weeks is overconfident (it has partly memorised
them), so z quantiles learned from it come out too narrow and the bands under-cover out of sample. The z
mapping is therefore learned from out-of-fold sigmas: training weeks split into contiguous blocks, each
predicted by a model fitted on the others.

    ridge_sigma  linear, standardised features; missing option features median-filled plus a "was missing" flag
    gbm_sigma    gradient-boosted trees (shallow, regularised); handles missing values natively
    ebm_sigma    explainable boosting machine: additive, one plottable curve per feature; handles missing values
"""

from __future__ import annotations

import warnings
from typing import Callable, Sequence

import numpy as np
import pandas as pd
from sklearn.model_selection import KFold

from ..evaluation.baselines import SigmaBaseline, week_sigma
from ..evaluation.metrics import QUANTILES
from ..evaluation.targets import next_week_variance

N_FOLDS = 5


class DropEmptyColumns:
    """Wraps an estimator: columns with no values at all in the training data are dropped (and the same ones at
    prediction). scikit-learn's gradient boosting fails on an all-missing column, which happens when a training
    window has no option chains (2024 to Sep 2026) for the option features."""

    def __init__(self, estimator):
        self.estimator = estimator

    def fit(self, x, y):
        self.keep = ~np.isnan(x).all(axis=0)
        self.estimator.fit(x[:, self.keep], y)
        return self

    def predict(self, x):
        return self.estimator.predict(x[:, self.keep])


def ridge():
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler(), Ridge(alpha=10.0))


def gbm():
    from sklearn.ensemble import HistGradientBoostingRegressor
    return DropEmptyColumns(HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=200,
                                                          min_samples_leaf=30, l2_regularization=1.0, random_state=0))


def ebm():
    from interpret.glassbox import ExplainableBoostingRegressor
    return DropEmptyColumns(ExplainableBoostingRegressor(interactions=0, outer_bags=4, random_state=0))


class SigmaModel(SigmaBaseline):
    def __init__(self, name: str, make: Callable, features: Sequence[str]):
        self.name, self.make, self.features = name, make, list(features)

    def _x(self, rows: pd.DataFrame) -> np.ndarray:
        return rows[self.features].to_numpy(dtype=float)

    def _fit(self, x, y):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)      # EBM: "missing values detected" (plots only)
            return self.make().fit(x, y)

    def fit(self, train: pd.DataFrame, ctx) -> None:
        x = self._x(train)
        y = np.log(np.clip(next_week_variance(train, ctx), 1e-10, None))
        sessions = train["sessions_next"].to_numpy(dtype=float)
        oof = np.empty(len(y))
        for fit_idx, out_idx in KFold(N_FOLDS).split(x):         # contiguous blocks, no shuffling
            oof[out_idx] = self._fit(x[fit_idx], y[fit_idx]).predict(x[out_idx])
        sigma_oof = week_sigma(np.exp(oof), sessions)
        self.z = np.quantile(train["close_ret"].to_numpy(dtype=float) / sigma_oof, QUANTILES)
        self.model = self._fit(x, y)

    def sigma(self, rows: pd.DataFrame, ctx) -> np.ndarray:
        return week_sigma(np.exp(self.model.predict(self._x(rows))), rows["sessions_next"].to_numpy(dtype=float))
