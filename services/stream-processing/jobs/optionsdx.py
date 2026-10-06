"""OptionsDX SPX end-of-day files -> option_chain_snapshots rows. Pure functions; I/O lives in import_optionsdx.py.

The files are wide: one row per (quote date, expiry, strike) with the call in C_* columns and
the put in P_* columns. Three quirks, all checked against the 2010-2023 files:

1. Expiry labels. Friday morning-settled expiries (the monthlies, and in 2010 almost every
   weekly) are labelled with the last trading day, the Thursday before. We store every expiry
   as its settlement date, so such a Thursday becomes the Friday, but only when the Thursday
   isn't an expiry itself and the Friday is. Month-end and quarter-end expiries (e.g. Jun 30)
   are real contracts our calendar doesn't model; they are kept as labelled.
2. No open interest in the files: stored as NULL ("unknown"), never 0.
3. Blank cells for missing values (e.g. no IV on deep in-the-money calls).
"""

from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F

from . import market_spec

# The header every file must have, in order (brackets and spaces stripped).
EXPECTED_COLUMNS = [
    "QUOTE_UNIXTIME", "QUOTE_READTIME", "QUOTE_DATE", "QUOTE_TIME_HOURS", "UNDERLYING_LAST", "EXPIRE_DATE",
    "EXPIRE_UNIX", "DTE", "C_DELTA", "C_GAMMA", "C_VEGA", "C_THETA", "C_RHO", "C_IV", "C_VOLUME", "C_LAST",
    "C_SIZE", "C_BID", "C_ASK", "STRIKE", "P_BID", "P_ASK", "P_SIZE", "P_LAST", "P_DELTA", "P_GAMMA", "P_VEGA",
    "P_THETA", "P_RHO", "P_IV", "P_VOLUME", "STRIKE_DISTANCE", "STRIKE_DISTANCE_PCT",
]

SOURCE = "optionsdx"


def parse_header(line: str) -> List[str]:
    return [c.strip().strip("[]").strip() for c in line.strip().split(",")]


def check_headers(first_lines: Dict[str, str]) -> None:
    """Fail loudly, naming every file whose header differs, before reading any data."""
    bad = {path: parse_header(line) for path, line in first_lines.items() if parse_header(line) != EXPECTED_COLUMNS}
    if bad:
        path, cols = next(iter(bad.items()))
        missing = [c for c in EXPECTED_COLUMNS if c not in cols]
        extra = [c for c in cols if c not in EXPECTED_COLUMNS]
        raise ValueError(f"{len(bad)} file(s) don't have the expected OptionsDX header, e.g. {path}: "
                         f"missing {missing}, unexpected {extra}. Update EXPECTED_COLUMNS / the mapping first.")


def map_expiry(label: date) -> Optional[Tuple[date, bool]]:
    """OptionsDX expiry label -> (settlement date, shifted?), or None if it can't be a real expiry."""
    try:
        # Thursday that isn't an expiry itself (including a holiday Thursday such as Thanksgiving 2010,
        # which OptionsDX used as the label for Friday Nov 26): the contract settles on the Friday.
        if label.weekday() == 3 and not market_spec.is_expiry(label):
            friday = label + timedelta(days=1)
            if market_spec.is_trading_day(friday) and market_spec.is_expiry(friday):
                return friday, True
        if not market_spec.is_trading_day(label):
            return None
    except Exception:                                                          # beyond the calendar's range
        return None
    return label, False


def expiry_map_frame(spark: SparkSession, labels: List[date]) -> DataFrame:
    """Small lookup table label -> expiry_date/shifted, computed on the driver (a few thousand dates)."""
    rows = []
    for label in labels:
        mapped = map_expiry(label)
        rows.append((label, mapped[0] if mapped else None, mapped[1] if mapped else None))
    return spark.createDataFrame(rows, "label date, expiry_date date, shifted boolean")


def typed(raw: DataFrame) -> DataFrame:
    """Raw string columns -> typed, renamed columns (only the ones we use)."""
    num = lambda c: F.col(c).cast("double")                                    # noqa: E731  blank -> null
    return raw.select(
        F.to_date("QUOTE_DATE").alias("snapshot_date"),
        # 16:00 ET normally, 13:00 on early closes; stored as UTC.
        F.to_utc_timestamp(F.to_timestamp("QUOTE_READTIME", "yyyy-MM-dd HH:mm"), "America/New_York").alias("quoted_at"),
        num("UNDERLYING_LAST").alias("underlying_price"),
        F.to_date("EXPIRE_DATE").alias("label"),
        num("DTE").alias("dte"),
        num("STRIKE").alias("strike"),
        *[num(f"{side}_{field}").alias(f"{side.lower()}_{field.lower()}")
          for side in ("C", "P") for field in ("BID", "ASK", "LAST", "VOLUME", "IV", "DELTA")],
    )


def unpivot(wide: DataFrame) -> DataFrame:
    """One row per strike -> one row per contract (C and P)."""
    def side(letter: str) -> DataFrame:
        p = letter.lower()
        return wide.select(
            "snapshot_date", "quoted_at", "underlying_price", "label", "dte", "strike", "expiry_date", "shifted",
            F.lit(letter).alias("option_type"),
            F.col(f"{p}_bid").alias("bid"), F.col(f"{p}_ask").alias("ask"), F.col(f"{p}_last").alias("last"),
            F.col(f"{p}_volume").cast("long").alias("volume"),
            F.col(f"{p}_iv").alias("vendor_iv"), F.col(f"{p}_delta").alias("vendor_delta"),
        )
    return side("C").unionByName(side("P"))


def classify(wide_with_expiry: DataFrame, max_dte: float, moneyness: float) -> DataFrame:
    """Contract rows with a `status`: 'kept', 'filtered: ...' (by choice) or 'rejected: ...' (bad data)."""
    rows = unpivot(wide_with_expiry)
    two_sided = (F.col("bid") > 0) & (F.col("ask") > 0) & (F.col("ask") >= F.col("bid"))
    status = (
        F.when(F.col("snapshot_date").isNull() | F.col("quoted_at").isNull(), "rejected: bad quote date")
        .when(F.col("strike").isNull() | (F.col("strike") <= 0) | F.col("underlying_price").isNull()
              | (F.col("underlying_price") <= 0), "rejected: bad strike or underlying")
        .when(F.col("dte").isNull() | (F.col("dte") < 0) | (F.col("dte") > max_dte), "filtered: dte")
        .when(F.abs(F.col("strike") / F.col("underlying_price") - 1) > moneyness, "filtered: moneyness")
        .when(F.col("expiry_date").isNull(), "rejected: expiry not a trading day")
        .when(~F.coalesce(two_sided, F.lit(False)), "rejected: no two-sided quote")
        .otherwise("kept")
    )
    return rows.withColumn("status", status)


def kept_rows(classified: DataFrame) -> DataFrame:
    """Kept contracts in option_chain_snapshots column order, one per key.

    A shifted Thursday label could meet a real Friday label at the same strike; the real one wins.
    """
    key = ["snapshot_date", "expiry_date", "strike", "option_type"]
    w = Window.partitionBy(*key).orderBy(F.col("shifted").asc())
    return (
        classified.where(F.col("status") == "kept")
        .withColumn("_rank", F.row_number().over(w)).where("_rank = 1")
        .select(
            F.lit("SPX").alias("symbol"), "snapshot_date", "expiry_date", "strike", "option_type", "underlying_price",
            "bid", "ask", "last", F.lit(None).cast("long").alias("open_interest"), "volume",
            "vendor_iv", "vendor_delta", "quoted_at", F.lit(SOURCE).alias("source"),
        )
    )
