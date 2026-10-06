import json
from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from app.producers.envelope import BarPayload, ChainPayload, DailyPayload, Envelope, QuotePayload, wrap

TS = datetime(2026, 10, 5, 14, 30, tzinfo=timezone.utc)


def bar(**kw):
    return BarPayload(**{"symbol": "SPX", "interval": "1m", "ts": TS, "open": 6700.0, "high": 6702.5,
                         "low": 6699.0, "close": 6701.0, "volume": 0, **kw})


def test_bar_round_trip_and_json_field_names():
    env = wrap("bars.v1", "yahoo", 15, bar(), produced_at=TS)
    raw = env.to_bytes()
    assert json.loads(raw)["schema"] == "bars.v1"              # JSON says "schema", not schema_name
    assert Envelope.from_bytes(raw) == env


def test_chain_round_trip_keeps_unknown_open_interest_as_null():
    payload = ChainPayload(symbol="SPX", expiry=date(2026, 10, 9), session_date=date(2026, 10, 5), quoted_at=TS,
                           underlying_price=6701.0,
                           quotes=[QuotePayload(option_type="C", strike=6700, bid=30.1, ask=30.6, open_interest=None)])
    back = Envelope.from_bytes(wrap("chain.v1", "cboe", 15, payload).to_bytes())
    assert isinstance(back.payload, ChainPayload)
    assert back.payload.quotes[0].open_interest is None


def test_daily_rows_need_their_fields():
    DailyPayload(dataset="rates", symbol="DGS3MO", date=date(2026, 10, 2), rate=0.0412)
    with pytest.raises(ValidationError):
        DailyPayload(dataset="underlying", symbol="SPX", date=date(2026, 10, 2), close=6700.0)  # no open/high/low


def test_bad_messages_are_rejected():
    good = json.loads(wrap("bars.v1", "yahoo", 15, bar()).to_bytes())
    with pytest.raises(ValidationError):
        Envelope.model_validate({**good, "schema": "bars.v9"})              # unknown version
    with pytest.raises(ValidationError):
        Envelope.model_validate({**good, "payload": {**good["payload"], "ts": None}})
    with pytest.raises(ValidationError):
        Envelope.model_validate({**good, "payload": {**good["payload"], "low": -1}})
    with pytest.raises(ValidationError):
        wrap("chain.v1", "yahoo", 15, bar())                                  # payload doesn't match schema
