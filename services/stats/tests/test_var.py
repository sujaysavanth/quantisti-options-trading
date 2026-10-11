import math
from datetime import date, datetime, timezone

import numpy as np
import pytest

from app.services import var, var_run
from app.services.exposure import Market

from .test_stress import quote, leg, trade, RATE


def test_var_and_es_from_a_sample():
    pnl = -np.arange(1, 101, dtype=float)                   # losses 1..100
    v, es = var.var_es(pnl, 0.95)
    assert v == pytest.approx(np.quantile(np.arange(1, 101), 0.95))
    assert es == pytest.approx(np.arange(1, 101)[np.arange(1, 101) >= v].mean())
    assert es >= v


def test_ewma_is_known_before_the_day():
    r = [0.01] * 30 + [0.05]
    s = var.ewma_sigmas(r)
    assert s[0] == pytest.approx(0.01) and s[30] == pytest.approx(0.01)        # the 5% day isn't in its own sigma
    assert s[31] == pytest.approx(math.sqrt(0.94 * 0.01 ** 2 + 0.06 * 0.05 ** 2))


def test_filtered_moves_rescale_to_todays_vol():
    moves = [(0.01 * (-1) ** i, 0.5 * (-1) ** i) for i in range(60)]
    out, sig, source = var.filtered_moves(moves, 0.02)                         # twice the history's 1%
    assert source == "garch" and sig == 0.02 and len(out) == 60 - var.EWMA_WARMUP
    assert out[0][0] == pytest.approx(-0.02 * (-1) ** var.EWMA_WARMUP * -1) and abs(out[0][1]) == pytest.approx(1.0)
    _, sig, source = var.filtered_moves(moves, None)
    assert source == "ewma" and sig == pytest.approx(0.01)


def test_delta_only_book_matches_the_normal_formula():
    rng = np.random.default_rng(1)
    moves = list(zip(rng.normal(0, 0.01, 2000), rng.normal(0, 1, 2000)))
    totals = {"delta": 100.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0}             # $100 per SPX point
    v, _ = var.var_es(var.taylor_pnl(totals, 6800, moves), 0.99)
    sd = 100 * 6800 * np.std([m[0] for m in moves], ddof=1)
    assert v == pytest.approx(2.326 * sd, rel=0.05)


def test_kupiec():
    ok = var.kupiec([True] * 3 + [False] * 247, 0.99)                         # 3 breaches vs 2.5 expected
    assert ok["p_value"] > 0.5
    bad = var.kupiec([True] * 10 + [False] * 240, 0.99)                       # Basel red zone
    assert bad["p_value"] < 0.001 and bad["breaches"] == 10
    none = var.kupiec([False] * 250, 0.99)
    # No breaches in 250 days at 99% is itself evidence the VaR is too high: P(chi2(1) > 5.03) = 0.025.
    assert none["lr"] == pytest.approx(-2 * 250 * math.log(0.99)) and none["p_value"] == pytest.approx(0.025, abs=1e-3)


def test_christoffersen_spots_clustering():
    spread = ([True] + [False] * 19) * 10
    clustered = [True] * 10 + [False] * 190
    assert var.christoffersen(spread)["p_value"] > 0.3
    assert var.christoffersen(clustered)["p_value"] < 0.001
    assert var.christoffersen([False] * 50)["p_value"] is None


def test_backtest_pairs_var_with_the_next_days_pnl():
    rows = [{"session": date(2026, 10, d), "method": "historical", "confidence": 0.95, "var": 500.0} for d in (5, 6, 7)]
    out = var.backtest(rows, {date(2026, 10, 5): -800.0, date(2026, 10, 6): 300.0})
    [t] = out["tests"]
    assert t["kupiec"]["observations"] == 2 and t["breach_days"] == ["2026-10-05"]


def test_realised_next_needs_consecutive_sessions():
    closes = [{"session": "2026-10-08", "account_value": 30_000}, {"session": "2026-10-09", "account_value": 30_250},
              {"session": "2026-10-13", "account_value": 30_100}]                 # Monday 12th missing
    assert var_run.realised_next(closes) == {date(2026, 10, 8): 250.0}


def test_due_close_window():
    assert var_run.due_close(datetime(2026, 10, 9, 20, 10, tzinfo=timezone.utc)) is None
    assert var_run.due_close(datetime(2026, 10, 9, 20, 25, tzinfo=timezone.utc)) == date(2026, 10, 9)
    assert var_run.due_close(datetime(2026, 10, 10, 0, 20, tzinfo=timezone.utc)) is None
    assert var_run.due_close(datetime(2026, 10, 10, 20, 25, tzinfo=timezone.utc)) is None         # Saturday


def test_compute_every_method_on_a_long_call():
    rng = np.random.default_rng(3)
    moves = list(zip(rng.normal(0, 0.01, 600), rng.normal(0, 1.0, 600)))
    trades = [trade("a", [leg("BUY", "CALL", 6800, qty=2)])]
    out = var_run.compute(trades, Market(quote(), RATE), RATE, moves, 0.005, "2026-10-09")
    assert set(out["methods"]) == {"historical", "filtered_historical", "delta_gamma_vega"}
    for m in out["methods"].values():
        for level in m["levels"].values():
            assert level["var"] > 0 and level["es"] >= level["var"]
        assert m["levels"]["0.99"]["var"] >= m["levels"]["0.95"]["var"]
    filt = out["methods"]["filtered_historical"]
    assert filt["sigma_source"] == "garch" and filt["garch_origin"] == "2026-10-09"
    # half the history's vol: the filtered tail is smaller
    assert filt["levels"]["0.99"]["var"] < out["methods"]["historical"]["levels"]["0.99"]["var"]
    long_premium = out["methods"]["delta_gamma_vega"]["greeks"]
    assert long_premium["gamma"] > 0 and long_premium["theta"] < 0
    rows = var_run.rows_for(date(2026, 10, 9), out, 30_000.0)
    assert len(rows) == 6 and {r["confidence"] for r in rows} == {0.95, 0.99}
    assert "levels" not in rows[0]["details"]


def test_empty_book_has_zero_var():
    rng = np.random.default_rng(4)
    moves = list(zip(rng.normal(0, 0.01, 100), rng.normal(0, 1.0, 100)))
    out = var_run.compute([], Market(quote(), RATE), RATE, moves, None, None)
    assert out["methods"]["historical"]["levels"]["0.99"]["var"] == 0
