"""Structured Streaming job: Kafka topics -> Postgres.

Four independent queries, each with its own checkpoint (the Kafka offsets it has
committed to Postgres):

    daily     market.daily          -> underlying_daily / vix_daily / rates_daily / index_daily
    chain     options.chain.quotes  -> option_chain_snapshots
    bars_1m   market.bars.1m        -> intraday_bars, bars stored as published (no watermark:
                                       late or replayed bars still land; the upsert makes repeats harmless)
    bars_5m   market.bars.1m        -> intraday_bars 5m, built with event-time windows and a watermark

Messages a query can't use go to ingest.dlq with the reason. On restart a query resumes
from its checkpoint; the very first start reads from the earliest offset still in Kafka.

    spark-submit --master local[2] jobs/stream_main.py
"""

import logging
import os

import psycopg2
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from jobs.dlq import send_to_dlq
from jobs.schemas import BAR_PAYLOAD, CHAIN_PAYLOAD, DAILY_PAYLOAD
from jobs.sink import write_bars, write_chain, write_daily
from jobs.transforms import (chain_rows, daily_frames, five_minute_bars, index_frame, latest_bars,
                             parse_envelopes, validate_bars)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("stream")

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://quantisti:quantisti@postgres:5432/quantisti")
CHECKPOINTS = os.getenv("CHECKPOINT_DIR", "/checkpoints")
TRIGGER = os.getenv("TRIGGER_INTERVAL", "30 seconds")
# How late a 1m bar may arrive (behind the newest bar seen) and still change its 5m bar.
WATERMARK = os.getenv("BARS_WATERMARK", "10 minutes")


def _upsert(write, *args) -> None:
    with psycopg2.connect(DATABASE_URL) as conn:      # commits on success, rolls back on error
        write(conn, *args)
    conn.close()


def handle_daily(batch: DataFrame, batch_id: int) -> None:
    batch.persist()
    try:
        valid, rejected = parse_envelopes(batch, DAILY_PAYLOAD, "daily.v1")
        underlying, vix, rates = daily_frames(valid)
        # A daily batch is a few dozen rows (a history backfill a few tens of thousands), so collecting
        # to the driver is fine. A large deployment would write per partition (foreachPartition) instead.
        u = [tuple(r) for r in underlying.collect()]
        v = [tuple(r) for r in vix.collect()]
        ra = [tuple(r) for r in rates.collect()]
        ix = [tuple(r) for r in index_frame(valid).collect()]
        _upsert(write_daily, u, v, ra, ix)
        bad = send_to_dlq(rejected, "daily", "market.daily", BOOTSTRAP)
        log.info("daily batch %d: %d underlying, %d vix, %d rates, %d index, %d to DLQ",
                 batch_id, len(u), len(v), len(ra), len(ix), bad)
    finally:
        batch.unpersist()


def handle_chain(batch: DataFrame, batch_id: int) -> None:
    batch.persist()
    try:
        valid, rejected = parse_envelopes(batch, CHAIN_PAYLOAD, "chain.v1")
        # A batch holds a few polls x ~1,300 contracts: small enough for the driver.
        rows = [tuple(r) for r in chain_rows(valid).collect()]
        _upsert(write_chain, rows)
        bad = send_to_dlq(rejected, "chain", "options.chain.quotes", BOOTSTRAP)
        sessions = sorted({str(r[1]) for r in rows})
        log.info("chain batch %d: %d contracts upserted (sessions %s), %d to DLQ", batch_id, len(rows), sessions, bad)
    finally:
        batch.unpersist()


def handle_bars_1m(batch: DataFrame, batch_id: int) -> None:
    batch.persist()
    try:
        valid, unparsed = parse_envelopes(batch, BAR_PAYLOAD, "bars.v1")
        good, bad = validate_bars(valid)
        rows = [tuple(r) for r in latest_bars(good).select(
            "symbol", "interval", "ts", "open", "high", "low", "close", "volume", "source").collect()]
        _upsert(write_bars, rows)
        to_dlq = send_to_dlq(unparsed.unionByName(bad), "bars_1m", "market.bars.1m", BOOTSTRAP)
        log.info("bars_1m batch %d: %d bars upserted, %d to DLQ", batch_id, len(rows), to_dlq)
    finally:
        batch.unpersist()


def handle_bars_5m(batch: DataFrame, batch_id: int) -> None:
    # In update mode each batch holds only the 5m windows that changed, with their full aggregate so far.
    rows = [(r.symbol, "5m", r.ts, r.open, r.high, r.low, r.close, r.volume, "agg_1m") for r in batch.collect()]
    _upsert(write_bars, rows)
    if rows:
        log.info("bars_5m batch %d: %d windows updated (latest %s)", batch_id, len(rows), max(r[2] for r in rows))


def kafka_stream(spark: SparkSession, topic: str, max_offsets: int = 2000) -> DataFrame:
    return (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", BOOTSTRAP)
        .option("subscribe", topic)
        .option("startingOffsets", "earliest")        # first start only; afterwards the checkpoint decides
        .option("failOnDataLoss", "false")            # retention may delete offsets we haven't read: skip, don't crash
        .option("maxOffsetsPerTrigger", max_offsets)  # bound the first catch-up batches
        .load()
    )


def start(df: DataFrame, name: str, handler, output_mode: str = "append"):
    return (
        df.writeStream.queryName(name)
        .outputMode(output_mode)
        .foreachBatch(handler)
        .option("checkpointLocation", f"{CHECKPOINTS}/{name}")
        .trigger(processingTime=TRIGGER)
        .start()
    )


def five_minute_stream(spark: SparkSession) -> DataFrame:
    """The stateful part, written on the stream itself (not inside foreachBatch) so Spark keeps state across batches.

    1. withWatermark: event time is the bar's own `ts`. Spark tracks the newest ts seen and accepts bars up
       to WATERMARK behind it; older ones are "late" and ignored, and state for finished windows is dropped.
    2. dropDuplicatesWithinWatermark: the CLI re-sends whole sessions; without this a 5m volume would be
       counted two or three times.
    3. A 5-minute tumbling window per symbol.
    """
    valid, _ = parse_envelopes(kafka_stream(spark, "market.bars.1m", 20000), BAR_PAYLOAD, "bars.v1")
    good, _ = validate_bars(valid)
    one_minute = (
        good.where(F.col("interval") == "1m")
        .withWatermark("ts", WATERMARK)
        .dropDuplicatesWithinWatermark(["symbol", "ts"])
    )
    return five_minute_bars(one_minute)


def main() -> None:
    spark = (
        SparkSession.builder.appName("quantisti-stream")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "4")   # tiny data: the default 200 tasks would be pure overhead
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    start(kafka_stream(spark, "market.daily"), "daily", handle_daily)
    start(kafka_stream(spark, "options.chain.quotes"), "chain", handle_chain)
    start(kafka_stream(spark, "market.bars.1m", 20000), "bars_1m", handle_bars_1m)
    # "update": emit a window every time it changes, so the current 5m bar is visible before it closes.
    start(five_minute_stream(spark), "bars_5m", handle_bars_5m, output_mode="update")
    log.info("4 streaming queries started; Spark UI on :4040")
    spark.streams.awaitAnyTermination()


if __name__ == "__main__":
    main()
