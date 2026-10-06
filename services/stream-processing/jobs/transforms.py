"""Pure DataFrame transforms: Kafka rows in, table-shaped rows out. No I/O, so they test on a local SparkSession."""

from typing import Sequence, Tuple

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F
from pyspark.sql.types import StructType

from .schemas import envelope

# Spark's default JSON timestamp pattern only allows 3 fraction digits; ingest writes 6 (Python microseconds).
JSON_OPTIONS = {"timestampFormat": "yyyy-MM-dd'T'HH:mm:ss[.SSSSSS][.SSS]XXX"}


def parse_envelopes(kafka_df: DataFrame, payload: StructType, schema_name: str) -> Tuple[DataFrame, DataFrame]:
    """Kafka `value` bytes -> (valid rows: json/source/produced_at/payload, rejected rows: json/reason).

    Rejected: not JSON, wrong envelope shape, or a schema name/version this job doesn't handle.
    The raw `json` is kept on both sides so a later check can still send the original to the DLQ.
    """
    parsed = kafka_df.select(
        F.col("value").cast("string").alias("json"),
        F.from_json(F.col("value").cast("string"), envelope(payload), JSON_OPTIONS).alias("env"),
    )
    reason = (
        F.when(F.col("env.schema").isNull(), F.lit("unparseable message"))
        .when(F.col("env.schema") != schema_name, F.concat(F.lit("unexpected schema "), F.col("env.schema")))
        .when(F.col("env.payload").isNull(), F.lit("payload does not match " + schema_name))
        .when(F.col("env.source").isNull(), F.lit("missing source"))
    )
    parsed = parsed.withColumn("reason", reason)
    valid = parsed.where(F.col("reason").isNull()).select("json", "env.source", "env.produced_at", "env.payload")
    rejected = parsed.where(F.col("reason").isNotNull()).select("json", "reason")
    return valid, rejected


# ---------------------------------------------------------------- intraday bars

SYMBOLS = ("SPX", "VIX")
INTERVALS = ("1m", "5m", "1h")
BAR_COLUMNS = ["symbol", "interval", "ts", "open", "high", "low", "close", "volume"]


def validate_bars(valid: DataFrame) -> Tuple[DataFrame, DataFrame]:
    """bars.v1 rows -> (good bars, bad bars with json/reason). The first failing rule is the reason."""
    p = valid.select("json", "source", "produced_at", "payload.*")
    prices = [F.col(c) for c in ("open", "high", "low", "close")]
    any_null = prices[0].isNull() | prices[1].isNull() | prices[2].isNull() | prices[3].isNull()
    any_nonpositive = (prices[0] <= 0) | (prices[1] <= 0) | (prices[2] <= 0) | (prices[3] <= 0)
    reason = (
        F.when(~F.coalesce(F.col("symbol").isin(*SYMBOLS), F.lit(False)), F.lit("unknown symbol"))
        .when(~F.coalesce(F.col("interval").isin(*INTERVALS), F.lit(False)), F.lit("unknown interval"))
        .when(F.col("ts").isNull(), F.lit("missing ts"))
        .when(any_null, F.lit("missing price"))
        .when(any_nonpositive, F.lit("non-positive price"))
        .when(F.col("high") < F.col("low"), F.lit("high < low"))
        .when((F.col("high") < F.greatest("open", "close")) | (F.col("low") > F.least("open", "close")),
              F.lit("open/close outside high-low"))
        .when(F.col("volume") < 0, F.lit("negative volume"))
    )
    p = p.withColumn("reason", reason)
    good = p.where(F.col("reason").isNull()).select("source", "produced_at", *BAR_COLUMNS) \
        .withColumn("volume", F.coalesce("volume", F.lit(0)))
    bad = p.where(F.col("reason").isNotNull()).select("json", "reason")
    return good, bad


def latest_bars(good: DataFrame) -> DataFrame:
    """One row per (symbol, interval, ts) for an upsert: the CLI re-sends whole sessions, so a batch repeats bars."""
    return latest(good, ["symbol", "interval", "ts"], "produced_at")


def five_minute_bars(one_minute: DataFrame) -> DataFrame:
    """1m bars -> 5m OHLCV bars on a tumbling window. Works on a batch DataFrame or a stream.

    open/close are the open of the earliest and the close of the latest 1m bar in the window
    (min_by/max_by), not min/max. `bars` says how many 1m bars went in (5 = complete).
    """
    return (
        one_minute.groupBy(F.window("ts", "5 minutes").alias("w"), "symbol")
        .agg(
            F.min_by("open", "ts").alias("open"),
            F.max("high").alias("high"),
            F.min("low").alias("low"),
            F.max_by("close", "ts").alias("close"),
            F.sum("volume").alias("volume"),
            F.count("*").alias("bars"),
        )
        .select("symbol", F.col("w.start").alias("ts"), "open", "high", "low", "close", "volume", "bars")
    )


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
