from datetime import datetime, timezone

from app.services.strategy_builder import build_strategies_from_quote


def leg(option_type, strike, price):
    code = "C" if option_type == "CALL" else "P"
    return {"identifier": f"SPXW261009{code}{strike * 1000:08d}", "strike": float(strike), "option_type": option_type,
            "expiry": "2026-10-09", "bid": price - 0.1, "ask": price + 0.1, "last": price}


QUOTE = {
    "symbol": "SPX", "last_price": 6702.0, "source": "cboe", "delay_minutes": 15,
    "quoted_at": "2026-10-05T20:15:00Z",
    "legs": [leg(t, k, 30.0 - abs(k - 6700) / 10) for k in range(6600, 6805, 25) for t in ("CALL", "PUT")],
}


def test_strategies_carry_quote_context():
    strategies = build_strategies_from_quote(QUOTE)
    assert len(strategies) > 5
    for s in strategies:
        assert (s.spot_price, s.source, s.delay_minutes) == (6702.0, "cboe", 15)
        assert s.quoted_at == datetime(2026, 10, 5, 20, 15, tzinfo=timezone.utc)
    assert {"Long Call", "Iron Condor"} <= {s.name for s in strategies}


def test_old_quotes_without_source_still_work():
    quote = {k: v for k, v in QUOTE.items() if k not in ("source", "delay_minutes", "quoted_at")}
    s = build_strategies_from_quote(quote)[0]
    assert s.source is None and s.quoted_at is None and s.spot_price == 6702.0


def test_no_legs_no_strategies():
    assert build_strategies_from_quote({"symbol": "SPX", "last_price": 6700.0, "legs": []}) == []
