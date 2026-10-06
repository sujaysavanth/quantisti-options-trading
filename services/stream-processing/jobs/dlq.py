"""Dead-letter queue: messages a job can't use go to ingest.dlq instead of being dropped.

Each DLQ message wraps the original so nothing is lost and the cause is visible:
    key   = the topic it came from
    value = {"job": "bars_1m", "topic": "market.bars.1m", "reason": "high < low",
             "failed_at": "...", "value": "<the original message, as a string>"}
Nothing reads the DLQ automatically; it's for people (Kafka UI) and, later, the gap/backfill tooling.
"""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

DLQ_TOPIC = "ingest.dlq"


def dlq_frame(rejected: DataFrame, job: str, topic: str) -> DataFrame:
    """rejected(json, reason) -> Kafka-shaped (key, value) rows."""
    return rejected.select(
        F.lit(topic).alias("key"),
        F.to_json(F.struct(
            F.lit(job).alias("job"),
            F.lit(topic).alias("topic"),
            F.col("reason"),
            F.date_format(F.current_timestamp(), "yyyy-MM-dd'T'HH:mm:ss'Z'").alias("failed_at"),
            F.col("json").alias("value"),
        )).alias("value"),
    )


def send_to_dlq(rejected: DataFrame, job: str, topic: str, bootstrap: str) -> int:
    """Write rejected rows to ingest.dlq with Spark's batch Kafka writer; returns how many."""
    count = rejected.count()
    if count:
        (dlq_frame(rejected, job, topic).write.format("kafka")
         .option("kafka.bootstrap.servers", bootstrap)
         .option("topic", DLQ_TOPIC)
         .save())
    return count
