"""Spark batch job: OptionsDX SPX end-of-day files -> option_chain_snapshots (source 'optionsdx').

Batch, not streaming: the input is a fixed folder of files read once. Re-running is safe
(upserts), so adding more years later just means running it again.

    spark-submit jobs/import_optionsdx.py --input /data/optionsdx/spx [--years 2010,2011]
                                          [--max-dte 60] [--moneyness 0.10] [--dry-run]

Default limits: expiries up to 60 days out, strikes within +/-10% of spot. Full SPX chains
run to millions of rows a year; these limits cover every strategy in schema/sql.
"""

import argparse
import glob
import logging
import os
from collections import defaultdict

import psycopg2
from pyspark import StorageLevel
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from jobs.optionsdx import EXPECTED_COLUMNS, check_headers, classify, expiry_map_frame, kept_rows, typed
from jobs.sink import copy_chain

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("optionsdx")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://quantisti:quantisti@postgres:5432/quantisti")
ROWS_PER_PARTITION = 200_000        # one COPY + one transaction per partition


def input_files(folder: str, years):
    files = sorted(glob.glob(os.path.join(folder, "spx_eod_*.txt")))
    if years:
        files = [f for f in files if os.path.basename(f)[8:12] in years]
    if not files:
        raise SystemExit(f"No spx_eod_*.txt files in {folder}" + (f" for years {sorted(years)}" if years else ""))
    return files


def partition_writer(written):
    """foreachPartition function; `written` is a Spark accumulator, so the driver learns the real total."""
    def write_partition(rows) -> None:
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn:                               # one transaction per partition
                written.add(copy_chain(conn, (tuple(r) for r in rows)))
        finally:
            conn.close()
    return write_partition


def print_unusable_days(classified) -> None:
    """Quote days in the files that produced no kept contract at all (e.g. a vendor day with blank bids)."""
    days = (classified.groupBy("snapshot_date")
            .agg(F.sum(F.when(F.col("status") == "kept", 1).otherwise(0)).alias("kept"))
            .where("kept = 0").orderBy("snapshot_date").collect())
    if days:
        listed = ", ".join(str(r.snapshot_date) for r in days[:20]) + (" ..." if len(days) > 20 else "")
        print(f"\n{len(days)} quote day(s) with no usable quotes (they stay synthetic): {listed}")


def print_summary(stats) -> None:
    """stats: rows of (year, status, contracts, days)."""
    by_year = defaultdict(dict)
    days = {}
    for r in stats:
        by_year[r.year][r.status] = r.contracts
        if r.status == "kept":
            days[r.year] = r.days
    statuses = sorted({s for counts in by_year.values() for s in counts if s != "kept"})
    print("\n'kept' is before merging shifted Thursday labels that duplicate a real Friday expiry.")
    print(f"{'year':>4} {'days':>5} {'kept':>11}  " + "  ".join(f"{s:>28}" for s in statuses))
    for year in sorted(by_year):
        counts = by_year[year]
        print(f"{year:>4} {days.get(year, 0):>5} {counts.get('kept', 0):>11,}  "
              + "  ".join(f"{counts.get(s, 0):>28,}" for s in statuses))


def main() -> None:
    parser = argparse.ArgumentParser(description="Import OptionsDX SPX EOD files into option_chain_snapshots")
    parser.add_argument("--input", default="/data/optionsdx/spx")
    parser.add_argument("--years", help="comma-separated, e.g. 2010,2011 (default: every file)")
    parser.add_argument("--max-dte", type=float, default=60)
    parser.add_argument("--moneyness", type=float, default=0.10)
    parser.add_argument("--dry-run", action="store_true", help="summarise only, write nothing")
    args = parser.parse_args()
    years = set(args.years.split(",")) if args.years else None

    files = input_files(args.input, years)
    # 1. Header check on every file, before Spark reads a single row.
    first_lines = {}
    for path in files:
        with open(path, encoding="utf8") as fh:
            first_lines[path] = fh.readline()
    check_headers(first_lines)
    log.info("%d files, headers OK", len(files))

    spark = (SparkSession.builder.appName("import-optionsdx")
             .config("spark.sql.session.timeZone", "UTC")
             .config("spark.sql.shuffle.partitions", "64")
             .getOrCreate())
    spark.sparkContext.setLogLevel("WARN")

    # 2. Schema-on-read: everything arrives as strings; positions are fixed by the checked header.
    raw = (spark.read.option("header", True).option("ignoreLeadingWhiteSpace", True)
           .option("ignoreTrailingWhiteSpace", True).csv(files)
           .toDF(*EXPECTED_COLUMNS))
    wide = typed(raw)

    # 3. Expiry labels -> settlement dates (a few thousand distinct labels: map them on the driver).
    labels = [r.label for r in wide.select("label").where(F.col("label").isNotNull()).distinct().collect()]
    expiries = expiry_map_frame(spark, labels)
    shifted = sum(1 for r in expiries.collect() if r.shifted)
    log.info("%d distinct expiry labels, %d Thursday labels moved to Friday", len(labels), shifted)
    wide = wide.join(F.broadcast(expiries), "label", "left")

    # 4. Unpivot C/P and give every contract a status; persisted because it's used twice (summary + write).
    classified = classify(wide, args.max_dte, args.moneyness).persist(StorageLevel.MEMORY_AND_DISK)
    stats = (classified.groupBy(F.year("snapshot_date").alias("year"), "status")
             .agg(F.count("*").alias("contracts"), F.countDistinct("snapshot_date").alias("days"))
             .collect())
    print_summary(stats)
    print_unusable_days(classified)

    kept = sum(r.contracts for r in stats if r.status == "kept")
    if args.dry_run:
        log.info("dry run: %d contracts would be written", kept)
    else:
        # 5. Write: one COPY-based upsert per partition.
        partitions = max(1, kept // ROWS_PER_PARTITION)
        written = spark.sparkContext.accumulator(0)
        kept_rows(classified).repartition(partitions).foreachPartition(partition_writer(written))
        # kept - written = shifted Thursday labels that met a real Friday expiry at the same strike (real one kept).
        log.info("wrote %d contracts to option_chain_snapshots (source optionsdx) in %d batches; "
                 "%d duplicate shifted-expiry rows merged", written.value, partitions, kept - written.value)
    classified.unpersist()
    spark.stop()


if __name__ == "__main__":
    main()
