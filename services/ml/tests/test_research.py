"""Chronos-2 contender. Skipped unless the optional research install is present (it is not in CI)."""

import numpy as np
import pytest

pytest.importorskip("chronos")

from app.evaluation import walkforward  # noqa: E402
from app.forecasting.chronos2 import COVARIATES, Chronos2Forecaster  # noqa: E402
from tests.test_evaluation import synthetic_rows  # noqa: E402


def test_each_context_ends_at_its_own_anchor_and_uses_no_labels():
    _, data = synthetic_rows()
    train, test = walkforward.split(data, 2025)
    f = Chronos2Forecaster(COVARIATES, name="chronos2_cov")
    f.fit(train, None)
    inputs = f.inputs(test.drop(columns=walkforward.LABEL_COLUMNS))
    for i, item in enumerate(inputs):
        expected = len(train) + i + 1                                      # every earlier week, plus this one
        assert len(item["target"]) == expected
        assert item["target"][-1] == pytest.approx(test["ret_1w"].iloc[i])  # this week's own return, a feature
        assert set(item["past_covariates"]) == set(COVARIATES)
    assert not set(walkforward.LABEL_COLUMNS) & set(f.history.columns)


def test_forecasts_are_ordered_quantiles():
    _, data = synthetic_rows()
    train, test = walkforward.split(data, 2025)
    f = Chronos2Forecaster()
    f.fit(train, None)
    q = f.predict(test.head(5).drop(columns=walkforward.LABEL_COLUMNS), None)
    assert q.shape == (5, 5) and np.isfinite(q).all() and (np.diff(q, axis=1) >= 0).all()
    assert 0.005 < np.median(q[:, 3] - q[:, 1]) < 0.15                      # a sane weekly 80% band
