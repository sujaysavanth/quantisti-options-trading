from datetime import date, datetime, timezone

import pytest

from app import market_spec
from app.services import stress as st
from app.services.exposure import Market
from app.services.pricing import bs_price

RATE, Q = 0.042, market_spec.DIVIDEND_YIELD
QUOTED = datetime(2026, 10, 9, 18, 0, tzinfo=timezone.utc)
EXPIRY = "2026-10-16"


def quote():
    legs = [{"strike": k, "option_type": t, "expiry": EXPIRY, "iv": 0.15, "bid": 10, "ask": 11}
            for k in (6700, 6800, 6850, 6900) for t in ("CALL", "PUT")]
    return {"last_price": 6805.0, "quoted_at": QUOTED.isoformat(), "legs": legs,
            "expiries": [{"expiry": EXPIRY, "forward": 6810.0, "quoted_at": QUOTED.isoformat()}]}


def leg(side, kind, strike, qty=1, entry=10.0, expiry=EXPIRY):
    return {"side": side, "option_type": kind, "strike": strike, "quantity": qty, "entry_price": entry, "expiry": expiry}


def trade(id_, legs):
    return {"id": id_, "legs": legs}


MARKET = Market(quote(), RATE)


def run(trades, scenario):
    legs, _ = st.book(trades, MARKET)
    return st.revalue(legs, len(trades), RATE, scenario)


def test_no_shock_is_zero_and_shocks_revalue_with_black_scholes():
    trades = [trade("a", [leg("BUY", "CALL", 6800), leg("SELL", "CALL", 6850)])]
    assert run(trades, st.Scenario("flat", 0.0, 0.0, 0))[0] == pytest.approx(0.0)
    pnl, marks = run(trades, st.Scenario("up", 0.05, 5.0, 1))
    x = MARKET.inputs(EXPIRY, 6800, "CALL")
    s, T = x.spot * 1.05, x.T - 1 / 365
    expect = 100 * ((bs_price(s, 6800, T, RATE, 0.20, Q, "CALL") - bs_price(x.spot, 6800, x.T, RATE, 0.15, Q, "CALL"))
                    - (bs_price(s, 6850, T, RATE, 0.20, Q, "CALL") - bs_price(x.spot, 6850, x.T, RATE, 0.15, Q, "CALL")))
    assert pnl == pytest.approx(expect)
    assert marks[0][0] == pytest.approx(bs_price(s, 6800, T, RATE, 0.20, Q, "CALL"))


def test_a_call_spread_gains_at_most_its_width():
    trades = [trade("a", [leg("BUY", "CALL", 6800), leg("SELL", "CALL", 6850)])]
    up, _ = run(trades, st.Scenario("+10%", 0.10, 0.0, 0))
    down, _ = run(trades, st.Scenario("-10%", -0.10, 0.0, 0))
    base = sum(100 * s * bs_price(MARKET.inputs(EXPIRY, k, "CALL").spot, k, MARKET.inputs(EXPIRY, k, "CALL").T, RATE,
                                  0.15, Q, "CALL") for k, s in ((6800, 1), (6850, -1)))
    assert up > 0 and down < 0
    assert up + base <= 50 * 100 + 1e-6 and down + base >= -1e-6        # value stays within [0, width]


def test_iv_shift_is_floored_and_an_expiry_passing_settles_at_intrinsic():
    trades = [trade("a", [leg("BUY", "PUT", 6700)])]
    _, marks = run(trades, st.Scenario("vol crush", 0.0, -50.0, 0))
    x = MARKET.inputs(EXPIRY, 6700, "PUT")
    assert marks[0][0] == pytest.approx(bs_price(x.spot, 6700, x.T, RATE, st.MIN_IV, Q, "PUT"))
    _, marks = run(trades, st.Scenario("a week later", -0.03, 0.0, 8))
    assert marks[0][0] == pytest.approx(max(6700 - x.spot * 0.97, 0))


def test_unpriced_legs_add_nothing_and_keep_no_mark():
    trades = [trade("a", [leg("BUY", "CALL", 6800)]), trade("b", [leg("BUY", "CALL", 6800, expiry="2026-10-09")])]
    legs, unpriced = st.book(trades, MARKET)
    pnl, marks = st.revalue(legs, 2, RATE, st.Scenario("up", 0.02, 0, 0))
    assert [u["trade_id"] for u in unpriced] == ["b"] and marks[1] == [None]
    assert pnl == pytest.approx(run([trades[0]], st.Scenario("up", 0.02, 0, 0))[0])


def test_grid_and_history_scenarios():
    g = st.grid()
    assert len(g) == len(st.SPX_MOVES) * len(st.IV_SHIFTS) * len(st.HORIZONS)
    assert g[0].name == "SPX -10%, IV -5 pts, +0d"
    [h] = st.historical([{"date": date(2020, 3, 16), "spx_return": -0.1198, "vix_change": 24.86}])
    assert (h.spx_move, h.iv_shift, h.days, h.date) == (-0.1198, 24.86, 1, "2020-03-16")
    assert st.historical([{"date": date(2011, 1, 3), "spx_return": 0.02, "vix_change": None}])[0].iv_shift == 0.0


def test_capital_request_shape_and_results():
    trades = [trade("a", [leg("BUY", "CALL", 6800, entry=40), leg("SELL", "CALL", 6850, entry=20)])]
    scenarios = [st.Scenario("x", -0.05, 0, 0)]
    body = st.capital_request(trades, 6800.0, scenarios, [[[1.0, 0.5]]])
    assert body["scenarios"] == [{"spot": pytest.approx(6460.0), "marks": [[1.0, 0.5]]}]
    assert body["trades"][0]["legs"][1] == {"strike": 6850.0, "option_type": "CALL", "side": "SELL", "quantity": 1,
                                             "entry_price": 20.0}
    account = {"account_value": 30_000, "capital_held": 2_000, "available": 27_000}
    rows = st.results(scenarios * 2, [-1_500, -900], [2_000, 31_000], account)
    assert rows[0]["available_after"] == 27_000 and not rows[0]["short_of_capital"]
    assert rows[0]["pct_of_account"] == pytest.approx(-0.05) and rows[0]["account_value_after"] == 28_500
    assert rows[1]["available_after"] == -2_000 and rows[1]["short_of_capital"]
    assert st.summary(rows) == {"worst": {"name": "x", "pnl": -1_500}, "best": {"name": "x", "pnl": -900},
                                "margin_calls": 1}
    assert st.results(scenarios, [0.0], [None], account)[0]["available_after"] is None
