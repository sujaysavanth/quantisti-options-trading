"""The ML-3 experiments: development evaluation, feature ablation, freezing the choice, the one holdout run.

    development  baselines + every model (all feature groups) on the development years, each also with
                 conformal calibration; Diebold-Mariano against scaled VIX and the best baseline
    ablation     forward feature-group selection for one model on the development years
    freeze       record the chosen model, feature groups and calibration with its development scores
    holdout      score the frozen choice on the holdout years, once
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd

from ..dataset import store
from ..dataset.features import CORE_FEATURES
from ..evaluation import periods, report, walkforward
from ..evaluation.baselines import Context, all_baselines, straddle_sigma
from . import ablation, catalog
from .conformal import SUFFIX, conformalize

REFERENCE = "vix_scaled"                   # the simplest calibrated baseline: what a model has to beat
NOT_CALIBRATED = ("vix_raw",)              # kept as published; it is the "market as-is" reference


def training_rows(features: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """Weeks with every core feature and a label: what forecasters are fitted and scored on.
    Option features may be missing (no real chains 2024 .. Sep 2026); models must handle that."""
    return features.dropna(subset=list(CORE_FEATURES)).merge(labels, on="anchor_date")


def load(conn) -> Tuple[pd.DataFrame, Context]:
    features, labels = store.build(conn)
    daily, _, _ = store.load_market(conn)
    data = training_rows(features, labels)
    chains = store.load_anchor_chains(conn, list(zip(data["anchor_date"], data["next_anchor_date"])), moneyness=0.01)
    return data, Context(daily[["date", "close"]], straddle_sigma(chains))


def with_conformal(preds: pd.DataFrame) -> pd.DataFrame:
    calibrate = preds[~preds["forecaster"].isin(NOT_CALIBRATED)]
    return pd.concat([preds, conformalize(calibrate)], ignore_index=True)


def best_baseline(summary: Dict, names: List[str]) -> str:
    """Lowest pinball among baselines scored on every week (the straddle only covers some)."""
    full = max(summary["overall"][n].get("n", 0) for n in names)
    eligible = [n for n in names if summary["overall"][n].get("n") == full]
    return min(eligible, key=lambda n: summary["overall"][n]["pinball"])


def development(data, ctx, log: Callable[[str], None] = print,
                groups: Optional[List[str]] = None, research: bool = False) -> Tuple[pd.DataFrame, Dict]:
    baselines, models = all_baselines(), catalog.all_models(groups)
    if research:
        from .chronos2 import contenders              # needs the optional research install (torch)
        models += contenders()
    log(f"development years {periods.DEV_YEARS.start}-{periods.DEV_YEARS.stop - 1}: "
        f"{len(baselines)} baselines + {len(models)} models on {', '.join(groups or catalog.ALL_GROUPS)}")
    preds = with_conformal(walkforward.run(data, ctx, baselines + models, periods.DEV_YEARS, log=log))
    names = [f.name for f in baselines + models]
    order = names + [n + SUFFIX for n in names if n not in NOT_CALIBRATED]
    summary = report.summarize(preds, order)
    plain_baselines = [b.name for b in baselines if b.name not in NOT_CALIBRATED]
    best = best_baseline(summary, plain_baselines + [n + SUFFIX for n in plain_baselines])
    references = list(dict.fromkeys([REFERENCE, best]))
    summary["best_baseline"] = best
    summary["groups"] = list(groups or catalog.ALL_GROUPS)
    summary["significance"] = report.significance(preds, [n for n in order if n not in references], references)
    return preds, summary


def run_ablation(data, ctx, model: str = "gbm_sigma", log: Callable[[str], None] = print) -> List[Dict]:
    return ablation.forward_selection(
        data, ctx, lambda groups: catalog.build(model, groups),
        candidates=[g for g in catalog.ALL_GROUPS if g != "vix"], years=periods.DEV_YEARS, log=log)


def chosen_forecaster(choice: Dict):
    if choice["model"] == "vix_scaled":              # "no model beats calibrated VIX" is a valid choice too
        from ..evaluation.baselines import VixScaled
        return VixScaled()
    if choice["model"].startswith("chronos2"):
        from .chronos2 import COVARIATES, Chronos2Forecaster
        return Chronos2Forecaster(COVARIATES if choice["model"] == "chronos2_cov" else (), name=choice["model"])
    return catalog.build(choice["model"], choice["groups"])


def fit_for_registry(data, ctx, choice: Dict, dev_preds: pd.DataFrame):
    """The frozen forecaster fitted on every development-period week, plus the conformal adjustments learned from
    its out-of-sample development forecasts: what would have been deployed on the first Friday of the holdout."""
    from .conformal import regime_adjustments
    train, _ = walkforward.split(data, periods.HOLDOUT_FIRST_YEAR)
    forecaster = chosen_forecaster(choice)
    forecaster.fit(train, ctx)
    adjustments = None
    if choice.get("conformal"):
        adjustments = regime_adjustments(dev_preds[dev_preds["forecaster"] == choice["model"]])
    return forecaster, adjustments, train


def chosen_name(choice: Dict) -> str:
    return choice["model"] + (SUFFIX if choice.get("conformal") else "")


def score_choice(data, ctx, choice: Dict, years, reference: Optional[str], log=print) -> Tuple[pd.DataFrame, Dict]:
    """The chosen forecaster next to scaled VIX (and the dev-best baseline), on `years`. Conformal history
    always starts at the first development year, so a holdout year is calibrated on everything before it."""
    baselines = [b for b in all_baselines() if b.name in {REFERENCE, "vix_raw", (reference or "").replace(SUFFIX, "")}]
    first = periods.FIRST_TEST_YEAR
    preds = walkforward.run(data, ctx, [chosen_forecaster(choice)] + baselines, range(first, max(years) + 1), log=log)
    preds = with_conformal(preds)
    preds = preds[preds["year"].isin(list(years))]
    name = chosen_name(choice)
    references = [r for r in dict.fromkeys([REFERENCE, reference]) if r and r != name]
    order = [name] + [b.name for b in baselines] + [r for r in references if r.endswith(SUFFIX)]
    summary = report.summarize(preds, list(dict.fromkeys(order)))
    summary["significance"] = report.significance(preds, [name], references)
    return preds, summary
