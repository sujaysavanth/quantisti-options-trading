import math
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from app.evaluation.baselines import NORMAL_Z, Context
from app.evaluation.walkforward import QCOLS
from app.forecasting import monitoring, serving
from app.forecasting.scheduler import due
from app.routers.predict import _block
from tests.test_evaluation import synthetic_rows

CHOICE = {"model": "gbm_sigma", "groups": ["vix", "options", "vix_term"], "reference": "garch",
          "frozen_at": "2026-10-08T00:23:15+00:00",
          "holdout": {"significance": {"gbm_sigma": {"garch": {"relative": 0.003, "p_value": 0.58, "n": 299}}}}}


def test_a_forecast_uses_nothing_after_its_anchor(monkeypatch):
    daily, data = synthetic_rows()
    monkeypatch.setattr(serving.store, "next_expiries", lambda anchors: [(a, a + timedelta(days=7)) for a in anchors])
    anchor = data["anchor_date"].iloc[-30]
    full = serving.forecast_anchor(data, data, Context(daily[["date", "close"]]), anchor, CHOICE)
    cut_daily = daily[daily["date"] <= anchor]
    cut = data[data["anchor_date"] <= anchor]
    truncated = serving.forecast_anchor(cut, cut, Context(cut_daily[["date", "close"]]), anchor, CHOICE)
    np.testing.assert_allclose(full[QCOLS].to_numpy(), truncated[QCOLS].to_numpy())
    assert set(full["role"]) == {"served", "second_opinion", "reference"}
    assert full.set_index("role").loc["served", "method"] == "garch"
    assert (full["trained_through"] < anchor).all()                       # the anchor's own outcome isn't known yet


def test_why_garch_is_served():
    text = serving.served_because(CHOICE)
    assert "gbm_sigma" in text and "p = 0.58" in text and "p < 0.05" in text
    assert "until a frozen model passes" in serving.served_because({"model": "gbm_sigma", "reference": "garch"})


def test_block_turns_quantiles_into_index_levels():
    row = pd.Series({"spot": 6800.0, "method": "garch", "origin": "live", "details": "", "trained_through": None,
                     **dict(zip(QCOLS, [-0.04, -0.03, 0.0, 0.03, 0.04]))})
    b = _block(row)
    assert b["median"] == 6800.0
    assert b["range_80"] == [round(6800 * math.exp(-0.03), 2), round(6800 * math.exp(0.03), 2)]


def stored(method, stretch, n=60, seed=0):
    rng = np.random.default_rng(seed)
    sigma = rng.uniform(0.01, 0.04, n)
    return pd.DataFrame({
        "anchor_date": [date(2025, 1, 3) + timedelta(weeks=i) for i in range(n)], "method": method, "role": "served",
        "origin": "backfill", "vix_close": rng.choice([12.0, 20.0, 30.0], n), "close_ret": sigma * rng.standard_normal(n),
        **{c: sigma * stretch * z for c, z in zip(QCOLS, NORMAL_Z)}})


def test_monitoring_flags_a_band_that_is_too_narrow():
    report = monitoring.monitor(pd.concat([stored("good", 1.0), stored("narrow", 0.4)]))
    good = report["methods"]["good"]["windows"]["last_52_weeks"]
    narrow = report["methods"]["narrow"]["windows"]["last_52_weeks"]
    assert not good["drift"] and narrow["drift"] and narrow["coverage_80"] < 0.5
    assert any(a.startswith("narrow") for a in report["alerts"]) and not any(a.startswith("good") for a in report["alerts"])
    assert good["weeks"] == 52 and set(good["coverage_80_by_regime"]) <= {"calm (VIX < 15)", "normal (VIX 15-25)",
                                                                           "stressed (VIX >= 25)"}


def test_binomial_test():
    assert monitoring.binomial_p(21, 26, 0.8) > 0.5                        # 81% hit: nothing unusual
    assert monitoring.binomial_p(12, 26, 0.8) < 0.01                       # 46% hit: drifted
    assert monitoring.binomial_p(26, 26, 0.8) < 0.05                       # every week inside: too wide


@pytest.mark.parametrize("latest,now,have,expected", [
    (date(2026, 10, 9), datetime(2026, 10, 9, 20, 50, tzinfo=timezone.utc), False, True),    # Friday 16:50 ET
    (date(2026, 10, 9), datetime(2026, 10, 9, 20, 30, tzinfo=timezone.utc), False, False),   # too soon
    (date(2026, 10, 9), datetime(2026, 10, 9, 21, 0, tzinfo=timezone.utc), True, False),     # already done
    (date(2026, 10, 8), datetime(2026, 10, 8, 21, 0, tzinfo=timezone.utc), False, False),    # Thursday: week not over
    (date(2026, 4, 2), datetime(2026, 4, 2, 21, 0, tzinfo=timezone.utc), False, True),       # Good Friday: Thursday
])
def test_scheduler_runs_once_per_completed_week(latest, now, have, expected):
    assert due(latest, have, now) is expected


def test_service_connections_give_tuple_cursors(monkeypatch):
    """The pool's connections default to dict cursors; app/dataset/ code indexes rows by position."""
    import psycopg2.extensions
    from psycopg2.extras import RealDictCursor

    from app.services import feature_service

    class FakeConn:
        cursor_factory = RealDictCursor
        def commit(self): pass
        def rollback(self): pass

    conn = FakeConn()
    monkeypatch.setattr(feature_service, "get_db_connection", lambda: conn)
    monkeypatch.setattr(feature_service, "return_db_connection", lambda c: None)
    with feature_service._connection() as c:
        assert c.cursor_factory is psycopg2.extensions.cursor
