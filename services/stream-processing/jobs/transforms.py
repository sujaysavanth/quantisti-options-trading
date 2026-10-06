"""Pure DataFrame transforms: Kafka rows in, table-shaped rows out. No I/O, so they test on a local SparkSession."""

from typing import Sequence, Tuple

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F
from pyspark.sql.types import StructType

from .schemas import envelope

# Spark's default JSON timestamp pattern only allows 3 fraction digits; ingest writes 6 (Python microseconds).
JSON_OPTIONS = {"timestampFormat": "yyyy-MM-dd'T'HH:mm:ss[.SSSSSS][.SSS]XXX"}


def parse_envelopes(kafka_df: DataFrame, payload: StructType, schema_name: str) -> Tuple[DataFrame, DataFrame]:
    """Kafka `value` bytes -> (valid rows with source/produced_at/payload, rejected raw rows).

    Rejected: not JSON, wrong envelope shape, or a schema name/version this job doesn't handle.
    """
    parsed = kafka_df.select(
        F.col("value").cast("string").alias("json"),
        F.from_json(F.col("value").cast("string"), envelope(payload), JSON_OPTIONS).alias("env"),
    )
    ok = (F.col("env.schema") == schema_name) & F.col("env.payload").isNotNull() & F.col("env.source").isNotNull()
    ok = F.coalesce(ok, F.lit(False))
    valid = parsed.where(ok).select("env.source", "env.produced_at", "env.payload")
    rejected = parsed.where(~ok).select("json")
    return valid, rejected


def latest(df: DataFrame, keys: Sequence[str], order_col: str) -> DataFrame:
    """One row per key: the one with the greatest `order_col`.

    Needed before an upsert: Postgres refuses an INSERT ... ON CONFLICT that hits the same
    row twice in one statement, and one micro-batch can hold several polls of the same contract.
    """
    w = Window.partitionBy(*keys).orderBy(F.col(order_col).desc())
    return df.withColumn("_rank", F.row_number().over(w)).where("_rank = 1").drop("_rank")


def daily_frames(valid: DataFrame) -> Tuple[DataFrame, DataFrame, DataFrame]:
    """Split daily.v1 rows into (underlying_daily, vix_daily, rates_daily) shaped frames, newest message per day."""
    p = valid.select("produced_at", "payload.*")

    underlying = latest(
        p.where((F.col("dataset") == "underlying") & F.col("open").isNotNull() & F.col("high").isNotNull()
                & F.col("low").isNotNull() & F.col("close").isNotNull() & F.col("date").isNotNull()),
        ["symbol", "date"], "produced_at",
    ).select("symbol", "date", "open", "high", "low", "close", F.coalesce("volume", F.lit(0)).alias("volume"))

    vix = latest(
        p.where((F.col("dataset") == "vix") & F.col("close").isNotNull() & F.col("date").isNotNull()),
        ["date"], "produced_at",
    ).select("date", "close")

    rates = latest(
        p.where((F.col("dataset") == "rates") & F.col("rate").isNotNull() & F.col("date").isNotNull()),
        ["date"], "produced_at",
    ).select("date", "rate")

    return underlying, vix, rates


CONTRACT_KEY = ["symbol", "snapshot_date", "expiry_date", "strike", "option_type", "source"]


def chain_rows(valid: DataFrame) -> DataFrame:
    """chain.v1 messages (one per expiry) -> one row per contract, newest quote per contract per session."""
    exploded = valid.select(
        "source",
        F.col("payload.symbol").alias("symbol"),
        F.col("payload.session_date").alias("snapshot_date"),
        F.col("payload.expiry").alias("expiry_date"),
        F.col("payload.quoted_at").alias("quoted_at"),
        F.col("payload.underlying_price").alias("underlying_price"),
        F.explode("payload.quotes").alias("q"),
    ).select("*", "q.*").drop("q")

    good = exploded.where(
        F.col("symbol").isNotNull() & F.col("snapshot_date").isNotNull() & F.col("expiry_date").isNotNull()
        & F.col("quoted_at").isNotNull() & F.col("option_type").isin("C", "P") & (F.col("strike") > 0)
    )
    return latest(good, CONTRACT_KEY, "quoted_at").select(
        "symbol", "snapshot_date", "expiry_date", "strike", "option_type", "underlying_price",
        "bid", "ask", "last", "open_interest", "volume", "vendor_iv", "vendor_delta", "quoted_at", "source",
    )
