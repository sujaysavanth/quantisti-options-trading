import json
import math
from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from app.dataset.features import OPTION_FEATURES
from app.evaluation import walkforward
from app.evaluation.baselines import Context, Garch, VixRaw
from app.forecasting import catalog, serving
from app.forecasting.explain import explain, garch_breakdown
from tests.test_evaluation import synthetic_rows
from tests.test_serving import CHOICE


@pytest.fixture(scope="module")
def fitted():
    daily, data = synthetic_rows()
    ctx = Context(daily[["date", "close"]])
    train, test = walkforward.split(data, 2024)
    return ctx, train, test


def test_garch_parts_add_up_to_its_forecast(fitted):
    ctx, train, test = fitted
    g = Garch()
    g.fit(train, ctx)
    for k in (0, 7, 30):
        row = test.iloc[[k]]
        ex = explain(g, row, ctx, row["anchor_date"].iloc[0])
        sigma = float(g.sigma(row, ctx)[0])
        assert ex["sigma"] == pytest.approx(sigma, rel=1e-9)
        assert math.sqrt(sum(ex["variance"].values())) == pytest.approx(sigma, rel=1e-9)
        assert sum(ex["sigma_parts"].values()) == pytest.approx(sigma, rel=1e-9)
        q = g.predict(row, ctx)[0]                                   # the quantiles are sigma * z
        assert np.allclose(q, sigma * np.array(ex["z"]))
        assert ex["half_life_sessions"] > 0


def test_garch_breakdown_by_hand():
    """omega 0.02, alpha 0.1, beta 0.8 -> long-run variance 0.2 (percent^2 a day); 5 sessions."""
    g = Garch()
    g.mu, g.omega, g.alpha, g.beta_ = 0.0, 0.02, 0.1, 0.8
    g.h_next = np.array([0.5, 0.02 + 0.1 * 4.0 + 0.8 * 0.5])        # day 1: a -2% move after variance 0.5
    ctx = Context(pd.DataFrame({"date": pd.to_datetime(["2026-01-05", "2026-01-06"]), "close": [100.0, 100 * math.exp(-0.02)]}))
    ex = garch_breakdown(g, ctx, pd.Timestamp("2026-01-06"), 5)
    k = (1 - 0.9 ** 5) / (1 - 0.9)
    assert ex["variance"]["long_run"] * 1e4 == pytest.approx(5 * 0.2)
    assert ex["variance"]["last_move"] * 1e4 == pytest.approx(k * 0.1 * (4.0 - 0.2))
    assert ex["variance"]["carried_over"] * 1e4 == pytest.approx(k * 0.8 * (0.5 - 0.2))
    assert ex["half_life_sessions"] == pytest.approx(math.log(0.5) / math.log(0.9))


def test_tree_shap_adds_up_and_turns_into_multipliers(fitted):
    ctx, train, test = fitted
    m = catalog.build("gbm_sigma", CHOICE["groups"])
    m.fit(train, ctx)
    row = test.iloc[[5]]
    ex = explain(m, row, ctx, row["anchor_date"].iloc[0])
    assert ex["kind"] == "tree_shap"
    assert ex["additivity_error"] < 1e-6
    assert ex["sigma"] == pytest.approx(float(m.sigma(row, ctx)[0]), rel=1e-9)
    product = math.prod(f["multiplier"] for f in ex["features"])
    assert ex["sigma_base"] * product == pytest.approx(ex["sigma"], rel=1e-9)
    assert sum(g["contribution"] for g in ex["groups"]) == pytest.approx(sum(f["contribution"] for f in ex["features"]))
    assert {g["group"] for g in ex["groups"]} <= set(CHOICE["groups"])
    # the synthetic market has no option chains: those columns are dropped in training and get no credit
    unused = [f for f in ex["features"] if f["name"] in OPTION_FEATURES]
    assert unused and all(not f["used"] and f["contribution"] == 0 for f in unused)
    contributions = [abs(f["contribution"]) for f in ex["features"]]
    assert contributions == sorted(contributions, reverse=True)


def test_vix_reference_is_the_formula(fitted):
    ctx, train, test = fitted
    v = VixRaw()
    v.fit(train, ctx)
    row = test.iloc[[0]]
    ex = explain(v, row, ctx, row["anchor_date"].iloc[0])
    assert ex["sigma"] == pytest.approx(float(v.sigma(row, ctx)[0]))


def test_every_stored_forecast_carries_a_json_explanation(monkeypatch):
    daily, data = synthetic_rows()
    monkeypatch.setattr(serving.store, "next_expiries", lambda anchors: [(a, a + timedelta(days=7)) for a in anchors])
    anchor = data["anchor_date"].iloc[-30]
    fc = serving.forecast_anchor(data, data, Context(daily[["date", "close"]]), anchor, CHOICE)
    kinds = dict(zip(fc["role"], fc["explanation"].map(lambda e: e["kind"])))
    assert kinds == {"served": "garch", "second_opinion": "tree_shap", "reference": "vix"}
    for ex in fc["explanation"]:
        json.dumps(ex)                                                # storable as JSONB: plain floats, no NaN
        assert "NaN" not in json.dumps(ex)
