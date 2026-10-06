import math

import pytest

from app.bridge.pricing import bs_price, implied_vol, infer_forward

S, T, R, Q = 6700.0, 7 / 365, 0.04, 0.013


def test_put_call_parity_holds():
    c, p = bs_price(S, 6650, T, R, 0.15, Q, "C"), bs_price(S, 6650, T, R, 0.15, Q, "P")
    assert c - p == pytest.approx(S * math.exp(-Q * T) - 6650 * math.exp(-R * T), abs=1e-9)


@pytest.mark.parametrize("strike,option_type,vol", [(6700, "C", 0.14), (6500, "P", 0.22), (6900, "C", 0.11)])
def test_implied_vol_round_trip(strike, option_type, vol):
    price = bs_price(S, strike, T, R, vol, Q, option_type)
    assert implied_vol(price, S, strike, T, R, Q, option_type) == pytest.approx(vol, abs=1e-5)


def test_impossible_prices_have_no_iv():
    assert implied_vol(0.0, S, 6700, T, R, Q, "C") is None            # below the min-vol price
    assert implied_vol(S, S, 6700, T, R, Q, "C") is None              # a call can't cost the index
    assert implied_vol(None, S, 6700, T, R, Q, "C") is None
    assert implied_vol(10.0, S, 6700, 0, R, Q, "C") is None           # expired


def test_forward_from_parity():
    forward = S * math.exp((R - Q) * T)
    mids = [(k, t, bs_price(S, k, T, R, 0.15, Q, t)) for k in (6680, 6690, 6700, 6710, 6720, 6900) for t in "CP"]
    mids.append((6500, "P", 3.0))                                      # no matching call: ignored
    assert infer_forward(mids, T, R, spot_hint=6700) == pytest.approx(forward, abs=1e-6)
    assert infer_forward([(6700, "C", 10.0)], T, R, 6700) is None
