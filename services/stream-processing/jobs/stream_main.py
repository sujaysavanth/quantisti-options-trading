"""Structured Streaming job: market.daily and options.chain.quotes -> Postgres.

Two independent queries, each with its own checkpoint (the Kafka offsets it has
committed to Postgres). On restart a query resumes from its checkpoint; the very
first start reads from the earliest offset still in Kafka, so everything published
within the 7-day retention gets saved.

    spark-submit --master local[2] jobs/stream_main.py
"""

import logging
import os

import psycopg2
from pyspark.sql import DataFrame, SparkSession

from jobs.schemas import CHAIN_PAYLOAD, DAILY_PAYLOAD
from jobs.sink import write_chain, write_daily
from jobs.transforms import chain_rows, daily_frames, parse_envelopes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("stream")

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://quantisti:quantisti@postgres:5432/quantisti")
CHECKPOINTS = os.getenv("CHECKPOINT_DIR", "/checkpoints")
TRIGGER = os.getenv("TRIGGER_INTERVAL", "30 seconds")


def handle_daily(batch: DataFrame, batch_id: int) -> None:
    batch.persist()
    try:
        valid, rejected = parse_envelopes(batch, DAILY_PAYLOAD, "daily.v1")
        underlying, vix, rates = daily_frames(valid)
        # A daily batch is a few dozen rows, so collecting to the driver is fine.
        # A large deployment would write per partition (foreachPartition) instead.
        u = [tuple(r) for r in underlying.collect()]
        v = [tuple(r) for r in vix.collect()]
        ra = [tuple(r) for r in rates.collect()]
        bad = rejected.count()
        with psycopg2.connect(DATABASE_URL) as conn:      # commits on success, rolls back on error
            write_daily(conn, u, v, ra)
        conn.close()
        log.info("daily batch %d: %d underlying, %d vix, %d rates, %d rejected", batch_id, len(u), len(v), len(ra), bad)
    finally:
        batch.unpersist()


def handle_chain(batch: DataFrame, batch_id: int) -> None:
    batch.persist()
    try:
        valid, rejected = parse_envelopes(batch, CHAIN_PAYLOAD, "chain.v1")
        # A batch holds a few polls x ~1,300 contracts: small enough for the driver.
        rows = [tuple(r) for r in chain_rows(valid).collect()]
        bad = rejected.count()
        with psycopg2.connect(DATABASE_URL) as conn:
            write_chain(conn, rows)
        conn.close()
        sessions = sorted({str(r[1]) for r in rows})
        log.info("chain batch %d: %d contracts upserted (sessions %s), %d rejected", batch_id, len(rows), sessions, bad)
    finally:
        batch.unpersist()


def start_query(spark: SparkSession, topic: str, name: str, handler):
    source = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", BOOTSTRAP)
        .option("subscribe", topic)
        .option("startingOffsets", "earliest")        # first start only; afterwards the checkpoint decides
        .option("failOnDataLoss", "false")            # retention may delete offsets we haven't read: skip, don't crash
        .option("maxOffsetsPerTrigger", 2000)         # bound the first catch-up batches
        .load()
    )
    return (
        source.writeStream.queryName(name)
        .foreachBatch(handler)
        .option("checkpointLocation", f"{CHECKPOINTS}/{name}")
        .trigger(processingTime=TRIGGER)
        .start()
    )


def main() -> None:
    spark = (
        SparkSession.builder.appName("quantisti-stream")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "4")   # tiny data: the default 200 tasks would be pure overhead
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    start_query(spark, "market.daily", "daily", handle_daily)
    start_query(spark, "options.chain.quotes", "chain", handle_chain)
    log.info("streaming queries started; Spark UI on :4040")
    spark.streams.awaitAnyTermination()


if __name__ == "__main__":
    main()
