from datetime import date, datetime, timedelta, timezone

import pytest

from app.bridge.pricing import bs_price
from app.bridge.state import BridgeState, occ_symbol
from app.market_spec import year_fraction
from app.producers.envelope import BarPayload, ChainPayload, DailyPayload, QuotePayload, wrap

QUOTED = datetime(2026, 10, 5, 20, 15, tzinfo=timezone.utc)      # Monday 16:15 ET
SPOT, VOL, RATE = 6700.0, 0.15, 0.04


def chain_env(expiry, quoted_at=QUOTED, bid_shift=0.0):
    T = year_fraction(quoted_at, expiry)
    quotes = []
    for k in range(6650, 6755, 5):
        for t in "CP":
            mid = bs_price(SPOT, k, T, RATE, VOL, 0.013, t) + bid_shift
            quotes.append(QuotePayload(option_type=t, strike=k, bid=round(mid - 0.05, 4), ask=round(mid + 0.05, 4), last=mid))
    payload = ChainPayload(symbol="SPX", expiry=expiry, session_date=date(2026, 10, 5), quoted_at=quoted_at,
                           underlying_price=SPOT, quotes=quotes)
    return wrap("chain.v1", "cboe", 15, payload)


def rate_env():
    return wrap("daily.v1", "fred", 0, DailyPayload(dataset="rates", symbol="DGS3MO", date=date(2026, 10, 2), rate=RATE))


def bar_env(ts, close=6705.0):
    return wrap("bars.v1", "yahoo", 15, BarPayload(symbol="SPX", interval="1m", ts=ts, open=close, high=close, low=close,
                                                   close=close, volume=0))


def state_with(*envs):
    s = BridgeState(min_dte=1)
    for e in envs:
        s.apply(e)
    return s


def test_occ_symbol():
    assert occ_symbol(date(2026, 10, 16), "C", 7650) == "SPXW261016C07650000"
    assert occ_symbol(date(2026, 10, 16), "P", 6702.5) == "SPXW261016P06702500"


def test_quote_has_every_live_expiry_and_a_default():
    s = state_with(rate_env(), chain_env(date(2026, 10, 5)), chain_env(date(2026, 10, 6)), chain_env(date(2026, 10, 9)))
    quote = s.to_quote(now=QUOTED + timedelta(minutes=1))
    assert date(2026, 10, 5) not in s.chains                       # settled at today's close: forgotten
    assert {leg["expiry"] for leg in quote["legs"]} == {"2026-10-06", "2026-10-09"}
    assert quote["default_expiry"] == "2026-10-06"                 # nearest at least 1 day out
    assert [(e["expiry"], e["dte"]) for e in quote["expiries"]] == [("2026-10-06", 1), ("2026-10-09", 4)]
    for e in quote["expiries"]:                                     # each expiry priced on its own forward
        assert e["atm_iv"] == pytest.approx(VOL, abs=0.003)
    assert (quote["source"], quote["delay_minutes"], quote["symbol"]) == ("cboe", 15, "SPX")
    leg = next(l for l in quote["legs"] if l["strike"] == 6700 and l["option_type"] == "CALL" and l["expiry"] == "2026-10-06")
    assert leg["identifier"] == "SPXW261006C06700000"
    assert leg["iv"] == pytest.approx(VOL, abs=0.003)               # recomputed from the mid
    assert quote["spot_iv"] == pytest.approx(VOL, abs=0.003)


def test_legs_carry_delta_volume_and_open_interest():
    quote = state_with(rate_env(), chain_env(date(2026, 10, 9))).to_quote(now=QUOTED)
    calls = [l for l in quote["legs"] if l["option_type"] == "CALL"]
    puts = [l for l in quote["legs"] if l["option_type"] == "PUT"]
    assert all(0 <= l["delta"] <= 1 for l in calls) and all(-1 <= l["delta"] <= 0 for l in puts)
    assert calls[0]["delta"] > calls[-1]["delta"]                    # lower strike call = higher delta
    assert {"volume", "open_interest"} <= set(calls[0])


def test_newer_messages_win_and_stale_ones_are_ignored():
    s = state_with(chain_env(date(2026, 10, 9)))
    assert s.apply(chain_env(date(2026, 10, 9), quoted_at=QUOTED + timedelta(minutes=2), bid_shift=1.0))
    assert not s.apply(chain_env(date(2026, 10, 9), quoted_at=QUOTED - timedelta(hours=1)))
    assert s.chains[date(2026, 10, 9)].payload.quoted_at == QUOTED + timedelta(minutes=2)
    assert s.apply(bar_env(QUOTED)) and not s.apply(bar_env(QUOTED - timedelta(minutes=1)))


def test_last_price_prefers_the_newer_of_bar_and_chain():
    later_bar = state_with(chain_env(date(2026, 10, 9)), bar_env(QUOTED + timedelta(minutes=1), close=6711.0))
    assert later_bar.to_quote(now=QUOTED + timedelta(minutes=2))["last_price"] == 6711.0
    older_bar = state_with(chain_env(date(2026, 10, 9)), bar_env(QUOTED - timedelta(minutes=30), close=6690.0))
    assert older_bar.to_quote(now=QUOTED + timedelta(minutes=2))["last_price"] == SPOT


def test_only_one_minute_bars_set_the_price():
    s = state_with(bar_env(QUOTED, close=6705.0))
    hourly = wrap("bars.v1", "yahoo", 0, BarPayload(symbol="SPX", interval="1h", ts=QUOTED + timedelta(hours=1),
                                                    open=1.0, high=1.0, low=1.0, close=1.0, volume=0))
    assert not s.apply(hourly) and s.spot.close == 6705.0


def test_no_chain_no_quote():
    assert state_with(bar_env(QUOTED)).to_quote(now=QUOTED) is None
