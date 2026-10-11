import asyncio
import csv
import io
from datetime import date, datetime, timezone

import pytest

from app.services import positions as views
from app.services import snapshots
from app.services.schedule import Due


def leg(side, kind, strike, entry, current=None, qty=1, expiry="2026-10-16", pnl=0.0, exit_price=None):
    return {"side": side, "option_type": kind, "strike": strike, "entry_price": entry, "current_price": current,
            "quantity": qty, "expiry": expiry, "pnl": pnl, "exit_price": exit_price}


def trade(id_, legs, status="open", pnl=0.0, held=None, created="2026-10-08T15:00:00Z"):
    return {"id": id_, "symbol": "SPX", "nickname": f"t{id_}", "status": status, "created_at": created, "pnl": pnl,
            "capital_held": held, "legs": legs, "closed_at": None, "close_reason": None, "expiry": "2026-10-16"}


def test_opposite_legs_in_different_trades_cancel():
    a = trade("a", [leg("BUY", "CALL", 6800, 40, 45, pnl=500), leg("SELL", "CALL", 6850, 20, 22, pnl=-200)])
    b = trade("b", [leg("BUY", "CALL", 6850, 21, 22, pnl=100)])
    net = views.net_positions([a, b])
    assert [(p["strike"], p["quantity"]) for p in net] == [(6800, 1)]       # the 6850s cancel
    assert net[0]["side"] == "LONG" and net[0]["market_value"] == pytest.approx(4500)
    assert net[0]["avg_entry_price"] == pytest.approx(40)


def test_same_contract_adds_up_with_average_entry_and_skips_closed_trades():
    a = trade("a", [leg("SELL", "PUT", 6700, 10, 8, qty=2, pnl=400)])
    b = trade("b", [leg("SELL", "PUT", 6700, 13, 8, pnl=500)])
    gone = trade("c", [leg("BUY", "PUT", 6700, 5)], status="closed")
    [p] = views.net_positions([a, b, gone])
    assert p["quantity"] == -3 and p["side"] == "SHORT"
    assert p["avg_entry_price"] == pytest.approx((2 * 10 + 13) / 3)
    assert p["market_value"] == pytest.approx(-3 * 8 * 100)
    assert p["unrealised_pnl"] == pytest.approx(900)
    assert p["trade_ids"] == ["a", "b"]


def test_missing_mark_leaves_market_value_empty():
    [p] = views.net_positions([trade("a", [leg("BUY", "CALL", 6900, 5)])])
    assert p["mark"] is None and p["market_value"] is None


def test_csv_has_one_row_per_leg_in_opening_order():
    later = trade("b", [leg("BUY", "PUT", 6600, 3, exit_price=1, pnl=-200)], status="closed", pnl=-200,
                  created="2026-10-09T15:00:00Z")
    first = trade("a", [leg("BUY", "CALL", 6800, 40, exit_price=50, pnl=1000),
                        leg("SELL", "CALL", 6850, 20, exit_price=25, pnl=-500)], status="closed", pnl=500)
    rows = list(csv.DictReader(io.StringIO(views.to_csv(views.trade_rows([later, first])))))
    assert [r["trade_id"] for r in rows] == ["a", "a", "b"]
    assert rows[0]["trade_pnl"] == "500.0" and rows[1]["leg_pnl"] == "-500.0" and rows[2]["exit_price"] == "1"


def test_snapshot_figures_come_from_one_set_of_marks():
    slot = Due("close", datetime(2026, 10, 9, 20, tzinfo=timezone.utc), date(2026, 10, 9))
    trades = [trade("a", [leg("BUY", "CALL", 6800, 40, 45)], pnl=500, held=4000),
              trade("b", [leg("BUY", "PUT", 6600, 3)], status="closed", pnl=-200)]
    snap = snapshots.build(slot, 30_000, trades, 6812.5, slot.taken_at)
    assert (snap.realised_pnl, snap.unrealised_pnl, snap.capital_held) == (-200, 500, 4000)
    assert snap.account_value == 30_300 and snap.available == 30_000 - 200 - 4000
    assert (snap.open_trades, snap.closed_trades) == (1, 1) and len(snap.positions) == 1


class FakeStore:
    def __init__(self):
        self.saved = []

    def exists(self, kind, taken_at):
        return any(s.kind == kind and s.taken_at == taken_at for s in self.saved)

    def save(self, snap):
        self.saved.append(snap)
        return True


class FakeSimulator:
    def __init__(self, up=True):
        self.up, self.calls = up, 0

    async def account(self):
        self.calls += 1
        return {"starting_balance": 30_000} if self.up else None

    async def orders(self):
        return [] if self.up else None


class FakeStream:
    async def spot(self, symbol="SPX"):
        return 6800.0


def test_take_due_stores_once_per_slot_and_retries_when_the_simulator_is_down():
    store, now = FakeStore(), datetime(2026, 10, 9, 14, 3, tzinfo=timezone.utc)
    assert asyncio.run(snapshots.take_due(store, FakeSimulator(up=False), FakeStream(), now)) is None
    sim = FakeSimulator()
    snap = asyncio.run(snapshots.take_due(store, sim, FakeStream(), now))
    assert snap.kind == "intraday" and snap.taken_at == datetime(2026, 10, 9, 14, 0, tzinfo=timezone.utc)
    assert asyncio.run(snapshots.take_due(store, sim, FakeStream(), now)) is None     # already stored: no call
    assert sim.calls == 1 and len(store.saved) == 1
    assert asyncio.run(snapshots.take_due(store, sim, FakeStream(), datetime(2026, 10, 10, 15, tzinfo=timezone.utc))) is None
