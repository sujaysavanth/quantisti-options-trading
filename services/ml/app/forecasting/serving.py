"""Serving the weekly range forecast: what is served, how each week's forecast is made, the weekly refresh.

What is served follows the frozen decision in services/ml/model_choice.json. The frozen model (gbm_sigma) did
not beat GARCH on the holdout (+0.3%, p = 0.58), so by the rule set before the holdout:

    garch        role "served"          the forecast the app shows
    <frozen>     role "second_opinion"  same accuracy on average, but far better coverage in stressed weeks
    vix_raw      role "reference"       VIX as published, before calibration (its ranges run ~12% too wide)

A forecast for anchor A is fitted on the weeks whose outcome was known at A's close (next_anchor_date <= A)
and uses features at A. It is stored once (weekly_forecasts) and never recomputed, so later data revisions
can't quietly improve the track record.

    refresh()   after each Friday close: rebuild the dataset, forecast every new anchor, store, log to MLflow
    backfill()  the holdout's walk-forward forecasts (2021 on, refitted yearly), stored as origin "backfill"
                so monitoring has a track record from day one

Each live forecast is stored with its explanation (app/forecasting/explain.py), made from the same fitted
models. explain_missing() adds one to live forecasts stored before explanations existed.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from ..dataset import store
from ..dataset.features import CORE_FEATURES
from ..evaluation import periods, walkforward
from ..evaluation.baselines import Context, Garch, VixRaw
from . import experiments
from .explain import explain

log = logging.getLogger(__name__)

SERVED, REFERENCE = "garch", "vix_raw"


def served_because(choice: Dict) -> str:
    h = (choice or {}).get("holdout") or {}
    sig = ((h.get("significance") or {}).get(choice.get("model", ""), {}) or {}).get(choice.get("reference", ""), {})
    if not sig:
        return "GARCH is served until a frozen model passes its holdout test"
    return (f"the frozen model ({choice['model']}) was {sig['relative'] * 100:+.1f}% vs {choice['reference']} on the "
            f"holdout (p = {sig['p_value']:.2f}); the rule set before the holdout serves {choice['reference']} "
            "unless p < 0.05")


def forecasters(choice: Dict) -> List:
    return [Garch(), experiments.chosen_forecaster(choice), VixRaw()]


def roles(choice: Dict) -> Dict[str, str]:
    return {SERVED: "served", choice["model"]: "second_opinion", REFERENCE: "reference"}


def _details(name: str, choice: Dict) -> str:
    if name == SERVED:
        return served_because(choice)
    if name == choice["model"]:
        return f"{name} on {', '.join(choice['groups'])}, refitted weekly; frozen {choice.get('frozen_at', '?')}"
    return "VIX/100 * sqrt(sessions/252), normal quantiles, no fitting"


def fitted_at(rows: pd.DataFrame, labelled: pd.DataFrame, ctx: Context, anchor, choice: Dict):
    """Every method fitted on the weeks whose outcome was known at `anchor`'s close, with that week's features:
    (forecasters, features row, training weeks)."""
    train = labelled[labelled["next_anchor_date"] <= anchor]
    row = rows[rows["anchor_date"] == anchor]
    if row.empty:
        raise ValueError(f"no complete feature row for {anchor}")
    features = row.drop(columns=[c for c in walkforward.LABEL_COLUMNS if c in row.columns])
    fitted = forecasters(choice)
    for f in fitted:
        f.fit(train, ctx)
    return fitted, features, train


def forecast_anchor(rows: pd.DataFrame, labelled: pd.DataFrame, ctx: Context, anchor, choice: Dict,
                    origin: str = "live") -> pd.DataFrame:
    """Every method's forecast for one anchor, with its explanation. `rows`: feature rows (may include
    unlabelled weeks)."""
    fitted, features, train = fitted_at(rows, labelled, ctx, anchor, choice)
    expiry = store.next_expiries([anchor])[0][1]
    out = []
    for f in fitted:
        q = np.asarray(f.predict(features, ctx), dtype=float)[0]
        out.append({"anchor_date": anchor, "expiry_date": expiry, "method": f.name, "role": roles(choice)[f.name],
                    "origin": origin, "spot": float(ctx_close(ctx, anchor)), "vix_close": float(features["vix_close"].iloc[0]),
                    **dict(zip(walkforward.QCOLS, q)), "trained_through": train["anchor_date"].max(),
                    "details": _details(f.name, choice), "explanation": explain(f, features, ctx, anchor)})
    return pd.DataFrame(out)


def ctx_close(ctx: Context, anchor) -> float:
    return float(ctx.daily.set_index("date").loc[anchor, "close"])


def load_all(conn):
    """(feature rows with every core feature, labelled training rows, context) from the database."""
    features, labels = store.build(conn)
    rows = features.dropna(subset=list(CORE_FEATURES))
    labelled = experiments.training_rows(features, labels)
    daily, _, _ = store.load_market(conn)
    return features, labels, rows, labelled, Context(daily[["date", "close"]])


def refresh(conn, choice: Optional[Dict] = None, log_fn: Callable[[str], None] = log.info) -> Dict:
    """Rebuild the dataset and store a forecast for every complete anchor that doesn't have one yet."""
    from .. import tracking
    choice = choice or periods.load_choice()
    if not choice:
        raise RuntimeError("no frozen choice (services/ml/model_choice.json)")
    features, labels, rows, labelled, ctx = load_all(conn)
    store.save(conn, features, labels)
    store.save_oi_levels(conn, store.build_oi_levels(conn))
    have = store.forecast_anchors(conn)
    anchors = sorted(rows["anchor_date"])
    # Weeks after the newest stored forecast (normally just the Friday that closed; more if the service was down,
    # and those still use only data up to their own anchor). With nothing stored yet: only the latest week.
    todo = [a for a in anchors if a > max(have)] if have else anchors[-1:]
    made = []
    with tracking.run("weekly-forecast", {"anchors": [str(a) for a in todo], "served": SERVED,
                                          "second_opinion": choice["model"]}, labelled) as mlf:
        for anchor in todo:
            fc = forecast_anchor(rows, labelled, ctx, anchor, choice)
            store.save_forecasts(conn, fc)
            made.append(fc)
            served = fc[fc["role"] == "served"].iloc[0]
            log_fn(f"forecast {anchor} -> {served['expiry_date']}: 80% range "
                   f"{served['spot'] * np.exp(served['q10']):,.0f} - {served['spot'] * np.exp(served['q90']):,.0f}")
            if mlf:
                mlf.log_metrics({f"{r['method']}.width_80": float(r["q90"] - r["q10"]) for _, r in fc.iterrows()})
    return {"new_anchors": [str(a) for a in todo], "latest_anchor": str(rows["anchor_date"].max()),
            "weeks": len(features), "labelled_weeks": len(labels)}


def explain_missing(conn, choice: Optional[Dict] = None, log_fn: Callable[[str], None] = print) -> int:
    """Add explanations to live forecasts stored without one. The models are refitted as they were for that
    anchor (same weeks, deterministic fits), and the explanation records whether the refit reproduces the stored
    quantiles, so a mismatch (revised data, say) shows instead of hiding."""
    choice = choice or periods.load_choice()
    stored = store.read_forecasts(conn)
    todo = stored[(stored["origin"] == "live") & stored["explanation"].isna()]
    if todo.empty:
        return 0
    _, _, rows, labelled, ctx = load_all(conn)
    done = 0
    for anchor, g in todo.groupby("anchor_date"):
        fitted, features, _ = fitted_at(rows, labelled, ctx, anchor, choice)
        for f in fitted:
            hit = g[g["method"] == f.name]
            ex = explain(f, features, ctx, anchor) if not hit.empty else None
            if ex is None:
                continue
            q = np.asarray(f.predict(features, ctx), dtype=float)[0]
            ex["added_later"] = True
            ex["matches_stored"] = bool(np.allclose(q, hit[walkforward.QCOLS].to_numpy(dtype=float)[0], rtol=1e-6, atol=1e-9))
            done += store.save_explanation(conn, anchor, f.name, ex)
            log_fn(f"explained {anchor} {f.name} (refit matches the stored forecast: {ex['matches_stored']})")
    return done


def backfill(conn, choice: Optional[Dict] = None, log_fn: Callable[[str], None] = print) -> int:
    """Store the holdout's walk-forward forecasts (yearly refits) for every method, origin 'backfill'."""
    choice = choice or periods.load_choice()
    features, labels, rows, labelled, ctx = load_all(conn)
    last_year = max(a.year for a in labelled["anchor_date"])
    preds = walkforward.run(labelled, ctx, forecasters(choice), periods.holdout_years(last_year), log=log_fn)
    preds = preds.dropna(subset=walkforward.QCOLS)
    years = pd.to_datetime(labelled["anchor_date"]).dt.year
    trained = {y: labelled.loc[years < y, "anchor_date"].max() for y in preds["year"].unique()}
    by_anchor = labelled.set_index("anchor_date")
    closes = ctx.daily.set_index("date")["close"]
    frame = pd.DataFrame({
        "anchor_date": preds["anchor_date"],
        "expiry_date": preds["anchor_date"].map(by_anchor["next_anchor_date"]),
        "method": preds["forecaster"], "role": preds["forecaster"].map(roles(choice)), "origin": "backfill",
        "spot": preds["anchor_date"].map(closes).astype(float), "vix_close": preds["vix_close"],
        **{c: preds[c] for c in walkforward.QCOLS},
        "trained_through": preds["year"].map(trained),
        "details": preds["forecaster"].map(lambda n: _details(n, choice)) + " (backfill: walk-forward, yearly refit)",
    })
    return store.save_forecasts(conn, frame)
