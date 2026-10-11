"""Conformal calibration: make "80%" mean 80%, in calm and stressed weeks alike.

Runs on walk-forward output (any forecaster). For test year Y, it looks at how that forecaster's bands missed
in the years *before* Y, out of sample, and widens or narrows Y's bands by the amount that would have given
the target coverage then (conformalized quantile regression, Romano et al. 2019). Only past years' outcomes
are used, so the adjustment is something you could have computed on the first Friday of Y.

- Scores are measured in band widths: score = max(lo - y, y - hi) / (hi - lo). Positive = missed by that
  fraction of the band, negative = landed inside. An adjustment of +0.1 widens each side by 10% of the band.
- Separately per VIX regime (calm / normal / stressed, known at the anchor), so a model that is too wide
  when calm and too narrow when stressed is corrected in both directions ("Mondrian" conformal). A regime
  with fewer than MIN_POINTS past weeks falls back to all past weeks; with fewer than that, no adjustment.
- The 80% band (q10, q90) and the 90% band (q05, q95) are calibrated separately; the median is untouched.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ..evaluation.metrics import REGIMES, regime_of
from ..evaluation.walkforward import QCOLS

REGIME_LABELS = [label for label, _, _ in REGIMES]

MIN_POINTS = 30
BANDS = (("q10", "q90", 0.80), ("q05", "q95", 0.90))
MAX_SHRINK = -0.45          # never shrink a band by more than 90% of its width
SUFFIX = "+conformal"


def adjustment(scores: np.ndarray, coverage: float) -> float:
    """Finite-sample conformal quantile of the scores: ceil((n + 1) * coverage) / n."""
    n = len(scores)
    level = min(1.0, math.ceil((n + 1) * coverage) / n)
    return max(float(np.quantile(scores, level, method="higher")), MAX_SHRINK)


def _scores(rows: pd.DataFrame, lo: str, hi: str) -> np.ndarray:
    width = (rows[hi] - rows[lo]).to_numpy()
    y = rows["close_ret"].to_numpy()
    return np.maximum(rows[lo].to_numpy() - y, y - rows[hi].to_numpy()) / width


def regime_adjustments(history: pd.DataFrame, min_points: int = MIN_POINTS) -> dict:
    """Adjustments learned from one forecaster's out-of-sample history, for forecasting the weeks after it:
    {regime: {"q10-q90": adj, "q05-q95": adj}}, plus "all" (pooled) used for a regime with too few weeks."""
    h = history.dropna(subset=QCOLS).copy()
    h["regime"] = regime_of(h["vix_close"].to_numpy(dtype=float))
    out = {}
    for key, rows in [("all", h), *((r, h[h["regime"] == r]) for r in REGIME_LABELS)]:
        if len(rows) >= min_points:
            out[key] = {f"{lo}-{hi}": adjustment(_scores(rows, lo, hi), cov) for lo, hi, cov in BANDS}
    return out


def apply_adjustments(q: np.ndarray, vix: np.ndarray, adjustments: dict) -> np.ndarray:
    """Apply regime_adjustments to quantile forecasts (columns in QCOLS order); returns sorted quantiles."""
    q = q.copy()
    index = {c: i for i, c in enumerate(QCOLS)}
    for row, regime in enumerate(regime_of(np.asarray(vix, dtype=float))):
        adj = adjustments.get(regime) or adjustments.get("all")
        if not adj:
            continue
        for lo, hi, _ in BANDS:
            a, (i, j) = adj[f"{lo}-{hi}"], (index[lo], index[hi])
            width = q[row, j] - q[row, i]
            q[row, i], q[row, j] = q[row, i] - a * width, q[row, j] + a * width
    return np.sort(q, axis=1)


def conformalize(preds: pd.DataFrame, min_points: int = MIN_POINTS) -> pd.DataFrame:
    """For each forecaster in `preds` (walk-forward output), a calibrated copy named '<name>+conformal'."""
    out = []
    for name, g in preds.groupby("forecaster", sort=False):
        if name.endswith(SUFFIX) or g[QCOLS].isna().all().all():
            continue
        g = g.dropna(subset=QCOLS).sort_values("anchor_date", kind="stable").copy()
        g["regime"] = regime_of(g["vix_close"].to_numpy(dtype=float))
        calibrated = g.copy()
        for year in sorted(g["year"].unique()):
            past, now = g[g["year"] < year], g["year"] == year
            for lo, hi, cov in BANDS:
                for regime in g.loc[now, "regime"].unique():
                    own = past[past["regime"] == regime]
                    pool = own if len(own) >= min_points else past
                    if len(pool) < min_points:
                        continue                                       # not enough history yet: leave as is
                    adj = adjustment(_scores(pool, lo, hi), cov)
                    rows = now & (g["regime"] == regime)
                    width = g.loc[rows, hi] - g.loc[rows, lo]
                    calibrated.loc[rows, lo] = g.loc[rows, lo] - adj * width
                    calibrated.loc[rows, hi] = g.loc[rows, hi] + adj * width
        q = np.sort(calibrated[QCOLS].to_numpy(dtype=float), axis=1)         # keep the quantiles in order
        calibrated[QCOLS] = q
        calibrated["forecaster"] = name + SUFFIX
        out.append(calibrated.drop(columns="regime"))
    return pd.concat(out, ignore_index=True) if out else preds.iloc[0:0]
