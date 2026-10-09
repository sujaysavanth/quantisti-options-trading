import asyncio
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from app.routers import paper
from app.services import paper_settlement as rules
from app.services.paper_settlement import Position
from app.services.paper_store import StoredLeg, StoredTrade


def P(kind, side, strike, price, qty=1):
    return Position(strike, kind, side, qty, price)


def test_settles_30_minutes_before_the_close():
    assert rules.settle_time(date(2026, 10, 9)) == datetime(2026, 10, 9, 19, 30, tzinfo=timezone.utc)      # 15:30 EDT
    assert rules.settle_time(date(2026, 11, 27)) == datetime(2026, 11, 27, 17, 30, tzinfo=timezone.utc)    # early close 13:00 EST


def test_settlement_mode_by_time():
    expiry = date(2026, 10, 9)
    assert rules.settlement_mode(expiry, datetime(2026, 10, 9, 19, 29, tzinfo=timezone.utc)) is None
    assert rules.settlement_mode(expiry, datetime(2026, 10, 9, 19, 30, tzinfo=timezone.utc)) == "quote"
    assert rules.settlement_mode(expiry, datetime(2026, 10, 9, 20, 5, tzinfo=timezone.utc)) == "close"


def test_defined_risk_holds_its_max_loss():
    debit = [P("CALL", "BUY", 6800, 40), P("CALL", "SELL", 6850, 20)]
    assert rules.capital_held(debit, 6800) == {"amount": pytest.approx(2000), "basis": "max loss"}
    credit = [P("PUT", "SELL", 6800, 30), P("PUT", "BUY", 6750, 12)]
    assert rules.capital_held(credit, 6800)["amount"] == pytest.approx(50 * 100 - 18 * 100)
    assert rules.capital_held([P("PUT", "BUY", 6800, 25)], 6800)["amount"] == pytest.approx(2500)


def test_uncovered_shorts_use_the_cboe_rule():
    # Short 1 put 6700 at 10 with SPX 6800: 100 OTM; 15% x 6800 - 100 = 920 vs 10% x 6700 = 670 -> 10 + 920 = 930 pts.
    naked = P("PUT", "SELL", 6700, 10)
    assert rules.naked_requirement(naked, 6800) == pytest.approx(93_000)
    held = rules.capital_held([naked], 6800)
    assert held["basis"] == "margin" and held["amount"] == pytest.approx(93_000 - 1_000)     # premium received is credited
    assert rules.max_loss([P("CALL", "SELL", 6900, 15)]) is None                            # unlimited


def test_ratio_spread_covers_the_dangerous_short_first():
    # Long 1 x 6800P, short 2 x 6750P: one short is covered (a 50-wide spread), the other is naked.
    legs = [P("PUT", "BUY", 6800, 30), P("PUT", "SELL", 6750, 15, qty=2)]
    held = rules.capital_held(legs, 6800)
    spread_loss = rules.max_loss([P("PUT", "BUY", 6800, 30), P("PUT", "SELL", 6750, 15)])
    naked = rules.naked_requirement(P("PUT", "SELL", 6750, 15), 6800) - 1_500
    assert held == {"amount": pytest.approx(spread_loss + naked), "basis": "margin"}


def test_realised_pnl():
    legs = [P("CALL", "BUY", 6800, 40), P("CALL", "SELL", 6850, 20)]
    assert rules.realised([40, 20], [55, 25], legs) == pytest.approx((15 - 5) * 100)


class FakeStore:
    def __init__(self, trade, close=None):
        self.trade, self.close, self.closed = trade, close, None

    def list_trades(self, status=None):
        return [self.trade] if self.trade.status == "open" else []

    def close_on(self, day, symbol="SPX"):
        return self.close

    def close_trade(self, trade_id, exits, reason, closed_at):
        self.closed = (exits, reason)
        self.trade.status = "closed"
        return True


class FakeQuotes:
    def __init__(self, quote):
        self.quote = quote

    async def get_quote(self, symbol):
        return self.quote


def make_trade():
    legs = [StoredLeg("SPXW261009C06800000", 6800.0, "CALL", "2026-10-09", 1, "BUY", 40.0),
            StoredLeg("SPXW261009C06850000", 6850.0, "CALL", "2026-10-09", 1, "SELL", 20.0)]
    return StoredTrade(uuid4(), "SPX", "test", datetime(2026, 10, 9, 14, 0, tzinfo=timezone.utc), legs)


def test_settles_at_the_mids_at_1530():
    quote = {"last_price": 6830.0, "legs": [{"identifier": "SPXW261009C06800000", "bid": 31.0, "ask": 33.0},
                                            {"identifier": "SPXW261009C06850000", "bid": 2.0, "ask": 3.0}]}
    store = FakeStore(make_trade())
    assert asyncio.run(paper.settle_due(store, FakeQuotes(quote), datetime(2026, 10, 9, 19, 0, tzinfo=timezone.utc))) == 0
    assert asyncio.run(paper.settle_due(store, FakeQuotes(quote), datetime(2026, 10, 9, 19, 31, tzinfo=timezone.utc))) == 1
    assert store.closed[0] == [32.0, 2.5] and "30 min before" in store.closed[1]


def test_a_missed_settlement_uses_the_official_close():
    store = FakeStore(make_trade(), close=6860.0)
    n = asyncio.run(paper.settle_due(store, FakeQuotes({}), datetime(2026, 10, 10, 15, 0, tzinfo=timezone.utc)))
    assert n == 1 and store.closed[0] == [60.0, 10.0] and "intrinsic" in store.closed[1]


def test_waits_for_the_official_close_if_it_has_not_arrived():
    store = FakeStore(make_trade(), close=None)
    assert asyncio.run(paper.settle_due(store, FakeQuotes({}), datetime(2026, 10, 10, 15, 0, tzinfo=timezone.utc))) == 0


def test_max_loss_is_fixed_at_entry_but_naked_margin_follows_the_market():
    spread = [Position(6800, "CALL", "BUY", 1, 40, mark=60), Position(6850, "CALL", "SELL", 1, 20, mark=30)]
    assert rules.capital_held(spread, 6830)["amount"] == pytest.approx(2000)          # the debit paid, not today's
    naked = Position(6700, "PUT", "SELL", 1, 10, mark=25)                              # the put has gained value
    assert rules.capital_held([naked], 6800)["amount"] == pytest.approx((25 + 920) * 100 - 1_000)
