import math

import pytest

from app.services.pricing import bs_price, greeks


def test_textbook_call():
    # Hull, Options Futures and Other Derivatives: S=49, K=50, r=5%, vol=20%, T=20 weeks, no dividend.
    g = greeks(49, 50, 0.3846, 0.05, 0.20, 0.0, "CALL")
    assert g.price == pytest.approx(2.40, abs=0.01)
    assert g.delta == pytest.approx(0.522, abs=0.001)
    assert g.gamma == pytest.approx(0.066, abs=0.001)
    assert g.vega * 100 == pytest.approx(12.1, abs=0.1)          # per 1.00 of vol
    assert g.theta * 365 == pytest.approx(-4.31, abs=0.01)       # per year


@pytest.mark.parametrize("kind", ["CALL", "PUT"])
@pytest.mark.parametrize("strike", [6500, 6800, 7100])
def test_greeks_match_finite_differences(kind, strike):
    S, T, r, v, q = 6800.0, 9 / 365, 0.042, 0.16, 0.013
    g = greeks(S, strike, T, r, v, q, kind)
    p = lambda s=S, t=T, vol=v: bs_price(s, strike, t, r, vol, q, kind)   # noqa: E731
    h = 0.5
    assert g.delta == pytest.approx((p(S + h) - p(S - h)) / (2 * h), abs=1e-4)
    assert g.gamma == pytest.approx((p(S + h) - 2 * p() + p(S - h)) / h ** 2, abs=1e-5)
    assert g.vega == pytest.approx((p(vol=v + 1e-4) - p(vol=v - 1e-4)) / 2e-4 / 100, rel=1e-4)
    # Theta is the instantaneous rate per day; a whole day's decay differs by up to ~15% this near expiry.
    dt = 1e-6
    assert g.theta == pytest.approx((p(t=T - dt) - p()) / dt / 365, rel=1e-3)
    assert g.theta == pytest.approx(p(t=T - 1 / 365) - p(), rel=0.2)


def test_put_call_relations():
    S, K, T, r, v, q = 6800.0, 6750.0, 30 / 365, 0.042, 0.18, 0.013
    c, p = greeks(S, K, T, r, v, q, "CALL"), greeks(S, K, T, r, v, q, "PUT")
    assert c.price - p.price == pytest.approx(S * math.exp(-q * T) - K * math.exp(-r * T))
    assert c.delta - p.delta == pytest.approx(math.exp(-q * T))
    assert c.gamma == pytest.approx(p.gamma) and c.vega == pytest.approx(p.vega)


def test_expired_option_is_intrinsic_with_no_time_greeks():
    g = greeks(6800, 6750, 0.0, 0.04, 0.2, 0.013, "CALL")
    assert (g.price, g.delta, g.gamma, g.vega, g.theta) == (50, 1.0, 0.0, 0.0, 0.0)
    assert greeks(6800, 6750, 0.0, 0.04, 0.2, 0.013, "PUT").delta == 0.0
