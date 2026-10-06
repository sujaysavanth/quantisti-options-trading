from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from app.sources.yahoo import fetch_bars

NOW = datetime(2026, 10, 5, 21, 0, tzinfo=timezone.utc)


def frame(times, tz):
    idx = pd.DatetimeIndex(pd.to_datetime(times)).tz_localize(tz)
    cols = pd.MultiIndex.from_product([["Open", "High", "Low", "Close", "Volume"], ["^VIX"]])
    return pd.DataFrame([[16.0, 16.2, 15.9, 16.1, 0]] * len(times), index=idx, columns=cols)


def test_regular_session_only_and_utc():
    df = frame(["2026-10-05 02:15", "2026-10-05 08:30", "2026-10-05 14:59", "2026-10-05 15:00"], "America/Chicago")
    bars = fetch_bars("VIX", "1m", NOW - timedelta(days=1), NOW, download=lambda **kw: df, now=NOW)
    # 02:15 CT is overnight; 15:00 CT is 16:00 ET, the close itself. Only 09:30 and 15:59 ET remain.
    assert [b.ts for b in bars] == [datetime(2026, 10, 5, 13, 30, tzinfo=timezone.utc),
                                    datetime(2026, 10, 5, 19, 59, tzinfo=timezone.utc)]
    assert bars[0].symbol == "VIX" and bars[0].interval == "1m" and bars[0].close == 16.1


def test_one_minute_requests_are_split_into_week_chunks():
    calls = []
    fetch_bars("SPX", "1m", NOW - timedelta(days=20), NOW,
               download=lambda **kw: calls.append(kw) or pd.DataFrame(), now=NOW)
    assert len(calls) == 3
    assert all(c["end"] - c["start"] <= timedelta(days=7) for c in calls)
    assert calls[0]["tickers"] == "^GSPC" and calls[-1]["end"] == NOW


def test_start_is_clamped_and_too_old_raises():
    calls = []
    fetch_bars("SPX", "5m", NOW - timedelta(days=90), NOW,
               download=lambda **kw: calls.append(kw) or pd.DataFrame(), now=NOW)
    assert calls[0]["start"] > NOW - timedelta(days=60)
    with pytest.raises(ValueError):
        fetch_bars("SPX", "1m", NOW - timedelta(days=50), NOW - timedelta(days=40), download=lambda **kw: None, now=NOW)


# ---------------------------------------------------------------- fallback chain source

from datetime import date
from types import SimpleNamespace

from app.sources.yahoo import YahooDelayedSource


def chain_rows(expiry, oi):
    return pd.DataFrame([
        {"contractSymbol": f"SPXW{expiry}C07700000", "strike": 7700.0, "bid": 10.0, "ask": 10.5,
         "lastPrice": 10.2, "volume": 5.0, "openInterest": oi, "impliedVolatility": 0.13},
        {"contractSymbol": f"SPXW{expiry}C09000000", "strike": 9000.0, "bid": 0.0, "ask": 0.05,
         "lastPrice": 0.05, "volume": 0.0, "openInterest": oi, "impliedVolatility": 0.3},
    ])


class FakeTicker:
    def __init__(self, oi):
        self.options = ("2026-10-01", "2026-10-02", "2026-10-05")
        self.oi = oi

    def history(self, **kw):
        return pd.DataFrame({"Close": [7690.0, 7700.0]})

    def option_chain(self, expiry):
        code = expiry[2:].replace("-", "")
        return SimpleNamespace(calls=chain_rows(code, self.oi), puts=chain_rows(code, self.oi).iloc[0:0])


def at(dt):
    return lambda: dt


def test_yahoo_chain_shape_matches_cboe():
    src = YahooDelayedSource(FakeTicker(oi=210.0), now=at(datetime(2026, 10, 2, 18, 0, tzinfo=timezone.utc)))
    snap = src.fetch_chain(expiries=2, moneyness=0.05)
    assert (snap.source, snap.session_date, snap.underlying_price) == ("yahoo", date(2026, 10, 2), 7700.0)
    assert snap.quoted_at == datetime(2026, 10, 2, 17, 45, tzinfo=timezone.utc)  # 15 min delay
    # 2026-10-01 already expired; 9000 strike outside +/-5%
    assert [(q.expiry, q.strike) for q in snap.quotes] == [(date(2026, 10, 2), 7700.0), (date(2026, 10, 5), 7700.0)]
    assert snap.quotes[0].open_interest == 210


def test_all_zero_open_interest_means_unknown():
    # Overnight capture, like the 01:45 ET rows from Module 2.
    src = YahooDelayedSource(FakeTicker(oi=0.0), now=at(datetime(2026, 10, 1, 5, 45, tzinfo=timezone.utc)))
    assert all(q.open_interest is None for q in src.fetch_chain(expiries=2, moneyness=0.05).quotes)
