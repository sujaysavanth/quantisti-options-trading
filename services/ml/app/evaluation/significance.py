"""Is one forecaster really better than another, or just lucky over this sample?

Diebold-Mariano test (Diebold & Mariano, 1995) on the weekly pinball losses of two forecasters scored on the
same weeks. d_t = loss_A - loss_B; if A is no better, the mean of d is zero. Neighbouring weeks' losses are
related (volatile periods cluster), so the variance of the mean uses Newey-West weights over `lags` weeks
instead of treating weeks as independent.

The p-value is one-sided: the probability of seeing A this much better (or more) if it really isn't.
Below 0.05 is the usual bar; with ~300-400 weeks, small improvements rarely clear it.
"""

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Dict

import numpy as np


def newey_west_variance(d: np.ndarray, lags: int) -> float:
    d = d - d.mean()
    n = len(d)
    var = float(d @ d) / n
    for k in range(1, min(lags, n - 1) + 1):
        weight = 1 - k / (lags + 1)
        var += 2 * weight * float(d[k:] @ d[:-k]) / n
    return max(var, 1e-18)


def diebold_mariano(loss_a: np.ndarray, loss_b: np.ndarray, lags: int = 4) -> Dict[str, float]:
    """One-sided test that A has lower loss than B. Rows where either is missing are dropped."""
    ok = ~(np.isnan(loss_a) | np.isnan(loss_b))
    d = loss_a[ok] - loss_b[ok]
    n = len(d)
    if n < 20:
        return {"n": n, "mean_diff": float("nan"), "relative": float("nan"), "stat": float("nan"), "p_value": float("nan")}
    mean = float(d.mean())
    stat = mean / math.sqrt(newey_west_variance(d, lags) / n)
    return {
        "n": n,
        "mean_diff": mean,                                     # negative: A better
        "relative": mean / float(loss_b[ok].mean()),           # e.g. -0.03 = 3% lower loss than B
        "stat": stat,
        "p_value": NormalDist().cdf(stat),                     # small when A is clearly better
    }
