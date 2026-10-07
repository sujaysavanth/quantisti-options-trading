from datetime import date

import numpy as np
import pandas as pd
import pytest

from app import market_spec
from app.dataset.features import COLUMNS, CORE_FEATURES, MODEL_FEATURES, OPTION_FEATURES, build_features
from app.dataset.labels import build_labels
from app.dataset.weeks import anchor_of_week, complete_anchors, sessions_next_week


def make_market(start=date(2024, 1, 2), end=date(2026, 4, 17), seed=7):
    """Random-walk SPX/VIX on the real NYSE calendar, plus a daily T-bill rate."""
    rng = np.random.default_rng(seed)
    days = market_spec.trading_days(start, end)
    close = 4000 * np.exp(np.cumsum(rng.normal(0, 0.01, len(days))))
    open_ = close * np.exp(rng.normal(0, 0.003, len(days)))
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.01, len(days)))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.01, len(days)))
    daily = pd.DataFrame({"date": days, "open": open_, "high": high, "low": low, "close": close,
                          "volume": rng.integers(2_000_000_000, 4_000_000_000, len(days))})
    vix = pd.DataFrame({"date": days, "close": 15 + 5 * np.abs(np.sin(np.arange(len(days)) / 40))})
    rates = pd.DataFrame({"date": days, "rate": 0.04 + 0.001 * np.cos(np.arange(len(days)) / 60)})
    return daily, vix, rates


def make_indexes(daily, seed=11):
    """The six index_daily series on the same sessions (VIX9D starts a few months in, like the real one)."""
    rng = np.random.default_rng(seed)
    n, days = len(daily), list(daily["date"])
    walk = lambda base, step: base + np.cumsum(rng.normal(0, step, n))  # noqa: E731
    series = {"VIX9D": walk(14, 0.3), "VIX3M": walk(18, 0.2), "VVIX": walk(85, 1.0), "SKEW": walk(140, 1.0),
              "BAA10Y": walk(1.8, 0.01), "T10Y2Y": walk(0.3, 0.01)}
    frames = [pd.DataFrame({"symbol": s, "date": days[60 if s == "VIX9D" else 0:],
                            "close": v[60 if s == "VIX9D" else 0:]}) for s, v in series.items()]
    return pd.concat(frames, ignore_index=True)


def build(daily, vix, rates, indexes=None):
    anchors = complete_anchors(daily["date"])
    indexes = make_indexes(daily) if indexes is None else indexes
    return anchors, build_features(daily, vix, rates, anchors, indexes=indexes), build_labels(daily, anchors)


# ---------------------------------------------------------------- anchors

def test_anchor_is_the_last_session_of_the_week():
    assert anchor_of_week(date(2026, 3, 25)) == date(2026, 3, 27)          # a normal Friday
    assert anchor_of_week(date(2026, 4, 1)) == date(2026, 4, 2)            # Good Friday 2026-04-03: Thursday
    assert sessions_next_week(date(2026, 3, 27)) == 4                       # the Good Friday week is short


def test_incomplete_or_gappy_weeks_have_no_anchor():
    stored = [date(2026, 3, 23), date(2026, 3, 24), date(2026, 3, 25), date(2026, 3, 26), date(2026, 3, 27),
              date(2026, 3, 30), date(2026, 3, 31)]                         # next week still in progress
    assert complete_anchors(stored) == [date(2026, 3, 27)]
    assert complete_anchors(stored[:4]) == []                              # Friday missing: no anchor on Thursday


# ---------------------------------------------------------------- features

def test_no_lookahead_features_match_data_cut_at_the_anchor():
    daily, vix, rates = make_market()
    anchors, full, _ = build(daily, vix, rates)
    for a in (anchors[60], anchors[85], anchors[-1]):
        indexes = make_indexes(daily)
        cut = [df[df["date"] <= a] for df in (daily, vix, rates, indexes)]
        truncated = build_features(*cut[:3], [a], indexes=cut[3]).iloc[0]
        row = full[full["anchor_date"] == a].iloc[0]
        for col in MODEL_FEATURES + ("macd", "macd_signal", "historical_vol_20d", "atr_14"):
            assert row[col] == pytest.approx(truncated[col], nan_ok=True), f"{col} at {a} uses later data"


def test_future_data_changes_nothing_in_the_past():
    daily, vix, rates = make_market()
    anchors, before, _ = build(daily, vix, rates)
    shocked = daily.copy()
    later = shocked["date"] > anchors[70]
    shocked.loc[later, ["open", "high", "low", "close"]] *= 2                # a crash/melt-up after anchor 70
    after = build_features(shocked, vix, rates, anchors, indexes=make_indexes(daily))
    cols = list(MODEL_FEATURES)
    pd.testing.assert_frame_equal(before.iloc[:71][cols], after.iloc[:71][cols])


def test_weekly_columns_cover_the_week_not_the_lookback():
    daily, vix, rates = make_market()
    anchors, features, _ = build(daily, vix, rates)
    a = anchors[50]
    row = features[features["anchor_date"] == a].iloc[0]
    d = daily.set_index("date")
    week = d.loc[[x for x in d.index if anchor_of_week(x) == a]]
    prev_close = d.loc[d.index < week.index[0], "close"].iloc[-1]
    assert row["weekly_change_pct"] == pytest.approx((d.loc[a, "close"] / prev_close - 1) * 100)
    assert row["range_1w"] == pytest.approx((week["high"].max() - week["low"].min()) / d.loc[a, "close"])
    assert row["ret_1w"] == pytest.approx(np.log(d.loc[a, "close"] / prev_close))


def test_feature_values_are_sane():
    daily, vix, rates = make_market()
    _, features, _ = build(daily, vix, rates)
    late = features.iloc[60:]                                               # past the 252-session warm-up
    assert list(features.columns) == list(COLUMNS)
    assert late[list(CORE_FEATURES)].notna().all().all()
    assert features[list(OPTION_FEATURES)].isna().all().all()             # no chains given
    assert late["rsi_14"].between(0, 100).all()
    assert (late["drawdown_52w"] <= 0).all() and late["vix_pct_1y"].between(0, 1).all()
    assert late["vix_hv_spread"].to_numpy() == pytest.approx((late["vix_close"] - late["historical_vol_20d"]).to_numpy())
    assert set(late["sessions_next"]) <= {3, 4, 5}


def test_rate_is_taken_before_the_anchor():
    daily, vix, rates = make_market()
    anchors, features, _ = build(daily, vix, rates)
    a = anchors[40]
    r = rates.set_index("date")["rate"]
    assert features.loc[features["anchor_date"] == a, "rate_3m"].iloc[0] == pytest.approx(r[r.index < a].iloc[-1])


# ---------------------------------------------------------------- labels

def test_labels_are_next_weeks_close_high_and_low():
    daily, vix, rates = make_market()
    anchors, _, labels = build(daily, vix, rates)
    a, n = anchors[30], anchors[31]
    lab = labels[labels["anchor_date"] == a].iloc[0]
    d = daily.set_index("date")
    nxt = d[(d.index > a) & (d.index <= n)]
    assert lab["next_anchor_date"] == n and lab["sessions"] == len(nxt)
    assert lab["close_ret"] == pytest.approx(np.log(d.loc[n, "close"] / d.loc[a, "close"]))
    assert lab["high_ret"] == pytest.approx(np.log(nxt["high"].max() / d.loc[a, "close"]))
    assert lab["low_ret"] == pytest.approx(np.log(nxt["low"].min() / d.loc[a, "close"]))
    assert anchors[-1] not in set(labels["anchor_date"])                    # its next week hasn't happened


def test_holiday_week_label_has_four_sessions():
    daily, vix, rates = make_market()
    _, _, labels = build(daily, vix, rates)
    lab = labels[labels["anchor_date"] == date(2026, 3, 27)].iloc[0]
    assert (lab["next_anchor_date"], lab["sessions"]) == (date(2026, 4, 2), 4)


def test_a_missing_session_drops_that_weeks_label():
    daily, vix, rates = make_market()
    gappy = daily[daily["date"] != date(2026, 3, 31)]                       # Tuesday of the Good Friday week
    anchors = complete_anchors(gappy["date"])
    labelled = set(build_labels(gappy, anchors)["anchor_date"])
    assert date(2026, 3, 27) not in labelled and date(2026, 3, 20) in labelled


def test_index_features_and_fred_taken_before_the_anchor():
    daily, vix, rates = make_market()
    indexes = make_indexes(daily)
    anchors, features, _ = build(daily, vix, rates, indexes)
    a = anchors[70]
    row = features[features["anchor_date"] == a].iloc[0]
    ix = {s: g.set_index("date")["close"] for s, g in indexes.groupby("symbol")}
    v = vix.set_index("date")["close"]
    assert row["vix9d_ratio"] == pytest.approx(ix["VIX9D"][a] / v[a])
    assert row["vix_term"] == pytest.approx(v[a] / ix["VIX3M"][a])
    assert row["skew_index"] == pytest.approx(ix["SKEW"][a])                 # CBOE: the anchor's own close
    baa = ix["BAA10Y"]
    assert row["baa10y"] == pytest.approx(baa[baa.index < a].iloc[-1])       # FRED: the day before
    assert features["vix9d"].iloc[:5].isna().all()                          # before VIX9D's history starts


def test_support_resistance_distances():
    daily, vix, rates = make_market()
    anchors, features, _ = build(daily, vix, rates)
    a = anchors[80]
    row = features[features["anchor_date"] == a].iloc[0]
    d = daily[daily["date"] <= a].tail(20)
    c = d["close"].iloc[-1]
    assert row["dist_high_20d"] == pytest.approx(c / d["high"].max() - 1) and row["dist_high_20d"] <= 0
    assert row["dist_low_20d"] == pytest.approx(c / d["low"].min() - 1) and row["dist_low_20d"] >= 0
