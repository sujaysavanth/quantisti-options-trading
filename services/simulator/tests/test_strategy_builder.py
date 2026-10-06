from datetime import datetime, timezone

from app.routers.paper import _match_quote_leg, _price_from_quote
from app.services.quote_pricing import leg_price, select_expiry
from app.services.strategy_builder import build_strategies_from_quote


def leg(option_type, strike, price, expiry="2026-10-09"):
    code = "C" if option_type == "CALL" else "P"
    return {"identifier": f"SPXW{expiry[2:].replace('-', '')}{code}{strike * 1000:08d}", "strike": float(strike),
            "option_type": option_type, "expiry": expiry, "bid": price - 0.1, "ask": price + 0.1, "last": price - 5}


def chain(expiry, base):
    return [leg(t, k, base - abs(k - 6700) / 10, expiry) for k in range(6600, 6805, 25) for t in ("CALL", "PUT")]


QUOTE = {
    "symbol": "SPX", "last_price": 6702.0, "source": "cboe", "delay_minutes": 15,
    "quoted_at": "2026-10-05T20:15:00Z", "default_expiry": "2026-10-09",
    "legs": chain("2026-10-07", 20.0) + chain("2026-10-09", 30.0),
}


def test_strategies_carry_quote_context():
    strategies = build_strategies_from_quote(QUOTE)
    assert len(strategies) > 5
    for s in strategies:
        assert (s.spot_price, s.source, s.delay_minutes, s.expiry) == (6702.0, "cboe", 15, "2026-10-09")
        assert s.quoted_at == datetime(2026, 10, 5, 20, 15, tzinfo=timezone.utc)
    assert {"Long Call", "Iron Condor"} <= {s.name for s in strategies}


def test_expiry_selects_its_own_legs():
    strategies = build_strategies_from_quote(QUOTE, "2026-10-07")
    assert {leg.expiry for s in strategies for leg in s.legs} == {"2026-10-07"}
    long_call = next(s for s in strategies if s.name == "Long Call")
    assert long_call.net_premium == 20.0                       # the 10-07 ATM mid, not the 10-09 one
    assert build_strategies_from_quote(QUOTE, "2026-12-18") == []


def test_select_expiry():
    assert select_expiry(QUOTE) == "2026-10-09"                 # the quote's default
    assert select_expiry(QUOTE, "2026-10-07") == "2026-10-07"
    assert select_expiry(QUOTE, "2026-12-18") is None
    assert select_expiry({**QUOTE, "default_expiry": None}) == "2026-10-07"   # older publishers: nearest


def test_prices_use_the_mid_not_a_stale_last_trade():
    assert leg_price({"bid": 26.9, "ask": 27.3, "last": 24.6}) == 27.1
    assert leg_price({"bid": None, "ask": 0.05, "last": None}) == 0.05      # one-sided quote
    assert leg_price({"bid": 0, "ask": 0, "last": 3.2}) == 3.2
    assert leg_price(None) == 0.0
    long_call = next(s for s in build_strategies_from_quote(QUOTE) if s.name == "Long Call")
    assert long_call.legs[0].price == 30.0                      # mid of 29.9 / 30.1; the last trade says 25


def test_paper_trades_price_at_the_mid():
    from app.models.paper import PaperLegInput
    wanted = PaperLegInput(strike=6700, option_type="CALL", expiry="2026-10-07", quantity=1, side="BUY")
    matched = _match_quote_leg(QUOTE, wanted)
    assert matched["expiry"] == "2026-10-07" and _price_from_quote(matched) == 20.0


def test_old_quotes_without_source_still_work():
    quote = {k: v for k, v in QUOTE.items() if k not in ("source", "delay_minutes", "quoted_at", "default_expiry")}
    s = build_strategies_from_quote(quote)[0]
    assert s.source is None and s.quoted_at is None and s.spot_price == 6702.0 and s.expiry == "2026-10-07"


def test_no_legs_no_strategies():
    assert build_strategies_from_quote({"symbol": "SPX", "last_price": 6700.0, "legs": []}) == []
