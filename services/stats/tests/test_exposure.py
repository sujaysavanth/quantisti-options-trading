import math
from datetime import date, datetime, timezone

import pytest

from app import market_spec
from app.services.exposure import portfolio_greeks
from app.services.pricing import greeks

RATE, Q = 0.042, market_spec.DIVIDEND_YIELD
QUOTED = datetime(2026, 10, 9, 18, 0, tzinfo=timezone.utc)
EXPIRY = date(2026, 10, 16)
FORWARD = 6810.0


def leg(strike, kind, iv, bid=10.0, ask=10.4):
    return {"strike": strike, "option_type": kind, "expiry": EXPIRY.isoformat(), "iv": iv, "bid": bid, "ask": ask}


def quote(legs, last=6805.0):
    return {"last_price": last, "quoted_at": QUOTED.isoformat(), "legs": legs,
            "expiries": [{"expiry": EXPIRY.isoformat(), "forward": FORWARD, "quoted_at": QUOTED.isoformat()}]}


def pos(strike, kind, qty, expiry=EXPIRY):
    return {"expiry": expiry.isoformat(), "strike": strike, "option_type": kind, "quantity": qty}


def implied_spot():
    T = market_spec.year_fraction(QUOTED, EXPIRY)
    return FORWARD * math.exp(-(RATE - Q) * T), T


def test_priced_at_the_chains_forward_and_moment():
    q = quote([leg(6800, "CALL", 0.15), leg(6850, "CALL", 0.14)])
    out = portfolio_greeks([pos(6800, "CALL", 1), pos(6850, "CALL", -1)], q, RATE)
    s, T = implied_spot()
    g1, g2 = greeks(s, 6800, T, RATE, 0.15, Q, "CALL"), greeks(s, 6850, T, RATE, 0.14, Q, "CALL")
    long_, short = out["positions"]
    assert long_["delta_per_contract"] == pytest.approx(g1.delta)
    assert long_["delta"] == pytest.approx(100 * g1.delta) and short["delta"] == pytest.approx(-100 * g2.delta)
    assert out["totals"]["delta"] == pytest.approx(100 * (g1.delta - g2.delta))
    assert out["totals"]["vega"] == pytest.approx(100 * (g1.vega - g2.vega))
    assert out["totals"]["theta"] == pytest.approx(100 * (g1.theta - g2.theta))
    pct = 6805.0 / 100
    assert out["totals"]["delta_1pct"] == pytest.approx(100 * (g1.delta - g2.delta) * pct)
    assert out["totals"]["gamma_1pct"] == pytest.approx(0.5 * 100 * (g1.gamma - g2.gamma) * pct ** 2)
    assert out["by_expiry"][0]["expiry"] == EXPIRY.isoformat() and long_["mid"] == pytest.approx(10.2)
    assert long_["days_to_expiry"] == pytest.approx(T * 365)


def test_long_straddle_is_long_gamma_and_vega_short_theta():
    q = quote([leg(6800, "CALL", 0.15), leg(6800, "PUT", 0.16)])
    t = portfolio_greeks([pos(6800, "CALL", 2), pos(6800, "PUT", 2)], q, RATE)["totals"]
    assert t["gamma"] > 0 and t["vega"] > 0 and t["theta"] < 0


def test_missing_iv_uses_the_nearest_strike():
    q = quote([leg(6800, "PUT", 0.16), leg(6600, "PUT", None, bid=0, ask=0.2), leg(6650, "CALL", 0.21)])
    [row] = portfolio_greeks([pos(6600, "PUT", -1)], q, RATE)["positions"]
    assert row["iv"] == 0.21 and row["iv_source"] == "nearest strike 6650 CALL"
    assert row["mid"] is None                                           # no bid: no mid


def test_unpriced_positions_are_listed_not_counted():
    q = quote([leg(6800, "CALL", 0.15)])
    out = portfolio_greeks([pos(6800, "CALL", 1), pos(6800, "CALL", 1, expiry=date(2026, 10, 9))], q, RATE)
    assert len(out["positions"]) == 1 and len(out["unpriced"]) == 1
    assert out["unpriced"][0]["expiry"] == "2026-10-09"
    assert out["totals"]["delta"] == pytest.approx(out["positions"][0]["delta"])


def test_no_positions():
    out = portfolio_greeks([], quote([]), RATE)
    assert out["totals"]["delta"] == 0 and out["positions"] == [] and out["by_expiry"] == []
