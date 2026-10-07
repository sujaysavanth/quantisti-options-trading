import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from app.dataset.features import CORE_FEATURES
from app.evaluation import report, walkforward
from app.evaluation.baselines import (NORMAL_Z, Context, Garch, HarRv, RealisedVol, VixRaw, VixScaled,
                                      all_baselines, straddle_sigma)
from app.evaluation.metrics import QUANTILES, coverage, pinball, score, winkler
from tests.test_dataset import build, make_market


# ---------------------------------------------------------------- metrics

def test_pinball_by_hand():
    y = np.array([1.0])
    q = np.zeros((1, 5))                                   # every quantile at 0, outcome 1: all too low
    assert pinball(y, q) == pytest.approx(np.mean(QUANTILES))
    assert pinball(np.array([-1.0]), q) == pytest.approx(np.mean([1 - t for t in QUANTILES]))
    assert pinball(np.array([0.0]), q) == 0


def test_coverage_and_winkler_by_hand():
    y, lo, hi = np.array([0.0, 2.0]), np.array([-1.0, -1.0]), np.array([1.0, 1.0])
    assert coverage(y, lo, hi) == 0.5
    assert winkler(y, lo, hi, alpha=0.2) == pytest.approx((2 + (2 + 10 * 1)) / 2)   # 2nd misses by 1: +2/0.2


def test_score_drops_weeks_without_a_forecast():
    y = np.array([0.0, 0.01, -0.01])
    q = np.array([[-0.02, -0.01, 0, 0.01, 0.02]] * 3, dtype=float)
    q[1] = np.nan
    assert score(y, q)["n"] == 2 and score(y, q)["coverage_80"] == 1.0


def test_the_right_sigma_scores_best_and_is_calibrated():
    rng = np.random.default_rng(0)
    sigma = rng.uniform(0.01, 0.04, 4000)                                    # volatility that changes week to week
    y = sigma * rng.standard_normal(4000)
    right = sigma[:, None] * NORMAL_Z[None, :]
    constant = np.full_like(right, 1) * (sigma.std() + sigma.mean()) * NORMAL_Z[None, :]
    too_wide = 1.3 * right
    s_right, s_const, s_wide = score(y, right), score(y, constant), score(y, too_wide)
    assert s_right["coverage_80"] == pytest.approx(0.80, abs=0.02)
    assert s_wide["coverage_80"] > 0.86                                      # like raw VIX: covers too much
    assert s_right["pinball"] < s_wide["pinball"] and s_right["pinball"] < s_const["pinball"]


# ---------------------------------------------------------------- baselines

def weekly(n=300, seed=1, vix_bias=1.25):
    """Synthetic weekly rows: true sigma drives the outcome; 'VIX' overstates it by vix_bias."""
    rng = np.random.default_rng(seed)
    sigma = rng.uniform(0.01, 0.04, n)
    return pd.DataFrame({"close_ret": sigma * rng.standard_normal(n), "sessions_next": 5,
                         "vix_close": sigma * vix_bias / math.sqrt(5 / 252) * 100,
                         "rv_20d": sigma / math.sqrt(5 / 252)})


def test_raw_vix_over_covers_and_scaling_fixes_it():
    train, test = weekly(seed=1, n=2000), weekly(seed=2, n=2000)
    raw, scaled = VixRaw(), VixScaled()
    for b in (raw, scaled):
        b.fit(train, None)
    s_raw, s_scaled = (score(test["close_ret"].to_numpy(), b.predict(test, None)) for b in (raw, scaled))
    assert s_raw["coverage_80"] > 0.88                                       # 25% too wide
    assert s_scaled["coverage_80"] == pytest.approx(0.80, abs=0.03)          # learned the 1.25 away
    assert s_scaled["pinball"] < s_raw["pinball"]


def test_realised_vol_uses_the_same_quantile_mapping():
    train = weekly(n=500)
    b = RealisedVol()
    b.fit(train, None)
    q = b.predict(train.head(3), None)
    assert q.shape == (3, 5) and (np.diff(q, axis=1) > 0).all()             # quantiles in order


def synthetic_rows():
    daily, vix, rates = make_market(start=date(2016, 1, 4), end=date(2025, 12, 31), seed=3)
    anchors, features, labels = build(daily, vix, rates)
    data = features.dropna(subset=list(CORE_FEATURES)).merge(labels, on="anchor_date")
    return daily, data


def test_har_and_garch_fit_and_forecast_on_daily_data():
    daily, data = synthetic_rows()
    ctx = Context(daily[["date", "close"]])
    train, test = walkforward.split(data, 2024)
    for b in (HarRv(), Garch()):
        b.fit(train, ctx)
        s = b.sigma(test, ctx)
        # the synthetic market moves ~1% a day: ~2.2% a week
        assert np.isfinite(s).all() and 0.01 < np.median(s) < 0.04, (b.name, np.median(s))
    garch = Garch()
    garch.fit(train, ctx)
    assert 0 <= garch.alpha + garch.beta_ < 1.0001


def test_garch_forecast_uses_only_returns_up_to_the_anchor():
    daily, data = synthetic_rows()
    train, test = walkforward.split(data, 2024)
    g = Garch()
    g.fit(train, Context(daily[["date", "close"]]))
    a = test["anchor_date"].iloc[10]
    later = daily.copy()
    later.loc[later["date"] > a, "close"] *= 1.5                            # a shock after the anchor
    before = g.sigma(test.iloc[[10]], Context(daily[["date", "close"]]))
    g.h_next = g._filter(Context(later[["date", "close"]]).returns * 100)
    after = g.sigma(test.iloc[[10]], Context(later[["date", "close"]]))
    assert after == pytest.approx(before)


def test_straddle_sigma_from_atm_quotes():
    quotes = pd.DataFrame({
        "anchor_date": [date(2020, 1, 3)] * 4 + [date(2020, 1, 10)] * 2,
        "strike": [3230.0, 3230.0, 3235.0, 3235.0, 3500.0, 3500.0],
        "option_type": ["C", "P", "C", "P", "C", "P"],
        "bid": [30.0, 28.0, 27.0, 31.0, 1.0, 1.0], "ask": [31.0, 29.0, 28.0, 32.0, 1.2, 1.2],
        "underlying_price": [3234.0] * 4 + [3265.0] * 2, "source": ["optionsdx"] * 6})
    sig = straddle_sigma(quotes)
    assert sig[date(2020, 1, 3)] == pytest.approx((27.5 + 31.5) / 3234 / math.sqrt(2 / math.pi))   # nearest strike
    assert date(2020, 1, 10) not in sig                                       # nothing within 1% of spot


# ---------------------------------------------------------------- walk-forward

def test_split_keeps_test_year_out_of_training():
    _, data = synthetic_rows()
    train, test = walkforward.split(data, 2024)
    assert max(a.year for a in train["anchor_date"]) == 2023 and {a.year for a in test["anchor_date"]} == {2024}
    assert train["next_anchor_date"].max() <= test["anchor_date"].min()


class Spy:
    name = "spy"

    def __init__(self):
        self.seen = []

    def fit(self, train, ctx):
        self.train_years = {a.year for a in train["anchor_date"]}

    def predict(self, test, ctx):
        self.seen.append((self.train_years, {a.year for a in test["anchor_date"]}, set(test.columns)))
        return np.zeros((len(test), 5))


def test_run_never_shows_labels_or_future_years_to_a_forecaster():
    daily, data = synthetic_rows()
    spy = Spy()
    walkforward.run(data, Context(daily[["date", "close"]]), [spy], [2023, 2024])
    for train_years, test_years, columns in spy.seen:
        assert max(train_years) < min(test_years)
        assert not columns & set(walkforward.LABEL_COLUMNS)


def test_full_run_and_report_on_synthetic_data(tmp_path):
    daily, data = synthetic_rows()
    baselines = all_baselines()                                              # straddle has no chains here
    preds = walkforward.run(data, Context(daily[["date", "close"]]), baselines, [2024, 2025])
    summary = report.summarize(preds, [b.name for b in baselines])
    assert summary["overall"]["straddle"]["n"] == 0
    assert all(summary["overall"][b]["n"] > 80 for b in ("vix_raw", "vix_scaled", "rv_20d", "har_rv", "garch"))
    paths = report.write(summary, tmp_path)
    md = paths[1].read_text(encoding="utf8")
    assert "| har_rv |" in md and "stressed" in md
