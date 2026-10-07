"""Scoring for quantile forecasts of next week's close return.

Forecasts are arrays of shape (n_weeks, len(QUANTILES)) in log-return units, one column per quantile.

- pinball loss: the proper scoring rule for quantiles. For each quantile tau, a miss above costs tau per
  unit and a miss below costs (1 - tau): the 90% quantile is punished mostly for being too low. Averaged
  over quantiles and weeks; lower is better. It rewards calibration and sharpness together.
- coverage: how often the close landed inside the 80% (q10..q90) or 90% (q05..q95) band. Should be 0.80
  and 0.90; above means too wide (wasted premium for a condor seller), below means too narrow.
- width: average size of the 80% band. Only comparable between forecasts with similar coverage.
- Winkler interval score: width plus a penalty of 2/alpha times the distance by which the close missed the
  band (alpha = 0.2 for 80%). One number that trades off narrow bands against misses; lower is better.
"""

from __future__ import annotations

from typing import Dict

import numpy as np

QUANTILES = (0.05, 0.10, 0.50, 0.90, 0.95)
I05, I10, I50, I90, I95 = range(5)


def pinball(y: np.ndarray, q: np.ndarray, taus=QUANTILES) -> float:
    diff = y[:, None] - q
    taus = np.asarray(taus)[None, :]
    return float(np.mean(np.maximum(taus * diff, (taus - 1) * diff)))


def coverage(y: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> float:
    return float(np.mean((y >= lo) & (y <= hi)))


def winkler(y: np.ndarray, lo: np.ndarray, hi: np.ndarray, alpha: float) -> float:
    penalty = (2 / alpha) * (np.clip(lo - y, 0, None) + np.clip(y - hi, 0, None))
    return float(np.mean(hi - lo + penalty))


def score(y: np.ndarray, q: np.ndarray) -> Dict[str, float]:
    """All metrics for one forecaster over the given weeks. Rows with any NaN forecast are dropped."""
    ok = ~np.isnan(q).any(axis=1)
    y, q = y[ok], q[ok]
    if not len(y):
        return {"n": 0}
    return {
        "n": int(len(y)),
        "coverage_80": coverage(y, q[:, I10], q[:, I90]),
        "coverage_90": coverage(y, q[:, I05], q[:, I95]),
        "width_80": float(np.mean(q[:, I90] - q[:, I10])),
        "pinball": pinball(y, q),
        "winkler_80": winkler(y, q[:, I10], q[:, I90], alpha=0.2),
    }
