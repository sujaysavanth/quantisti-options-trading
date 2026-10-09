"""Is the forecast still calibrated? Checks stored forecasts against what happened.

For each method, over the last 26 and 52 weeks with a known outcome: how often next week's close landed inside
the 80% band (q10..q90) and the 90% band (q05..q95), the average band width, the pinball loss, and 80% coverage
by VIX regime.

Drift flag: if the band really covers 80%, the number of weeks inside it over n weeks follows a binomial
distribution. An exact two-sided binomial test asks how surprising the observed count would be; below
ALERT_P the flag is raised. (With 26 weeks, roughly fewer than 16 or more than 25 hits.) A flag means
"look into it": refit, recalibrate, or check the data, not "the model is broken".
"""

from __future__ import annotations

from math import comb
from typing import Dict

import numpy as np
import pandas as pd

from ..evaluation.metrics import pinball, regime_of
from ..evaluation.walkforward import QCOLS

WINDOWS = (26, 52)
ALERT_P = 0.05


def binomial_p(hits: int, n: int, p: float) -> float:
    """Exact two-sided binomial test: probability of an outcome at most as likely as `hits`."""
    probs = [comb(n, k) * p ** k * (1 - p) ** (n - k) for k in range(n + 1)]
    return float(min(1.0, sum(x for x in probs if x <= probs[hits] * (1 + 1e-9))))


def window_stats(g: pd.DataFrame) -> Dict:
    y = g["close_ret"].to_numpy(dtype=float)
    q = g[QCOLS].to_numpy(dtype=float)
    in80 = (y >= q[:, 1]) & (y <= q[:, 3])
    in90 = (y >= q[:, 0]) & (y <= q[:, 4])
    n = len(y)
    p80 = binomial_p(int(in80.sum()), n, 0.80)
    regimes = regime_of(g["vix_close"].to_numpy(dtype=float))
    return {
        "weeks": n, "from": str(g["anchor_date"].min()), "to": str(g["anchor_date"].max()),
        "coverage_80": float(in80.mean()), "coverage_90": float(in90.mean()),
        "width_80": float(np.mean(q[:, 3] - q[:, 1])), "pinball": pinball(y, q),
        "drift_p_value": p80, "drift": bool(p80 < ALERT_P),
        "coverage_80_by_regime": {r: {"weeks": int((regimes == r).sum()), "coverage_80": float(in80[regimes == r].mean())}
                                  for r in pd.unique(regimes)},
    }


HORIZON_WINDOWS = (60, 250)


def monitor_horizons(forecasts: pd.DataFrame) -> Dict:
    """expiry_forecasts with outcomes: the same checks per horizon (sessions to expiry), over the last 60 and
    250 forecasts. Consecutive daily forecasts overlap (the same days' moves), so a drift flag here is a prompt
    to look, more than a test result."""
    scored = (forecasts.dropna(subset=["close_ret"])
              .rename(columns={"origin_date": "anchor_date"}).sort_values("anchor_date"))
    out = {}
    for h, g in scored.groupby("sessions"):
        if len(g) >= 20:
            out[str(int(h))] = {f"last_{w}": window_stats(g.tail(w)) for w in HORIZON_WINDOWS}
    return out


def monitor(forecasts: pd.DataFrame) -> Dict:
    """forecasts: store.read_forecasts output. One entry per method, per window."""
    scored = forecasts.dropna(subset=["close_ret"]).sort_values("anchor_date")
    out = {"methods": {}, "pending": int(forecasts["close_ret"].isna().sum() // max(forecasts["method"].nunique(), 1))}
    for method, g in scored.groupby("method"):
        out["methods"][method] = {
            "role": g["role"].iloc[-1],
            "windows": {f"last_{w}_weeks": window_stats(g.tail(w)) for w in WINDOWS if len(g) >= 10},
            "live_weeks": int((g["origin"] == "live").sum()),
        }
    out["alerts"] = [f"{m}: last {w.split('_')[1]} weeks' 80% band covered {s['coverage_80']:.0%} (p = {s['drift_p_value']:.3f})"
                     for m, v in out["methods"].items() for w, s in v["windows"].items() if s["drift"]]
    return out
