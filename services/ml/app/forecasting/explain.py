"""Why is this week's range as wide as it is? One explanation per forecast, of the kind that is exact for it.

Every method here forecasts a weekly volatility sigma and turns it into quantiles as q = sigma * z (z learned
on the training weeks), so explaining the range means explaining sigma.

garch (served): no features, so SHAP has nothing to attribute. Its forecast splits exactly instead. With
    p = alpha + beta, long-run daily variance LR = omega / (1 - p), and n sessions to expiry,

        week variance = n * LR  +  k * alpha * (e^2 - LR)  +  k * beta * (h0 - LR),    k = (1 - p^n) / (1 - p)

    long run: the level volatility returns to; last move: the anchor day's return e (its surprise against the
    long-run level); carried over: how far the previous day's variance h0 sat from the long-run level, decaying
    at rate p. A shock's effect halves every ln 0.5 / ln p sessions.

gbm_sigma (second opinion): TreeSHAP (Lundberg et al. 2020; exact for trees, missing values included) on the
    model, which predicts log next-week daily variance. Contributions add up to the prediction, so each one is
    an exact multiplier on sigma: exp(phi / 2). Features measuring the same thing (VIX, VIX9D, VIX3M) share
    credit somewhat arbitrarily between them, so contributions are also summed per feature group, which is the
    stable view. SHAP explains the model, not the market.

vix_raw (reference): the formula, sigma = VIX / 100 * sqrt(sessions / 252).
"""

from __future__ import annotations

import math
from typing import Dict, Optional

import numpy as np
import pandas as pd

from ..dataset.features import FEATURE_GROUPS
from ..evaluation.baselines import TRADING_DAYS, Garch, VixRaw, VixScaled
from .sigma_models import DropEmptyColumns, SigmaModel

GROUP_OF = {f: g for g, cols in FEATURE_GROUPS.items() for f in cols}


def _f(x) -> Optional[float]:
    return None if x is None or not np.isfinite(x) else float(x)


def garch_breakdown(model: Garch, ctx, anchor, sessions: float) -> Dict:
    i = int(ctx.index_of([anchor])[0])
    n = float(sessions)
    p = model.alpha + model.beta_
    e = float(np.nan_to_num(ctx.returns[i] * 100 - model.mu))           # the anchor day's surprise, in percent
    h0, h1 = float(model.h_next[i - 1]), float(model.h_next[i])         # daily variance before / after that day
    out = {
        "kind": "garch", "sessions": n,
        "params": {"omega": model.omega, "alpha": model.alpha, "beta": model.beta_, "mu": model.mu},
        "persistence": p, "last_move_pct": e,
        "daily_vol_now_annual": math.sqrt(h1 * TRADING_DAYS) / 100,
    }
    if p >= 0.9999:                                                     # no long-run level: variance just persists
        var = {"long_run": 0.0, "last_move": n * model.alpha * e * e, "carried_over": n * (model.omega + model.beta_ * h0)}
        out.update(half_life_sessions=None, daily_vol_long_run_annual=None)
    else:
        lr = model.omega / (1 - p)
        k = (1 - p ** n) / (1 - p)
        var = {"long_run": n * lr, "last_move": k * model.alpha * (e * e - lr), "carried_over": k * model.beta_ * (h0 - lr)}
        out.update(half_life_sessions=math.log(0.5) / math.log(p) if 0 < p < 1 else None,
                   daily_vol_long_run_annual=math.sqrt(lr * TRADING_DAYS) / 100)
    total = sum(var.values())
    sigma = math.sqrt(max(total, 1e-12)) / 100
    sigma_lr = math.sqrt(max(var["long_run"], 0.0)) / 100
    # The parts add up in variance. For display in volatility, the gap between sigma and the long-run sigma is
    # shared between the two short-run parts in proportion to their variance.
    short = var["last_move"] + var["carried_over"]
    gap = sigma - sigma_lr
    share = {k_: (gap * var[k_] / short if abs(short) > 1e-15 else 0.0) for k_ in ("last_move", "carried_over")}
    out.update(variance={k_: v / 1e4 for k_, v in var.items()}, sigma=sigma, sigma_long_run=sigma_lr,
               sigma_parts={"long_run": sigma_lr, **share})
    return out


def tree_contributions(model: SigmaModel, row: pd.DataFrame) -> Dict:
    """TreeSHAP for a SigmaModel whose estimator is a tree ensemble (gbm_sigma)."""
    import shap
    wrapped = model.model
    est, keep = (wrapped.estimator, wrapped.keep) if isinstance(wrapped, DropEmptyColumns) else (wrapped, None)
    x = model._x(row)
    used = np.ones(x.shape[1], bool) if keep is None else keep
    explainer = shap.TreeExplainer(est)
    phi_used = np.asarray(explainer.shap_values(x[:, used]), dtype=float)[0]
    base = float(np.ravel(explainer.expected_value)[0])
    phi = np.zeros(x.shape[1])
    phi[used] = phi_used
    log_var = float(np.asarray(model.model.predict(x))[0])
    n = float(row["sessions_next"].iloc[0])
    features = sorted(
        ({"name": f, "group": GROUP_OF.get(f, "other"), "value": _f(x[0, j]), "used": bool(used[j]),
          "contribution": float(phi[j]), "multiplier": math.exp(phi[j] / 2)} for j, f in enumerate(model.features)),
        key=lambda d: -abs(d["contribution"]))
    groups: Dict[str, float] = {}
    for d in features:
        groups[d["group"]] = groups.get(d["group"], 0.0) + d["contribution"]
    return {
        "kind": "tree_shap", "target": "log of next week's average daily variance", "sessions": n,
        "base_log_variance": base, "log_variance": log_var,
        "sigma_base": math.sqrt(math.exp(base) * n), "sigma": math.sqrt(math.exp(log_var) * n),
        "additivity_error": abs(base + float(phi.sum()) - log_var),
        "features": features,
        "groups": sorted(({"group": g, "contribution": c, "multiplier": math.exp(c / 2)} for g, c in groups.items()),
                         key=lambda d: -abs(d["contribution"])),
    }


def vix_formula(row: pd.DataFrame) -> Dict:
    vix, n = float(row["vix_close"].iloc[0]), float(row["sessions_next"].iloc[0])
    return {"kind": "vix", "vix": vix, "sessions": n, "sigma": vix / 100 * math.sqrt(n / TRADING_DAYS)}


def explain(forecaster, row: pd.DataFrame, ctx, anchor) -> Optional[Dict]:
    """The explanation for a fitted forecaster's forecast at `anchor` (row: that week's features), with the z
    that turns its sigma into quantiles. None for a forecaster with no explanation here."""
    if isinstance(forecaster, Garch):
        out = garch_breakdown(forecaster, ctx, anchor, float(row["sessions_next"].iloc[0]))
    elif isinstance(forecaster, SigmaModel) and _is_tree(forecaster):
        out = tree_contributions(forecaster, row)
    elif isinstance(forecaster, (VixRaw, VixScaled)):
        out = vix_formula(row)
    else:
        return None
    out["z"] = [float(v) for v in forecaster.z]
    return out


def _is_tree(model: SigmaModel) -> bool:
    from sklearn.ensemble import HistGradientBoostingRegressor
    m = getattr(model, "model", None)
    return isinstance(m.estimator if isinstance(m, DropEmptyColumns) else m, HistGradientBoostingRegressor)
