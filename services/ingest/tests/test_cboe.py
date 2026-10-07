from datetime import date, datetime, timezone

from app.sources.cboe import CboeDelayedSource


def opt(symbol, bid=10.0, ask=10.5, oi=100, iv=0.12):
    return {"option": symbol, "bid": bid, "ask": ask, "last_trade_price": 10.2,
            "volume": 5, "open_interest": oi, "iv": iv, "delta": 0.5}


PAYLOAD = {
    "timestamp": "2026-10-02 20:03:12",  # UTC, when the file was generated
    "data": {
        "current_price": 7700.0,
        "last_trade_time": "2026-10-02T15:48:10",  # New York time
        "options": [
            opt("SPXW261001C07700000"),                   # expired yesterday: dropped
            opt("SPXW261002C07700000"),                   # today's 0DTE
            opt("SPXW261002P07700000", bid=0),            # zero bid -> None
            opt("SPXW261005C07700000", iv=0),             # CBOE's "no IV" -> None
            opt("SPXW261005C09000000"),                   # far outside +/-5%: dropped
            opt("SPX261016C07700000", oi=999),            # AM monthly duplicate: dropped
            opt("SPXW261016C07700000", oi=111),           # PM weekly at the same strike: kept
            opt("SPX271217C07700000"),                    # LEAPS with no SPXW: kept, but beyond 3 expiries
        ],
    },
}


def test_fetch_chain_from_saved_payload():
    snap = CboeDelayedSource(get=lambda url: PAYLOAD).fetch_chain(expiries=3, moneyness=0.05)

    assert (snap.source, snap.delay_minutes, snap.underlying_price) == ("cboe", 15, 7700.0)
    assert snap.quoted_at == datetime(2026, 10, 2, 19, 48, 10, tzinfo=timezone.utc)  # 15:48:10 EDT
    assert snap.session_date == date(2026, 10, 2)

    keys = [(q.expiry, q.option_type, q.strike) for q in snap.quotes]
    assert keys == [
        (date(2026, 10, 2), "C", 7700.0),
        (date(2026, 10, 2), "P", 7700.0),
        (date(2026, 10, 5), "C", 7700.0),
        (date(2026, 10, 16), "C", 7700.0),
    ]

    zero_bid = snap.quotes[1]
    assert zero_bid.bid is None and zero_bid.ask == 10.5
    assert snap.quotes[3].open_interest == 111  # the SPXW row, not the SPX one
    assert snap.quotes[0].vendor_iv == 0.12
    assert snap.quotes[2].vendor_iv is None


VIX_CSV = """DATE,OPEN,HIGH,LOW,CLOSE
09/30/2026,16.000000,16.400000,15.800000,16.340000
10/01/2026,16.300000,16.500000,15.900000,15.950000
10/02/2026,16.150000,16.240000,15.300000,15.310000
"""


def test_vix_history_parses_and_filters_dates():
    from app.sources.cboe import DailyClose, fetch_vix_history

    rows = fetch_vix_history(start=date(2026, 10, 1), get_text=lambda url: VIX_CSV)
    assert rows == [DailyClose(date(2026, 10, 1), 15.95), DailyClose(date(2026, 10, 2), 15.31)]


def test_expiry_that_settled_today_is_dropped():
    after_close = {**PAYLOAD, "data": {**PAYLOAD["data"], "last_trade_time": "2026-10-02T16:14:00"}}
    snap = CboeDelayedSource(get=lambda url: after_close).fetch_chain(expiries=3, moneyness=0.05)
    assert snap.session_date == date(2026, 10, 2)
    assert date(2026, 10, 2) not in {q.expiry for q in snap.quotes}   # 0DTE settled at 16:00
