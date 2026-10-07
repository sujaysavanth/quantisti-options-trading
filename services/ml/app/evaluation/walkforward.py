"""Walk-forward evaluation: for each test year Y, fit on every week before Y, forecast every week of Y.

This is how a forecaster would actually have been used: refitted once a year on the history available,
then run live for the year. A random train/test split would let weeks from the future inform the fit.

Strictly, a training week's label is the following week's close, so the last training week of Y-1 has a
label in the first week of Y. That is still known before the first forecast of Y is made (at the close
of Y's first anchor), so it isn't leakage; `split` asserts it.
"""

from __future__ import annotations

from typing import Iterable, List, Tuple

import numpy as np
import pandas as pd

from .baselines import Context
from .metrics import QUANTILES

QCOLS = [f"q{int(t * 100):02d}" for t in QUANTILES]
# What happened after the anchor. predict() never receives these columns, so a forecaster can't peek.
LABEL_COLUMNS = ["close_ret", "high_ret", "low_ret", "sessions", "next_anchor_date"]


def split(data: pd.DataFrame, year: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
    years = pd.to_datetime(data["anchor_date"]).dt.year
    train, test = data[years < year], data[years == year]
    if len(train) and len(test):
        assert train["next_anchor_date"].max() <= test["anchor_date"].min(), "training labels reach past the first forecast"
    return train, test


def run(data: pd.DataFrame, ctx: Context, forecasters: Iterable, years: Iterable[int]) -> pd.DataFrame:
    """Long table: one row per (forecaster, test week) with the forecast quantiles and the outcome."""
    frames: List[pd.DataFrame] = []
    for year in years:
        train, test = split(data, year)
        if test.empty:
            continue
        features_only = test.drop(columns=[c for c in LABEL_COLUMNS if c in test.columns])
        for f in forecasters:
            try:
                f.fit(train, ctx)
                q = f.predict(features_only, ctx)
            except ValueError:            # e.g. the straddle baseline with no real chains in the training years
                q = np.full((len(test), len(QCOLS)), np.nan)
            frame = pd.DataFrame(q, columns=QCOLS)
            frame.insert(0, "forecaster", f.name)
            frame.insert(1, "anchor_date", test["anchor_date"].to_numpy())
            frame.insert(2, "year", year)
            frame["close_ret"] = test["close_ret"].to_numpy()
            frame["vix_close"] = test["vix_close"].to_numpy()
            frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["forecaster", *QCOLS])


def forecasts(rows: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    return rows["close_ret"].to_numpy(dtype=float), rows[QCOLS].to_numpy(dtype=float)
