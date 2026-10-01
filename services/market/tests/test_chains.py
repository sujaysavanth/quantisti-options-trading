import math
from datetime import date, datetime, timezone

import pytest

from app import market_spec
from app.models.options import OptionType
from app.services.black_scholes import BlackScholesCalculator as BS
from app.services.chains import (
    Quote,
    atm_vol,
    build_snapshot_chain,
    build_synthetic_chain,
    implied_vol,
    infer_forward,
    smile_vol,
)

SPOT, RATE, Q = 7650.0, 0.0425, market_spec.DIVIDEND_YIELD


@pytest.mark.parametrize("strike", [7400.0, 7650.0, 7900.0])
def test_put_call_parity_with_dividends(strike):
    T, vol = 10 / 365, 0.15
    call = BS.call_price(SPOT, strike, T, RATE, vol, Q)
    put = BS.put_price(SPOT, strike, T, RATE, vol, Q)
    assert call - put == pytest.approx(SPOT * math.exp(-Q * T) - strike * math.exp(-RATE * T), abs=1e-8)


def test_smile_has_put_skew():
    T = 7 / 365
    atm = atm_vol(16.0, T)
    forward = SPOT * math.exp((RATE - Q) * T)
    assert smile_vol(atm, 7400, forward, T) > atm > smile_vol(atm, 7800, forward, T)


def test_synthetic_chain_uses_five_point_strikes_and_both_types():
    chain = build_synthetic_chain(SPOT, date(2026, 9, 30), date(2026, 10, 2), 2 / 365, RATE, vix=16.0, strike_range=10)
    strikes = sorted({o.strike for o in chain["options"]})
    assert len(strikes) == 21
    assert all(b - a == market_spec.STRIKE_STEP for a, b in zip(strikes, strikes[1:]))
    assert strikes[10] == market_spec.round_to_strike(SPOT)
    assert {o.option_type for o in chain["options"]} == {OptionType.CALL, OptionType.PUT}
    assert chain["source"] == "synthetic"
    assert all(o.ask >= o.bid >= 0 for o in chain["options"])


def test_zero_dte_chain_has_time_value_before_the_close():
    expiry = date(2026, 9, 28)
    morning = datetime(2026, 9, 28, 14, 0, tzinfo=timezone.utc)  # 10:00 ET
    T = market_spec.year_fraction(market_spec.valuation_time(expiry, now=morning), expiry)
    chain = build_synthetic_chain(SPOT, expiry, expiry, T, RATE, vix=16.0, strike_range=3)
    atm_call = next(o for o in chain["options"] if o.strike == 7650 and o.option_type == OptionType.CALL)
    assert atm_call.time_value > 0
    assert 0.3 < atm_call.greeks.delta < 0.7


def test_implied_vol_round_trips_and_rejects_arbitrage():
    T = 5 / 365
    price = BS.put_price(SPOT, 7600, T, RATE, 0.18, Q)
    assert implied_vol(price, SPOT, 7600, T, RATE, Q, "P") == pytest.approx(0.18, abs=1e-5)
    assert implied_vol(0.0001, SPOT, 7000, T, RATE, Q, "C") is None  # below intrinsic


def _quotes_from_model(spot: float, T: float, vol: float, strikes, spread: float = 0.2):
    quotes = []
    for k in strikes:
        for t, pricer in (("C", BS.call_price), ("P", BS.put_price)):
            mid = pricer(spot, k, T, RATE, vol, Q)
            quotes.append(Quote(k, t, bid=mid - spread / 2, ask=mid + spread / 2, last=None, open_interest=0, volume=10))
    return quotes


def test_snapshot_chain_ignores_stale_spot_and_recovers_vol():
    true_spot, T, vol = 7686.0, 2 / 365, 0.14
    strikes = [7600 + 5 * i for i in range(33)]
    quotes = _quotes_from_model(true_spot, T, vol, strikes)

    # The feed's underlying price is stale by ~35 points, as observed with Yahoo.
    forward = infer_forward(quotes, T, RATE, spot_hint=7651.54)
    assert forward == pytest.approx(true_spot * math.exp((RATE - Q) * T), abs=0.01)

    chain = build_snapshot_chain(quotes, 7651.54, date(2026, 9, 30), date(2026, 10, 2), T, RATE, strike_range=5)
    assert chain["source"] == "snapshot"
    assert chain["spot_price"] == pytest.approx(true_spot, abs=0.01)
    assert chain["atm_iv"] == pytest.approx(vol, abs=1e-3)
    assert len({o.strike for o in chain["options"]}) == 11


def test_snapshot_chain_needs_two_sided_quotes():
    quotes = [Quote(7650, "C", bid=0, ask=1.0, last=None, open_interest=0, volume=0)]
    assert build_snapshot_chain(quotes, 7650, date(2026, 9, 30), date(2026, 10, 2), 2 / 365, RATE, 5) is None
