from datetime import date, timedelta

import pandas as pd

from app.calculators.volatility_calculator import VolatilityCalculator


def _vix(values, start=date(2026, 9, 1)):
    return pd.DataFrame({"date": [start + timedelta(days=i) for i in range(len(values))], "close": values})


def test_vix_features_use_only_data_up_to_as_of():
    vix = _vix([15, 16, 17, 18, 19, 20, 30, 40])
    out = VolatilityCalculator.calculate_vix_features(vix, as_of=date(2026, 9, 6), hv_20d=12.5)
    assert out == {"vix_close": 20.0, "vix_change_1w": 5.0, "vix_hv_spread": 7.5}


def test_vix_features_degrade_gracefully():
    empty = {"vix_close": None, "vix_change_1w": None, "vix_hv_spread": None}
    assert VolatilityCalculator.calculate_vix_features(None, date(2026, 9, 6), 12.0) == empty
    short = VolatilityCalculator.calculate_vix_features(_vix([15, 16]), date(2026, 9, 6), None)
    assert short == {"vix_close": 16.0, "vix_change_1w": None, "vix_hv_spread": None}
