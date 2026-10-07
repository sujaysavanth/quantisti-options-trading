"""The JSON message every producer sends, and its payload shapes.

    {"schema": "bars.v1", "source": "yahoo", "delay_minutes": 15,
     "produced_at": "2026-10-05T14:31:02Z", "payload": {...}}

`schema` names the payload shape and its version. A consumer looks at it first
and can reject (or upgrade) messages it does not understand; changing a payload
in an incompatible way means a new version (bars.v2), never editing v1.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BarPayload(BaseModel):
    """One OHLCV bar. `ts` is the bar start in UTC."""

    symbol: Literal["SPX", "VIX"]
    interval: Literal["1m", "5m", "1h"]
    ts: datetime
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: int = Field(ge=0)


class QuotePayload(BaseModel):
    """One option contract inside a chain message."""

    option_type: Literal["C", "P"]
    strike: float = Field(gt=0)
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    volume: Optional[int] = None
    open_interest: Optional[int] = None     # None = the source doesn't know, not zero
    vendor_iv: Optional[float] = None
    vendor_delta: Optional[float] = None


class ChainPayload(BaseModel):
    """All quotes for one expiry from one fetch (one Kafka message per expiry)."""

    symbol: Literal["SPX"]
    expiry: date
    session_date: date                      # the trading session the quotes belong to
    quoted_at: datetime                     # when the quotes are from (already includes the delay)
    underlying_price: Optional[float] = None
    quotes: List[QuotePayload]


class DailyPayload(BaseModel):
    """One day of one daily dataset: an SPX OHLCV bar, a VIX close, a T-bill rate, or an index close
    (VIX9D, VIX3M, VVIX, SKEW, BAA10Y, T10Y2Y: app/sources/indexes.py)."""

    dataset: Literal["underlying", "vix", "rates", "index"]
    symbol: str                             # SPX, VIX, DGS3MO, or an index symbol
    date: date
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None
    rate: Optional[float] = None            # decimal: 0.0419 = 4.19%

    @model_validator(mode="after")
    def _fields_for_dataset(self):
        needed = {"underlying": ("open", "high", "low", "close"), "vix": ("close",), "rates": ("rate",), "index": ("close",)}[self.dataset]
        missing = [f for f in needed if getattr(self, f) is None]
        if missing:
            raise ValueError(f"{self.dataset} row needs {', '.join(missing)}")
        return self


class BackfillPayload(BaseModel):
    """A request to refill one session of one dataset (from the gap detector to the backfill worker)."""

    dataset: Literal["daily", "vix", "rates", "index", "intraday", "chain"]
    symbol: str                             # as in ingest_gaps: SPX, VIX, DGS3MO, "SPX:1m"
    date: date
    attempt: int = Field(ge=1)

    @model_validator(mode="after")
    def _intraday_symbol(self):
        if self.dataset == "intraday":
            symbol, _, interval = self.symbol.partition(":")
            if symbol not in ("SPX", "VIX") or interval not in ("1m", "5m", "1h"):
                raise ValueError(f"intraday symbol must look like SPX:1m, got {self.symbol!r}")
        return self


PAYLOADS = {"bars.v1": BarPayload, "chain.v1": ChainPayload, "daily.v1": DailyPayload, "backfill.v1": BackfillPayload}
Payload = Union[BarPayload, ChainPayload, DailyPayload, BackfillPayload]


class Envelope(BaseModel):
    # `schema` would shadow a BaseModel attribute, so the field is schema_name with JSON name "schema".
    model_config = ConfigDict(populate_by_name=True)

    schema_name: str = Field(alias="schema")
    source: str
    delay_minutes: int = Field(ge=0)
    produced_at: datetime
    payload: Payload

    @model_validator(mode="before")
    @classmethod
    def _payload_by_schema(cls, data):
        # Pick the payload class from `schema` instead of letting pydantic guess from the fields.
        if isinstance(data, dict):
            name = data.get("schema", data.get("schema_name"))
            if name not in PAYLOADS:
                raise ValueError(f"unknown schema {name!r}; expected one of {sorted(PAYLOADS)}")
            if isinstance(data.get("payload"), dict):
                data = {**data, "payload": PAYLOADS[name].model_validate(data["payload"])}
        return data

    @model_validator(mode="after")
    def _payload_matches_schema(self):
        if not isinstance(self.payload, PAYLOADS[self.schema_name]):
            raise ValueError(f"{self.schema_name} needs a {PAYLOADS[self.schema_name].__name__}")
        return self

    def to_bytes(self) -> bytes:
        return self.model_dump_json(by_alias=True).encode()

    @classmethod
    def from_bytes(cls, raw: bytes) -> "Envelope":
        return cls.model_validate(json.loads(raw))


def wrap(schema: str, source: str, delay_minutes: int, payload: Payload,
         produced_at: Optional[datetime] = None) -> Envelope:
    return Envelope(schema=schema, source=source, delay_minutes=delay_minutes,
                    produced_at=produced_at or datetime.now(timezone.utc), payload=payload)
