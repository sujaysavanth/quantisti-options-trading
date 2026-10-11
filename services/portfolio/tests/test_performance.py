import math
from datetime import date

import numpy as np
import pytest

from app import market_spec
from app.services import performance as perf


def snaps(values, start=date(2026, 6, 1)):
    days = market_spec.trading_days(start, date(2027, 6, 1))[:len(values)]
    return [{"session": d, "account_value": v} for d, v in zip(days, values)], days


def test_drawdown_peak_trough_and_recovery():
    values = [100, 110, 99, 105, 111, 90]
    days = [None, *market_spec.trading_days(date(2026, 6, 1), date(2026, 6, 10))[:5]]
    dd = perf.drawdown(values, days)
    assert dd["max_drawdown"] == pytest.approx(90 / 111 - 1)
    assert dd["peak"] == days[4] and dd["trough"] == days[5]
    assert dd["sessions_to_trough"] == 1 and dd["sessions_to_recover"] is None      # still under water
    first = perf.drawdown(values[:5], days[:5])
    assert first["max_drawdown"] == pytest.approx(99 / 110 - 1) and first["sessions_to_recover"] == 2


def test_drawdown_from_the_starting_balance():
    dd = perf.drawdown([30_000, 29_000, 31_000], [None, date(2026, 6, 1), date(2026, 6, 2)])
    assert dd["peak"] is None and dd["max_drawdown"] == pytest.approx(-1 / 30)        # None peak = the start
    assert dd["sessions_to_recover"] == 1 and dd["current_drawdown"] == 0


def test_short_history_reports_returns_but_no_ratios():
    rows, days = snaps([30_100, 30_400, 30_250])
    out = perf.equity_stats(rows, 30_000, [], {days[0]: 6000, days[-1]: 6060})
    assert out["returns"] == 2 and out["total_return"] == pytest.approx(250 / 30_000)
    assert out["period_return"] == pytest.approx(30_250 / 30_100 - 1)
    assert out["spx_return"] == pytest.approx(0.01)
    assert out["sharpe"] is None and out["volatility"] is None and out["beta"] is None


def test_ratios_match_the_backtest_definitions():
    rng = np.random.default_rng(7)
    r = rng.normal(0.001, 0.01, 40)
    values = list(30_000 * np.cumprod(1 + np.concatenate([[0.0], r])))
    rows, days = snaps(values)
    spx_r = 0.5 * r + rng.normal(0, 0.002, 40)                         # beta ~2 the other way round
    spx = dict(zip(days, 6000 * np.cumprod(1 + np.concatenate([[0.0], spx_r]))))
    rates = [(date(2026, 5, 29), 0.0504)]                              # before the first session: carried forward
    out = perf.equity_stats(rows, 30_000, rates, spx)
    excess = r - 0.0504 / 252
    assert out["sharpe"] == pytest.approx(excess.mean() / excess.std(ddof=1) * math.sqrt(252))
    downside = np.sqrt(np.mean(np.minimum(excess, 0) ** 2))
    assert out["sortino"] == pytest.approx(excess.mean() / downside * math.sqrt(252))
    assert out["volatility"] == pytest.approx(r.std(ddof=1) * math.sqrt(252))
    assert out["beta"] == pytest.approx(np.cov(r, spx_r)[0, 1] / np.var(spx_r, ddof=1))
    assert 0.9 < out["correlation"] <= 1


def test_missing_sessions_are_counted():
    days = market_spec.trading_days(date(2026, 6, 1), date(2026, 6, 5))
    rows = [{"session": d, "account_value": 30_000} for d in (days[0], days[3], days[4])]
    assert perf.equity_stats(rows, 30_000, [], {})["missing_sessions"] == 2


def trade(pnl, nickname, opened="2026-10-08T14:00:00Z", closed="2026-10-09T19:30:00Z", status="closed"):
    return {"pnl": pnl, "nickname": nickname, "status": status, "created_at": opened, "closed_at": closed}


def test_trade_stats_and_by_strategy():
    trades = [trade(500, "Bull Call Spread"), trade(-200, "Bull Call Spread"), trade(300, "Iron Condor",
              opened="2026-10-09T13:30:00Z"), trade(-100, "Iron Condor", status="open", closed=None)]
    out = perf.trade_stats(trades)
    assert out["trades"] == 3 and out["total_pnl"] == 600
    assert out["win_rate"] == pytest.approx(2 / 3)
    assert out["average_win"] == 400 and out["average_loss"] == -200
    assert out["profit_factor"] == pytest.approx(4) and out["expectancy"] == pytest.approx(200)
    assert out["largest_win"] == 500 and out["largest_loss"] == -200
    assert out["median_holding_hours"] == pytest.approx(29.5)                 # 29.5, 29.5, 6
    assert out["by_strategy"]["Iron Condor"]["trades"] == 1
    assert out["by_strategy"]["Iron Condor"]["profit_factor"] is None          # no losses yet


def test_performance_flags_small_samples():
    rows, _ = snaps([30_000, 30_100])
    out = perf.performance(rows, [trade(100, "x")], 30_000, [], {})
    assert out["meaningful"] is False and len(out["notes"]) == 2
    empty = perf.performance([], [], 30_000, [], {})
    assert empty["equity"]["total_return"] is None and empty["trades"]["win_rate"] is None
