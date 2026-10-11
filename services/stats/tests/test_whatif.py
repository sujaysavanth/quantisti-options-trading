import numpy as np
import pytest

from app.services import whatif
from app.services.exposure import Market

from .test_stress import EXPIRY, RATE, leg, quote, trade

MARKET = Market(quote(), RATE)


def cand(side, kind, strike, qty=1, expiry=EXPIRY):
    return {"side": side, "option_type": kind, "strike": strike, "quantity": qty, "expiry": expiry}


def test_candidate_fills_at_the_mid():
    t = whatif.candidate_trade([cand("BUY", "CALL", 6800), cand("SELL", "CALL", 6850)], MARKET)
    assert t["id"] == "candidate" and [leg["entry_price"] for leg in t["legs"]] == [10.5, 10.5]   # (10 + 11) / 2
    assert {leg["price_source"] for leg in t["legs"]} == {"mid"}


def test_candidate_off_the_quote_is_an_error():
    t = whatif.candidate_trade([cand("BUY", "CALL", 6800, expiry="2026-10-09")], MARKET)
    assert "errors" in t and "2026-10-09" in t["errors"][0]


def test_hedging_reduces_delta_and_risk():
    rng = np.random.default_rng(5)
    moves = list(zip(rng.normal(0, 0.01, 300), rng.normal(0, 1.0, 300)))
    book = [trade("a", [leg("BUY", "CALL", 6800, qty=2)])]
    hedge = whatif.candidate_trade([cand("BUY", "PUT", 6800, qty=2)], MARKET)
    before = whatif.measure(book, MARKET, RATE, moves, 0.01, [])
    after = whatif.measure([*book, hedge], MARKET, RATE, moves, 0.01, [])
    assert abs(after["delta"]) < abs(before["delta"])                       # long calls + long puts: near flat
    assert after["gamma_1pct"] > before["gamma_1pct"] > 0
    assert after["theta"] < before["theta"] < 0
    assert after["worst_stress"] > before["worst_stress"]                   # a straddle's worst case is milder
    assert after["worst_day"] is None
    rows = whatif.compare(before, after)
    assert [r["metric"] for r in rows] == list(whatif.METRICS)
    assert rows[0]["change"] == pytest.approx(after["delta"] - before["delta"])


def test_empty_book_before():
    rng = np.random.default_rng(6)
    moves = list(zip(rng.normal(0, 0.01, 100), rng.normal(0, 1.0, 100)))
    before = whatif.measure([], MARKET, RATE, moves, None, [])
    assert before["delta"] == 0 and before["var99"] == 0 and before["worst_stress"] == 0


def test_capital_check():
    assert whatif.capital_check(2_000, "max loss", 27_000) == {"required": 2_000, "basis": "max loss",
                                                               "available_now": 27_000, "available_after": 25_000,
                                                               "fits": True}
    assert whatif.capital_check(117_000, "margin", 27_000)["fits"] is False
    assert whatif.capital_check(None, None, 27_000)["fits"] is None
