from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from app.evaluation.walkforward import QCOLS
from app.forecasting import horizons as H
from app.forecasting import monitoring
from app.forecasting.scheduler import due_daily
from tests.test_evaluation import synthetic_rows


@pytest.fixture(scope="module")
def data():
    daily, _ = synthetic_rows()
    rng = np.random.default_rng(5)
    vix = pd.DataFrame({"date": daily["date"], "close": 15 + 5 * rng.random(len(daily))})
    return H.HorizonData.from_frames(daily, vix)


def test_a_forecast_uses_nothing_after_its_origin(data):
    origin = data.day(len(data.dates) - 40)
    full = H.forecast_origin(data, origin)
    cut = len(data.dates) - 39
    daily = pd.DataFrame({"date": [data.day(i) for i in range(cut)], "close": np.exp(data.log_close[:cut])})
    truncated = H.forecast_origin(H.HorizonData.from_frames(daily, pd.DataFrame({"date": daily["date"], "close": data.vix[:cut]})), origin)
    np.testing.assert_allclose(full[QCOLS].to_numpy(float), truncated[QCOLS].to_numpy(float))


def test_five_sessions_match_the_weekly_garch_formula(data):
    g = H.fit_garch(data, data.day(len(data.dates) - 100))
    sig = H.sigmas(H.variance_paths(g))
    i = len(data.dates) - 50
    row = pd.DataFrame({"anchor_date": [pd.Timestamp(data.dates[i])], "sessions_next": [5]})
    assert sig[i, 4] == pytest.approx(float(g.sigma(row, data.ctx)[0]), rel=1e-9)
    assert (np.diff(sig[i]) > 0).all()                                      # wider the further out


def test_forecasts_cover_each_listed_expiry_with_its_variance_path(data):
    fc = H.forecast_origin(data, data.day(len(data.dates) - 1))
    assert list(fc["sessions"]) == sorted(fc["sessions"]) and fc["sessions"].max() <= H.H_MAX
    for r in fc.itertuples():
        assert len(r.variance_path) == r.sessions == len(r.path_dates) and r.path_dates[-1] == r.expiry_date
        assert np.sqrt(sum(r.variance_path)) == pytest.approx(r.sigma)
        assert r.q10 == pytest.approx(r.sigma * r.z[1])


def test_listed_expiries_follow_the_history():
    assert [e for e, _, _ in H.listed_expiries(date(2026, 10, 8))][:3] == [date(2026, 10, 9), date(2026, 10, 12), date(2026, 10, 13)]
    early = H.listed_expiries(date(2015, 3, 2))                           # Fridays only before Aug 2016
    assert all(e.weekday() == 4 for e, _, _ in early) and early[0][1] == 4


def test_walk_forward_and_the_gate(data):
    preds = H.walk_forward(data, [2023, 2024], h_max=3)
    assert set(preds["method"]) == {"garch", "vix_scaled"} and set(preds["horizon"]) == {1, 2, 3}
    assert (pd.to_datetime(preds["origin_date"]).dt.year.isin([2023, 2024])).all()
    result = H.evaluate(preds)
    for r in result.values():
        assert r["valid"] == (H.GATE[0] <= r["coverage_80"] <= H.GATE[1])
    rigged = {"1": {**result["1"], "coverage_80": 0.95, "valid": False}}
    v = H.validation(1, {"horizons": rigged, "dev_years": [2014, 2020]})
    assert not v["valid"] and "95%" in v["reason"]
    assert not H.validation(7, {"horizons": rigged, "dev_years": [2014, 2020]})["valid"]


def test_the_holdout_is_recorded_once(tmp_path):
    path = tmp_path / "horizons.json"
    H.freeze({"1": {"coverage_80": 0.8, "valid": True}}, range(2014, 2021), path=path)
    H.record_holdout({"1": {"coverage_80": 0.79}}, range(2021, 2026), path=path)
    with pytest.raises(RuntimeError):
        H.record_holdout({"1": {"coverage_80": 0.7}}, range(2021, 2026), path=path)
    with pytest.raises(RuntimeError):
        H.freeze({"1": {"coverage_80": 0.8, "valid": True}}, range(2014, 2021), path=path)
    rec = H.record_holdout({"1": {"coverage_80": 0.7}}, range(2021, 2026), force=True, path=path)
    assert rec["holdout"]["horizons"]["1"]["coverage_80"] == 0.79 and len(rec["holdout_reruns"]) == 1


def test_monitoring_by_horizon():
    n = 80
    rng = np.random.default_rng(1)
    rows = pd.DataFrame({"origin_date": [date(2025, 1, 2) + timedelta(days=i) for i in range(n)], "sessions": 1,
                         "vix_close": 18.0, "close_ret": 0.01 * rng.standard_normal(n),
                         **{c: 0.01 * z for c, z in zip(QCOLS, [-1.64, -1.28, 0, 1.28, 1.64])}})
    out = monitoring.monitor_horizons(rows)
    assert out["1"]["last_60"]["weeks"] == 60 and 0.6 < out["1"]["last_250"]["coverage_80"] < 0.95


def test_daily_refresh_is_due_after_each_close():
    close = datetime(2026, 10, 8, 20, 0, tzinfo=timezone.utc)                # Thursday 16:00 ET
    assert not due_daily(date(2026, 10, 8), False, close + timedelta(minutes=30))
    assert due_daily(date(2026, 10, 8), False, close + timedelta(minutes=50))
    assert not due_daily(date(2026, 10, 8), True, close + timedelta(minutes=50))
