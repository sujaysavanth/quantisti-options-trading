"""Spark schemas for the JSON envelopes the ingest service publishes.

They mirror the pydantic models in services/ingest/app/producers/envelope.py.
A streaming read can't infer a schema (there is no "whole dataset" to sample),
and an explicit one doubles as validation: a message that doesn't fit parses
to null and is rejected instead of silently producing wrong columns.
"""

from pyspark.sql.types import (ArrayType, DateType, DoubleType, IntegerType, LongType, StringType, StructField,
                               StructType, TimestampType)


def _fields(*specs):
    return StructType([StructField(name, kind, True) for name, kind in specs])


QUOTE = _fields(
    ("option_type", StringType()), ("strike", DoubleType()),
    ("bid", DoubleType()), ("ask", DoubleType()), ("last", DoubleType()),
    ("volume", LongType()), ("open_interest", LongType()),
    ("vendor_iv", DoubleType()), ("vendor_delta", DoubleType()),
)

CHAIN_PAYLOAD = _fields(
    ("symbol", StringType()), ("expiry", DateType()), ("session_date", DateType()),
    ("quoted_at", TimestampType()), ("underlying_price", DoubleType()), ("quotes", ArrayType(QUOTE)),
)

DAILY_PAYLOAD = _fields(
    ("dataset", StringType()), ("symbol", StringType()), ("date", DateType()),
    ("open", DoubleType()), ("high", DoubleType()), ("low", DoubleType()), ("close", DoubleType()),
    ("volume", LongType()), ("rate", DoubleType()),
)


def envelope(payload: StructType) -> StructType:
    return _fields(
        ("schema", StringType()), ("source", StringType()), ("delay_minutes", IntegerType()),
        ("produced_at", TimestampType()), ("payload", payload),
    )
