# Stream processing (Spark)

Spark jobs that move market data from Kafka into Postgres, plus a batch job for historical option chains.
Image: `apache/spark:3.5.3-scala2.12-java17-python3-ubuntu` (Python 3.10) with the Kafka connector jars built in.
The transforms are pure functions in `jobs/transforms.py` and `jobs/optionsdx.py`; I/O lives in `stream_main.py`,
`sink.py` and `import_optionsdx.py`.

## Streaming job (`jobs/stream_main.py`, container `spark`)

Four independent Structured Streaming queries, one micro-batch every 30 s (`TRIGGER_INTERVAL`):

| Query | Reads | Writes |
|---|---|---|
| `daily` | `market.daily` | `underlying_daily`, `vix_daily`, `rates_daily`, `index_daily` (VIX9D, VIX3M, VVIX, SKEW, BAA10Y, T10Y2Y); recomputes 30-day historical volatility from the earliest changed day |
| `chain` | `options.chain.quotes` | `option_chain_snapshots`, one row per contract per session |
| `bars_1m` | `market.bars.1m` | `intraday_bars` at the interval each bar was published with (1m, 5m or 1h) |
| `bars_5m` | `market.bars.1m` | `intraday_bars` 5m rows built from 1m bars (`source = 'agg_1m'`), event-time windows with a 10 min watermark |

Spark UI: http://localhost:4040 -> Structured Streaming.

**Replays are safe.** Each query keeps its Kafka offsets in a checkpoint (volume `spark_checkpoints`). After a crash
Spark re-runs the last micro-batch, and every write is an upsert, so writing the same rows twice leaves the
tables as writing them once. To reprocess everything Kafka still holds (7 days), stop `spark`, delete the volume,
and start it again.

**What wins when rows collide:**

- Chains: an older capture never replaces a newer one. A capture with no bid or ask doesn't replace a stored
  quote that has both (CBOE sometimes publishes one, as on 2026-10-05 at 16:14 ET); open interest and volume
  always take the newest values.
- Bars: a vendor bar (Yahoo) replaces anything; a 5m bar built from 1m bars only replaces another built one,
  because it can miss a minute.
- Daily rows: the newest message for a day.

**Dead-letter queue.** Messages a query can't use go to `ingest.dlq` with the reason, instead of being dropped
or stopping the query: unparseable JSON, unexpected schema, payload that doesn't match, and for bars unknown
symbol or interval, missing or non-positive price, high < low, open/close outside the high-low range, negative volume.
Read them in Kafka UI (http://localhost:8089 -> `ingest.dlq`).

## OptionsDX import (`jobs/import_optionsdx.py`, container `spark-import`)

A batch job: real end-of-day SPX chains for 2010-2023 from OptionsDX's free files.

1. Register at optionsdx.com and download the SPX end-of-day files (`spx_eod_YYYYMM.txt`). Put them in
   `data/optionsdx/spx/` (git-ignored).
2. Run the import (it checks every file's headers first and stops if the format differs):

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.streaming.yml --profile tools run --rm spark-import
   ```

   One year only (add `--dry-run` to print the summary without writing):

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.streaming.yml --profile tools run --rm spark-import \
     /opt/spark/bin/spark-submit --master "local[4]" --driver-memory 4g --conf spark.sql.session.timeZone=UTC \
     jobs/import_optionsdx.py --input /data/optionsdx/spx --years 2023
   ```

   In PowerShell, end the lines with a backtick (`` ` ``) instead of `\`. In Git Bash, prefix the command with
   `MSYS_NO_PATHCONV=1` so `/opt/...` isn't rewritten into a Windows path.

It unpivots each row into a call and a put, maps OptionsDX expiry labels to settlement dates (Thursday labels of
Friday AM expiries move to the Friday), keeps expiries up to 60 days out and strikes within +/-10% of spot
(`--max-dte`, `--moneyness`), drops contracts without a two-sided quote, and bulk-upserts with
`source = 'optionsdx'` and `quoted_at` at 16:00 ET. It prints a per-year summary of days, kept and rejected
contracts. Re-running is safe.

All 14 years come to about 8.9M rows over 3,491 sessions. What the files don't have:

- **Open interest**: none (stored as NULL), so the market service computes the put/call ratio from volume.
- **43 sessions**: 2010-01-27..02-05 are blank (listed as a known range), and 35 others are simply absent,
  for example 2021-08-09 and 2021-08-31. The gap detector reports those 35 as unrecoverable; no free source has them.
- **Contracts with a zero bid** (far out of the money) are dropped, so some backtest weeks are skipped.

## Tests

```bash
docker compose -f docker-compose.yml -f docker-compose.streaming.yml build spark
docker compose -f docker-compose.yml -f docker-compose.streaming.yml run --rm --no-deps spark pytest -q
```

Transform tests run on a local Spark session. Sink tests run against the real Postgres inside a transaction that
is always rolled back, and are skipped when Postgres isn't reachable.
