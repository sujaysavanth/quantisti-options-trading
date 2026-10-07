import json

import pytest
from pyspark.sql import SparkSession


@pytest.fixture(scope="session")
def spark():
    session = (
        SparkSession.builder.master("local[1]").appName("tests")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()


@pytest.fixture
def kafka_df(spark):
    """Build a DataFrame shaped like a Kafka micro-batch from dicts (or raw strings)."""
    def make(*messages):
        rows = [(bytearray(m if isinstance(m, str) else json.dumps(m), "utf-8"),) for m in messages]
        return spark.createDataFrame(rows, "value binary")
    return make
