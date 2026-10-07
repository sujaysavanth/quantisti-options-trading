from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.evaluation import periods, walkforward
from app.evaluation.baselines import NORMAL_Z, Context
from app.evaluation.metrics import coverage, regime_of
from app.evaluation.significance import diebold_mariano
from app.forecasting import ablation, catalog
from app.forecasting.conformal import SUFFIX, conformalize
from tests.test_evaluation import synthetic_rows

QCOLS = walkforward.QCOLS


# ---------------------------------------------------------------- significance

def test_dm_no_difference_and_a_clear_winner():
    rng = np.random.default_rng(0)
    base = rng.gamma(2, 0.002, 400)
    same = diebold_mariano(base, base.copy())
    assert same["mean_diff"] == 0 and same["p_value"] == pytest.approx(0.5)
    better = diebold_mariano(base * 0.9, base)
    assert better["relative"] == pytest.approx(-0.1) and better["p_value"] < 0.001
    noisy = diebold_mariano(base * (1 + rng.normal(0, 0.5, 400)), base)
    assert noisy["p_value"] > 0.05
    assert np.isnan(diebold_mariano(base[:10], base[:10])["p_value"])       # too few weeks to say anything


# ---------------------------------------------------------------- conformal

def miscalibrated_preds(seed=1, per_week=8):
    """One forecaster over 2014-2020 whose bands are too wide when calm and too narrow when stressed.
    Several rows per week keep the sample big enough to judge coverage to a few percent."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(7 * 52 * per_week):
        day = date(2014, 1, 3) + timedelta(weeks=i // per_week)
        vix = rng.choice([12.0, 20.0, 35.0])
        sigma = vix / 100 / np.sqrt(52)
        y = sigma * rng.standard_normal()
        stretch = {12.0: 1.4, 20.0: 1.0, 35.0: 0.6}[vix]                     # the baseline weakness, exaggerated
        q = sigma * stretch * NORMAL_Z
        rows.append({"forecaster": "x", "anchor_date": day, "year": day.year, **dict(zip(QCOLS, q)),
                     "close_ret": y, "vix_close": vix})
    return pd.DataFrame(rows)


def coverage_by_regime(df):
    out = {}
    for regime, g in df.groupby(regime_of(df["vix_close"].to_numpy())):
        out[regime] = coverage(g["close_ret"].to_numpy(), g["q10"].to_numpy(), g["q90"].to_numpy())
    return out


def test_conformal_fixes_coverage_per_regime():
    preds = miscalibrated_preds()
    late = lambda df: df[df["year"] >= 2017]                                  # noqa: E731 (enough history by then)
    before = coverage_by_regime(late(preds))
    after = coverage_by_regime(late(conformalize(preds)))
    assert before["calm (VIX < 15)"] > 0.9 and before["stressed (VIX >= 25)"] < 0.6
    for regime, cov in after.items():
        assert cov == pytest.approx(0.80, abs=0.04), regime                 # conformal is slightly conservative


def test_conformal_uses_only_earlier_years():
    preds = miscalibrated_preds()
    changed = preds.copy()
    changed.loc[changed["year"] == 2020, "close_ret"] *= 5                    # wild outcomes in the last year
    a, b = conformalize(preds), conformalize(changed)
    upto_2020 = lambda df: df[df["year"] <= 2020][QCOLS].to_numpy()          # noqa: E731
    np.testing.assert_allclose(upto_2020(a), upto_2020(b))                    # 2020's own bands can't see 2020
    assert (a["forecaster"] == "x" + SUFFIX).all()


def test_conformal_leaves_the_first_year_alone_and_keeps_order():
    preds = miscalibrated_preds()
    out = conformalize(preds)
    first = lambda df: df[df["year"] == 2014][QCOLS].to_numpy()               # noqa: E731 (no history yet)
    np.testing.assert_allclose(first(out), first(preds))
    assert (np.diff(out[QCOLS].to_numpy(), axis=1) >= 0).all()


# ---------------------------------------------------------------- models

@pytest.mark.parametrize("name", ["ridge_sigma", "gbm_sigma", "ebm_sigma", "gbm_quantile"])
def test_models_fit_and_forecast_with_missing_option_features(name):
    daily, data = synthetic_rows()                                            # option features are all NaN here
    ctx = Context(daily[["date", "close"]])
    train, test = walkforward.split(data, 2024)
    model = catalog.build(name)
    model.fit(train, ctx)
    q = model.predict(test.drop(columns=walkforward.LABEL_COLUMNS), ctx)
    assert q.shape == (len(test), 5) and np.isfinite(q).all()
    assert (np.diff(q, axis=1) >= 0).all()                                    # quantiles in order
    cov = coverage(test["close_ret"].to_numpy(), q[:, 1], q[:, 3])
    assert 0.6 < cov < 0.97, (name, cov)


def test_sigma_model_learns_its_z_mapping_out_of_fold():
    daily, data = synthetic_rows()
    model = catalog.build("gbm_sigma")
    model.fit(walkforward.split(data, 2024)[0], Context(daily[["date", "close"]]))
    assert model.z[3] - model.z[1] > 2.0                                     # an 80% band of ~2.56 sigma, not shrunk


def test_unknown_groups_are_rejected():
    with pytest.raises(ValueError):
        catalog.features_for(["vix", "astrology"])
    assert catalog.features_for(["vix"]) == ["vix_close", "vix_change_1w", "vix_hv_spread", "vix_pct_1y"]


# ---------------------------------------------------------------- ablation

class Stub:
    """Knows the true sigma only if the 'good' group is in its feature set."""

    def __init__(self, groups):
        self.name, self.good = "stub", "good" in groups

    def fit(self, train, ctx):
        pass

    def predict(self, test, ctx):
        sigma = test["true_sigma"].to_numpy() if self.good else np.full(len(test), 0.025)
        return sigma[:, None] * NORMAL_Z[None, :]


def test_forward_selection_keeps_what_helps_and_stops():
    rng = np.random.default_rng(3)
    n = 7 * 52
    days = [date(2013, 1, 4) + timedelta(weeks=i) for i in range(n + 52)]
    sigma = rng.uniform(0.01, 0.05, len(days))
    data = pd.DataFrame({"anchor_date": days, "next_anchor_date": [d + timedelta(weeks=1) for d in days],
                         "true_sigma": sigma, "close_ret": sigma * rng.standard_normal(len(days)), "vix_close": 20.0})
    steps = ablation.forward_selection(data, None, Stub, candidates=["noise", "good"], years=periods.DEV_YEARS,
                                       start=(), log=lambda s: None)
    assert ablation.chosen_groups(steps) == ["good"]
    assert steps[-1].get("stopped")


# ---------------------------------------------------------------- the holdout lock

def test_holdout_lock(tmp_path):
    path = tmp_path / "model_choice.json"
    with pytest.raises(RuntimeError, match="no frozen choice"):
        periods.holdout_allowed(path)
    periods.freeze({"model": "gbm_quantile", "groups": ["vix"], "conformal": True}, path)
    assert periods.holdout_allowed(path)["model"] == "gbm_quantile"
    periods.record_holdout({"pinball": 0.0039}, path)
    with pytest.raises(RuntimeError, match="already been scored"):
        periods.holdout_allowed(path)
    with pytest.raises(RuntimeError, match="hindsight"):
        periods.freeze({"model": "ridge_sigma", "groups": ["vix"]}, path)
    periods.holdout_allowed(path, force=True)
    record = periods.record_holdout({"pinball": 0.0038}, path)
    assert record["holdout"]["pinball"] == 0.0039 and record["holdout_reruns"][0]["pinball"] == 0.0038
