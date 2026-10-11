import asyncio
from datetime import date

import pytest
from pydantic import ValidationError

from app.models.backtest import BacktestCreate
from app.services import backtest_engine as be
from app.services.backtest_engine import BacktestEngine, exit_check_days, exit_rule_hit, exit_value

# A 6800/6850 call spread bought for 20 points ($2,000 for 1 lot), expiring Friday 2026-10-16, entered Monday.
ENTRY, EXPIRY = date(2026, 10, 12), date(2026, 10, 16)
LEGS = [{"action": "BUY", "option_type": "C", "strike": 6800.0, "expiry_date": EXPIRY, "quantity": 100, "entry_price": 30.0},
        {"action": "SELL", "option_type": "C", "strike": 6850.0, "expiry_date": EXPIRY, "quantity": 100, "entry_price": 10.0}]
DEBIT = -2_000.0


def test_rules_in_order():
    assert exit_rule_hit(-1_000, DEBIT, 1, 50, None, None) == "STOP_LOSS"           # lost half the debit
    assert exit_rule_hit(-999, DEBIT, 1, 50, None, None) is None
    assert exit_rule_hit(2_000, DEBIT, 1, None, 100, None) == "TARGET"              # doubled
    assert exit_rule_hit(-1_500, DEBIT, 3, 50, 100, 3) == "STOP_LOSS"               # stop beats the clock
    assert exit_rule_hit(0, DEBIT, 3, 50, 100, 3) == "MAX_DAYS"
    assert exit_rule_hit(400, 800.0, 1, None, 50, None) == "TARGET"                 # credit: half the $800 earned
    assert exit_rule_hit(-5, 0.0, 1, 50, 50, None) is None                          # no premium: % rules can't apply


def test_check_days_are_sessions_strictly_between():
    assert exit_check_days(ENTRY, EXPIRY) == [date(2026, 10, 13), date(2026, 10, 14), date(2026, 10, 15)]
    assert exit_check_days(date(2026, 11, 25), date(2026, 11, 30)) == [date(2026, 11, 27)]     # Thanksgiving, weekend


def test_exit_value_signs():
    assert exit_value(LEGS, [45.0, 20.0]) == pytest.approx(4_500 - 2_000)


class ChainMarket:
    """Daily closes for the spread: day -> (6800 C price, 6850 C price); spot 6800 every day."""

    def __init__(self, marks):
        self.marks, self.chain_calls = marks, []

    async def get_option_chain(self, target_date=None, expiry_date=None, strike_range=10):
        self.chain_calls.append(target_date)
        if target_date not in self.marks:
            return None
        lo, hi = self.marks[target_date]
        return {"options": [{"strike": 6800.0, "option_type": "C", "price": lo},
                            {"strike": 6850.0, "option_type": "C", "price": hi}]}

    async def get_spot_price(self, target_date=None):
        return 6900.0 if target_date == EXPIRY else 6800.0

    async def get_option_price(self, **kwargs):
        raise AssertionError("not used: both legs expire together")


@pytest.fixture
def engine(monkeypatch):
    eng = BacktestEngine.__new__(BacktestEngine)
    written = {}

    class Conn:
        def cursor(self):
            class C:
                def execute(self, sql, args):
                    written["args"] = args
                def close(self):
                    pass
            return C()

        def commit(self):
            pass

    monkeypatch.setattr(be, "get_db_connection", lambda: Conn())
    monkeypatch.setattr(be, "return_db_connection", lambda conn: None)
    eng.written = written
    return eng


def run_exit(eng, marks, **rules):
    eng.market_client = ChainMarket(marks)
    params = {"stop_loss_pct": None, "target_pct": None, "max_holding_days": None, **rules}
    return asyncio.run(eng._simulate_exit(trade_id="t", entry_date=ENTRY, expiry_date=EXPIRY, entry_premium=DEBIT,
                                          trade_legs=LEGS, exit_logic="ON_EXPIRY", **params))


MARKS = {date(2026, 10, 13): (32.0, 11.0), date(2026, 10, 14): (50.0, 15.0), date(2026, 10, 15): (12.0, 2.0)}


def test_target_closes_early_at_that_close(engine):
    out = run_exit(engine, MARKS, target_pct=50)                    # Wednesday: 35 pts = +$1,500 >= $1,000
    assert (out["exit_date"], out["exit_reason"]) == (date(2026, 10, 14), "TARGET")
    assert out["pnl"] == pytest.approx(-2_000 + 3_500)


def test_stop_loss_skips_unpriced_days(engine):
    marks = {**MARKS, date(2026, 10, 14): None}
    marks = {d: m for d, m in marks.items() if m}
    out = run_exit(engine, marks, stop_loss_pct=40)                 # Thursday: 10 pts = -$1,000 <= -$800
    assert (out["exit_date"], out["exit_reason"]) == (date(2026, 10, 15), "STOP_LOSS")
    assert out["pnl"] == pytest.approx(-1_000)


def test_max_days(engine):
    out = run_exit(engine, MARKS, max_holding_days=2)
    assert (out["exit_date"], out["exit_reason"]) == (date(2026, 10, 14), "MAX_DAYS")


def test_no_rule_fires_settles_at_expiry_intrinsic(engine):
    out = run_exit(engine, MARKS, target_pct=500)
    assert (out["exit_date"], out["exit_reason"]) == (EXPIRY, "EXPIRY")
    assert out["pnl"] == pytest.approx(-2_000 + 50 * 100)          # SPX 6900: the spread is worth its full width


def test_no_rules_no_extra_requests(engine):
    out = run_exit(engine, MARKS)
    assert out["exit_reason"] == "EXPIRY" and engine.market_client.chain_calls == []


def test_exit_logic_needs_its_setting():
    base = {"strategy_id": "00000000-0000-0000-0000-000000000001", "name": "x",
            "start_date": "2026-01-01", "end_date": "2026-02-01"}
    with pytest.raises(ValidationError):
        BacktestCreate(**base, exit_logic="STOP_LOSS")
    assert BacktestCreate(**base, exit_logic="TARGET", target_pct=50).target_pct == 50
    assert BacktestCreate(**base, stop_loss_pct=50).exit_logic.value == "ON_EXPIRY"
