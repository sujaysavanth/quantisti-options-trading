import numpy as np
import pytest

pytest.importorskip("mlflow")

from app import registry, tracking  # noqa: E402
from app.evaluation import walkforward  # noqa: E402
from app.evaluation.baselines import VixScaled  # noqa: E402
from app.forecasting.conformal import apply_adjustments, conformalize, regime_adjustments  # noqa: E402
from tests.test_evaluation import synthetic_rows  # noqa: E402
from tests.test_models import miscalibrated_preds  # noqa: E402


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    monkeypatch.setattr(tracking, "data_dir", lambda: tmp_path)
    return tmp_path


SUMMARY = {
    "overall": {"vix_scaled": {"n": 52, "pinball": 0.0038, "coverage_80": 0.8},
                "gbm_sigma+conformal": {"n": 52, "pinball": 0.0037, "coverage_80": 0.79}},
    "by_regime": {"calm (VIX < 15)": {"vix_scaled": {"n": 30, "coverage_80": 0.86}}},
    "significance": {"gbm_sigma+conformal": {"vix_scaled": {"n": 52, "p_value": 0.3, "relative": -0.02}}},
}


def test_a_run_records_scores_and_where_they_came_from(store):
    _, data = synthetic_rows()
    with tracking.run("evaluate-models", {"groups": ["vix", "options"], "period": "development"}, data) as mlf:
        tracking.log_summary(mlf, SUMMARY)
        run_id = mlf.active_run().info.run_id
    import mlflow
    r = mlflow.get_run(run_id)
    assert r.data.params["groups"] == "vix,options"
    assert r.data.metrics["vix_scaled.pinball"] == pytest.approx(0.0038)
    assert r.data.metrics["gbm_sigma_conformal.vs.vix_scaled.p_value"] == pytest.approx(0.3)   # '+' made safe
    assert r.data.metrics["vix_scaled.coverage_80.calm"] == pytest.approx(0.86)
    assert {"git_commit", "git_dirty", "feature_version", "data_fingerprint"} <= set(r.data.tags)


def test_tracking_can_be_turned_off(store, monkeypatch):
    monkeypatch.setenv("ML_TRACKING", "off")
    with tracking.run("evaluate-models", {}) as mlf:
        assert mlf is None
        tracking.log_summary(mlf, SUMMARY)                                # no-ops


def test_fingerprint_changes_with_the_data():
    _, data = synthetic_rows()
    changed = data.copy()
    changed.loc[changed.index[-1], "close_ret"] += 0.001
    assert tracking.data_fingerprint(data) == tracking.data_fingerprint(data.copy())
    assert tracking.data_fingerprint(data) != tracking.data_fingerprint(changed)


def test_registered_model_predicts_like_the_original(store):
    _, data = synthetic_rows()
    train, test = walkforward.split(data, 2025)
    model = VixScaled()
    model.fit(train, None)
    adjustments = {"all": {"q10-q90": 0.1, "q05-q95": 0.05}}
    features = test.drop(columns=walkforward.LABEL_COLUMNS)
    with tracking.run("freeze", {"model": "vix_scaled"}, data) as mlf:
        version = registry.register(mlf, model, {"model": "vix_scaled"}, adjustments, features.head(3))
    loaded = registry.load(version)
    got = loaded.predict(features).to_numpy()
    want = apply_adjustments(model.predict(features, None), features["vix_close"].to_numpy(), adjustments)
    np.testing.assert_allclose(got, want)
    assert list(loaded.predict(features).columns) == walkforward.QCOLS


def test_serving_adjustments_match_the_walk_forward_calibration():
    preds = miscalibrated_preds()
    history, last = preds[preds["year"] < 2020], preds[preds["year"] == 2020]
    adj = regime_adjustments(history)
    served = apply_adjustments(last[walkforward.QCOLS].to_numpy(), last["vix_close"].to_numpy(), adj)
    walked = conformalize(preds)
    np.testing.assert_allclose(served, walked[walked["year"] == 2020][walkforward.QCOLS].to_numpy())
