import math
from datetime import date

import pandas as pd
import pytest

from app.dataset.oi_levels import oi_levels
from app.dataset.options import (option_features, pc_volume_ratio, preferred_source, skew_25d,
                                 straddle_sigma_week)

A = date(2020, 1, 10)


def chain(rows, source="optionsdx", spot=3265.0, anchor=A):
    """rows: (type, strike, bid, ask, iv, delta, volume, open_interest)."""
    cols = ["option_type", "strike", "bid", "ask", "vendor_iv", "vendor_delta", "volume", "open_interest"]
    df = pd.DataFrame(rows, columns=cols)
    df["underlying_price"], df["source"], df["anchor_date"] = spot, source, anchor
    return df


# Shaped like the real 2020-01-10 chain for 2020-01-17 (25-delta put 9.14% IV, call 7.88%).
JAN = chain([
    ("P", 3235, 6.49, 6.70, 0.0914, -0.2495, 216, None), ("P", 3265, 14.0, 14.4, 0.085, -0.48, 900, None),
    ("C", 3265, 15.0, 15.4, 0.080, 0.52, 700, None), ("C", 3290, 5.59, 5.90, 0.0788, 0.2531, 300, None),
])


def test_straddle_and_atm_iv():
    sigma = straddle_sigma_week(JAN)
    assert sigma == pytest.approx((14.2 + 15.2) / 3265 / math.sqrt(2 / math.pi))
    feats = option_features(JAN, {A: 5}).iloc[0]
    assert feats["atm_iv_1w"] == pytest.approx(sigma * math.sqrt(252 / 5))
    assert feats["source"] == "optionsdx"


def test_skew_uses_the_25_delta_wings():
    assert skew_25d(JAN) == pytest.approx(0.0914 - 0.0788)
    far = chain([("P", 3000, 1, 1.1, 0.2, -0.02, 1, None), ("C", 3290, 5.6, 5.9, 0.08, 0.25, 1, None)])
    assert skew_25d(far) is None                                           # no put anywhere near 25 delta


def test_put_call_volume_ratio_needs_enough_volume():
    assert pc_volume_ratio(JAN) == pytest.approx((216 + 900) / (700 + 300))
    assert pc_volume_ratio(JAN.assign(volume=[5, 5, 5, 5])) is None


def test_one_source_per_anchor_cboe_first():
    both = pd.concat([JAN, JAN.assign(source="yahoo"), JAN.assign(source="cboe")])
    assert preferred_source(both) == "cboe"
    assert option_features(both, {A: 5}).iloc[0]["source"] == "cboe"


def test_open_interest_levels():
    q = chain([
        ("P", 7700, 8, 8.4, 0.151, -0.17, 0, 4534), ("P", 7750, 17, 17.3, 0.135, -0.32, 0, 3576),
        ("P", 7800, 35, 36, 0.122, -0.56, 0, 1662), ("C", 7800, 24, 25, 0.122, 0.44, 0, 5816),
        ("C", 7850, 7, 7.4, 0.113, 0.20, 0, 9336), ("C", 7900, 1.4, 1.5, 0.110, 0.05, 0, 9900),
    ], source="cboe", spot=7818.93)
    lv = oi_levels(q, years_to_expiry=3 / 365)
    assert (lv["put_wall"], lv["call_wall"]) == (7700, 7900)
    assert lv["max_pain"] in (7750, 7800)
    legs = list(zip(q["option_type"], q["strike"], q["open_interest"]))
    payout = {s: sum(oi * max(s - k, 0) for t, k, oi in legs if t == "C")
              + sum(oi * max(k - s, 0) for t, k, oi in legs if t == "P")
              for s in (7700, 7750, 7800, 7850, 7900)}
    assert lv["max_pain"] == min(payout, key=payout.get)
    assert lv["contracts"] == 4534 + 3576 + 1662 + 5816 + 9336 + 9900
    assert lv["gex"] > 0                                                   # more call gamma near spot than put


def test_no_open_interest_no_levels():
    assert oi_levels(JAN, years_to_expiry=7 / 365) is None                 # OptionsDX: OI is unknown
