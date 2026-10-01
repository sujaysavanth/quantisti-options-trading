import asyncio
from datetime import date

import pytest

from app.models.backtest import EntryLogic
from app.services.backtest_engine import BacktestEngine

IRON_CONDOR = [
    {"action": "BUY", "option_type": "P", "strike_offset": -50, "quantity": 1, "leg_order": 1},
    {"action": "SELL", "option_type": "P", "strike_offset": -25, "quantity": 1, "leg_order": 2},
    {"action": "SELL", "option_type": "C", "strike_offset": 25, "quantity": 1, "leg_order": 3},
    {"action": "BUY", "option_type": "C", "strike_offset": 50, "quantity": 1, "leg_order": 4},
]


class FakeMarket:
    """Spot 7651.54 every day; option price = distance-from-spot rule, enough to check the maths."""

    def __init__(self, missing_closes=()):
        self.missing = set(missing_closes)
        self.requests = []

    async def get_spot_price(self, target_date=None):
        return None if target_date in self.missing else 7651.54

    async def get_option_price(self, strike, option_type, target_date=None, expiry_date=None):
        self.requests.append((strike, option_type, target_date, expiry_date))
        return {"price": max(1.0, 40.0 - abs(strike - 7650) * 0.5), "implied_volatility": 0.14}


@pytest.fixture
def engine(monkeypatch):
    eng = BacktestEngine.__new__(BacktestEngine)  # skip DB-bound __init__ wiring
    from app.config import get_settings
    eng.settings = get_settings()
    eng.market_client = FakeMarket()
    saved = {}

    def fake_save(**kwargs):
        saved.update(kwargs)
        return "trade-1"

    async def fake_exit(**kwargs):
        return {"trade_id": kwargs["trade_id"], "pnl": 0.0, "exit_date": kwargs["expiry_date"]}

    monkeypatch.setattr(eng, "_save_trade", fake_save)
    monkeypatch.setattr(eng, "_simulate_exit", fake_exit)
    eng.saved = saved
    return eng


def run(coro):
    return asyncio.run(coro)


def test_iron_condor_uses_spx_strikes_expiry_and_multiplier(engine):
    result = run(engine._execute_trade(
        backtest_id="bt", trade_number=1, entry_date=date(2026, 9, 21), strategy_legs=IRON_CONDOR,
        exit_logic="ON_EXPIRY", stop_loss_pct=None, target_pct=None, max_holding_days=None,
    ))
    assert result is not None, "trade should execute (regression: NameError on expiry_date)"

    legs = engine.saved["trade_legs"]
    assert [(l["action"], l["option_type"], l["strike"]) for l in legs] == [
        ("BUY", "P", 7600.0), ("SELL", "P", 7625.0), ("SELL", "C", 7675.0), ("BUY", "C", 7700.0),
    ]
    assert all(l["quantity"] == 100 for l in legs)
    assert {l["expiry_date"] for l in legs} == {date(2026, 9, 22)}  # Monday entry -> Tuesday daily expiry
    # credit = 100 * (sold 27.5 + 27.5 - bought 15 - 15)
    assert engine.saved["entry_premium"] == pytest.approx(100 * (27.5 * 2 - 15.0 * 2))


def test_calendar_far_leg_is_one_week_out(engine):
    calendar = [
        {"action": "SELL", "option_type": "C", "strike_offset": 0, "quantity": 1, "leg_order": 1, "expiry_offset": 0},
        {"action": "BUY", "option_type": "C", "strike_offset": 0, "quantity": 1, "leg_order": 2, "expiry_offset": 1},
    ]
    run(engine._execute_trade("bt", 1, date(2026, 9, 21), calendar, "ON_EXPIRY", None, None, None))
    assert [l["expiry_date"] for l in engine.saved["trade_legs"]] == [date(2026, 9, 22), date(2026, 9, 29)]


def test_trade_skipped_when_expiry_close_not_loaded(engine):
    engine.market_client = FakeMarket(missing_closes={date(2026, 9, 22)})
    assert run(engine._execute_trade("bt", 1, date(2026, 9, 21), IRON_CONDOR, "ON_EXPIRY", None, None, None)) is None
    assert engine.market_client.requests == []


@pytest.mark.parametrize("logic, expected", [
    (EntryLogic.ON_DATE.value, [date(2026, 11, 23)]),
    (EntryLogic.WEEKLY.value, [date(2026, 11, 23), date(2026, 11, 30)]),
    (EntryLogic.MONTHLY.value, [date(2026, 11, 23), date(2026, 12, 1)]),
])
def test_entry_dates_follow_nyse_calendar(logic, expected):
    eng = BacktestEngine.__new__(BacktestEngine)
    assert eng._generate_trade_dates(date(2026, 11, 22), date(2026, 12, 4), logic) == expected


def test_daily_entries_skip_thanksgiving():
    eng = BacktestEngine.__new__(BacktestEngine)
    days = eng._generate_trade_dates(date(2026, 11, 23), date(2026, 11, 27), EntryLogic.DAILY.value)
    assert date(2026, 11, 26) not in days and len(days) == 4
