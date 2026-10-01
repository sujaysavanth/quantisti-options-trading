import math
from datetime import date, timedelta

import numpy as np
import pytest

from app.services.metrics_calculator import RISK_FREE_RATE, MetricsCalculator


def weekly_trades(pnls):
    start = date(2026, 6, 1)
    return [{"pnl": p, "entry_date": start + timedelta(weeks=i), "holding_days": 1} for i, p in enumerate(pnls)]


def test_periods_per_year_follows_entry_spacing():
    dates = [date(2026, 1, 5) + timedelta(weeks=i) for i in range(10)]
    assert MetricsCalculator._periods_per_year(dates) == pytest.approx(365.25 / 7)


def test_sharpe_uses_returns_on_capital_and_entry_frequency():
    pnls = [1000.0, -500.0, 800.0, 300.0, -200.0, 600.0]
    metrics = MetricsCalculator()._calculate_all_metrics(weekly_trades(pnls), initial_capital=100_000)

    returns = np.array(pnls) / 100_000 - RISK_FREE_RATE / (365.25 / 7)
    expected = returns.mean() / returns.std(ddof=1) * math.sqrt(365.25 / 7)
    assert metrics["sharpe_ratio"] == pytest.approx(expected, abs=1e-4)
    assert metrics["total_pnl"] == 2000.0
    assert metrics["max_drawdown"] == -500.0


def test_metrics_are_plain_python_numbers():
    metrics = MetricsCalculator()._calculate_all_metrics(weekly_trades([100.0, -50.0, 75.0]), initial_capital=100_000)
    numpy_values = {k: type(v) for k, v in metrics.items() if isinstance(v, np.generic)}
    # _save_metrics also converts, but the ratios themselves should no longer be numpy scalars.
    assert "sharpe_ratio" not in numpy_values and "sortino_ratio" not in numpy_values
