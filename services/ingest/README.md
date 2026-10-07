# Ingest service

Fetches SPX/VIX market data, SPX option chains and T-bill rates from free sources and publishes them to Kafka.
It also finds missing data and requests backfills. It never writes market data to Postgres itself: Spark
(`services/stream-processing`) does that, so live data and backfills go through the same validation and upserts.

One image, two containers (`docker-compose.streaming.yml`):

| Container | Entry point | Does |
|---|---|---|
| `ingest` | `uvicorn app.main:app` (port 8087 inside, **8088** on the host) | pollers, gap scans, backfill worker, HTTP API |
| `stream-bridge` | `python -m app.bridge` | Kafka -> market-stream (`:8090`), which feeds the dashboard and paper-trade P&L |

## Sources (`app/sources/`)

| Data | Source | Notes |
|---|---|---|
| SPX option chain | **CBOE delayed quotes** (`cboe.py`, default) | ~15 min delayed, one request for the whole chain, has open interest |
| SPX option chain (fallback) | Yahoo (`yahoo.py`, `CHAIN_SOURCE=yahoo`) | one request per expiry, no reliable open interest |
| SPX/VIX intraday bars | Yahoo | 1m for ~30 days back, 5m for 60 days, 1h for ~730 days (`yahoo.LIMITS`) |
| SPX daily | Yahoo `^GSPC` | |
| VIX daily | CBOE `VIX_History.csv` | can lag a day |
| 3-month T-bill | FRED `DGS3MO` | posts a day or more late |
| Index series (`app/sources/indexes.py`) | CBOE `VIX9D`, `VIX3M`, `VVIX`, `SKEW` history files; FRED `BAA10Y`, `T10Y2Y` | features for the range forecast, stored in `index_daily` |

FRED's ICE high-yield spread (`BAMLH0A0HYM2`) only serves about 3 years of history (licensing), so the Moody's
`BAA10Y` spread stands in for credit stress. FRED can take over a minute to answer; requests wait up to 150 s.

Every quote is stamped with the time it was taken (`quoted_at`) and the trading session it belongs to
(`app/sources/session.py`): quotes taken after 20:15 ET belong to the next day's session (CBOE's overnight hours).

### Adding a paid chain source

1. Write a class with `name`, `delay_minutes` and `fetch_chain(expiries, moneyness) -> ChainSnapshot`
   (the `ChainSource` protocol in `app/sources/base.py`). Return `open_interest=None` when the provider doesn't
   give it, never 0.
2. Return it from `chain_source()` in `app/sources/__init__.py`.
3. Add its name to `CHAIN_SOURCE` in `app/config.py` and to `SNAPSHOT_SOURCE_PRIORITY` in
   `services/market/app/services/chains.py` (which source wins when several captured the same day).
4. Set `CHAIN_SOURCE=<name>` on the `ingest` container. Nothing downstream changes: messages carry `source`
   and `delay_minutes`, and the dashboard's "Delayed N min" badge reads them.

## Pollers (`app/producers/`)

All run in one background thread; the schedule comes from the NYSE calendar (`market_spec.py`).

| Poller | When | Publishes to |
|---|---|---|
| intraday | every 60 s while the market is open | `market.bars.1m` (1m bars newer than the last one sent) |
| chain | every 90 s while open, plus the closing chain | `options.chain.quotes` (nearest 5 expiries, strikes within +/-5%) |
| end of day | once per session, from 16:20 ET (13:20 on early closes) | final bars, closing chain, and the last 7 days of daily rows to `market.daily` |

A rate limit (HTTP 429) pauses the chain poller with backoff. A failed poll is logged and retried next time.

## Topics

Created by `infra/kafka/create-topics.sh` (the `kafka-init` container). Messages are JSON envelopes,
`{"schema": "bars.v1", "source": "yahoo", "delay_minutes": 15, "produced_at": ..., "payload": {...}}`,
validated with pydantic in `app/producers/envelope.py`.

| Topic | Key | Schema | Partitions / retention |
|---|---|---|---|
| `market.bars.1m` | symbol | `bars.v1` (each message carries its `interval`: 1m, 5m or 1h) | 3 / 7 days |
| `market.daily` | `dataset:symbol` | `daily.v1` | 1 / 7 days |
| `options.chain.quotes` | `symbol:expiry` | `chain.v1`, one message per expiry per poll | 3 / 7 days |
| `ingest.backfill.requests` | `dataset:date` | `backfill.v1` | 1 / 7 days |
| `ingest.dlq` | the topic it came from | `{"job", "topic", "reason", "failed_at", "value"}` | 1 / 30 days |

Postgres is the system of record; Kafka only keeps data long enough to replay.

## Gap detector and backfill worker (`app/gaps/`, `app/backfill/`)

The detector compares Postgres with the NYSE calendar and records what's missing in `ingest_gaps`:

| Dataset | Checked | A gap is |
|---|---|---|
| `daily` (SPX) | every session since 2010-01-04 | no row |
| `vix` | the same, except the latest session | no row |
| `rates` | the same | more than 3 sessions missing in a row |
| `index` (`VIX9D` ...) | each series from its start date | CBOE series as for `vix`, FRED series as for `rates` |
| `intraday` (`SPX:1m` ...) | only sessions Yahoo still serves at that size | fewer than 98% of the session's bars (390/78/7, or 210/42/4 on early closes) |
| `chain` | OptionsDX years (2010-2023) and every session since live collection began | no rows |

Ranges no free source can fill are listed once as **known** instead of as one gap per day (`KNOWN_RANGES` in
`detector.py`): blank OptionsDX days in early 2010, and 2024 until live collection started, where the
market service prices synthetic chains.

How a gap moves:

- `requested`: a `backfill.v1` request is published. The worker (consumer group `ingest-backfill`) fetches the
  session and publishes it to the normal data topics.
- `filled`: set by a **later check that finds the rows in Postgres**, never when the request is published.
- `unrecoverable`: the source can no longer supply the data (a past chain day, or intraday bars older than
  Yahoo's window), or 3 requests didn't bring it back. In the second case the request is also copied to `ingest.dlq`.

A full scan runs hourly (the first one a minute after startup). A cheaper check of `requested` gaps runs
every 2 minutes. Both checks also look at `unrecoverable` gaps, so data loaded later by hand (an OptionsDX
import, `populate_us_data.py`) turns them `filled`.

## API

| Endpoint | |
|---|---|
| `GET /health/healthz`, `GET /health/readyz` | ready when Kafka answers; also reports whether Postgres answers |
| `GET /v1/producers` | last run of each poller, messages delivered or failed per topic |
| `POST /v1/gaps/scan` | run a gap scan now |
| `GET /v1/gaps?status=&dataset=&limit=` | gaps (newest first), counts, known ranges, last scan, worker stats |

## CLI

Inside the container (`docker compose -f docker-compose.yml -f docker-compose.streaming.yml exec ingest ...`), or from
your machine after `pip install -e services/ingest` with `--bootstrap localhost:9094` and
`--database-url postgresql://quantisti:quantisti@localhost:5432/quantisti`:

```bash
python -m app.cli fetch-chain --expiries 1 --limit 6       # print a chain (no Kafka, no database)
python -m app.cli fetch-bars --symbol SPX --interval 1m --days 1
python -m app.cli poll-once --all --force                  # run the pollers once, even outside market hours
python -m app.cli backfill-intraday --max                  # all the intraday history Yahoo still has
python -m app.cli backfill-daily --indexes --since 2010-01-01   # index series history (~25k rows via market.daily)
python -m app.cli scan-gaps --dry-run                      # print gaps; changes nothing
python -m app.cli scan-gaps                                # same as POST /v1/gaps/scan
```

## Settings

Environment variables (`app/config.py`): `KAFKA_BOOTSTRAP`, `DATABASE_URL`, `PRODUCERS_ENABLED`, `GAPS_ENABLED`,
`CHAIN_SOURCE`, `INTRADAY_POLL_SECONDS` (60), `CHAIN_POLL_SECONDS` (90), `CHAIN_EXPIRIES` (5),
`CHAIN_MONEYNESS` (0.05), `GAP_SCAN_MINUTES` (60), `GAP_RECHECK_SECONDS` (120), and for the bridge
`MARKET_STREAM_URL`, `BRIDGE_MIN_DTE`. The host port is `INGEST_HOST_PORT` (default 8088).

## Tests

```bash
cd services/ingest && pip install -e ".[test]" && pytest -q
```

No network or Kafka needed: sources take injectable fetch functions and tests use a fake producer (`tests/fakes.py`).
`tests/test_market_spec_copy.py` fails if this service's copy of `market_spec.py` drifts from the market service's.
