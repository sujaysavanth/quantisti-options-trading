# Getting Started

How to run Quantisti locally: the services, the streaming data pipeline, and the data they need.
Commands are PowerShell (Windows PowerShell 5.1 or PowerShell 7); bash equivalents follow where they differ.

## Prerequisites
- Docker Desktop (Compose v2). Give it at least 8 GB of memory if you'll run the OptionsDX import.
- Python 3.11, to load the daily history from your machine.
- Node 20+, for the dashboard.

## 1. Database

```powershell
docker compose up -d --wait postgres          # --wait returns once Postgres is healthy
# Apply every schema file in order (safe to re-run):
Get-ChildItem schema\sql\*.sql | Sort-Object Name | ForEach-Object {
  Get-Content $_.FullName -Raw | docker exec -i quantisti-postgres psql -q -U quantisti -d quantisti -v ON_ERROR_STOP=1 }
```
bash: `DATABASE_URL=postgresql://quantisti:quantisti@localhost:5432/quantisti ./scripts/db_apply.sh`

## 2. Daily history (SPX, VIX, T-bill rates)

The pipeline only fetches the last few days on each run, so load the history once from your machine:

```powershell
python -m venv .venv; .venv\Scripts\Activate.ps1   # if scripts are blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -e services\ingest
$env:DATABASE_URL = "postgresql://quantisti:quantisti@localhost:5432/quantisti"
python scripts\populate_us_data.py --start-date 2010-01-01      # ~4,200 sessions; takes a minute
```

If `pip install` fails with "No such file or directory" deep inside `site-packages`, the folder path is too long for
Windows (260 characters): clone into a shorter folder, or enable long paths.

## 3. Services and the streaming pipeline

```powershell
docker compose -f docker-compose.yml -f docker-compose.streaming.yml up -d --build `
  postgres market simulator market_stream kafka kafka-init kafka-ui ingest stream-bridge spark
docker compose -f docker-compose.yml -f docker-compose.streaming.yml ps     # ingest and kafka "healthy"
```

Leave out the service names to start everything, including the health-only stubs (gateway, portfolio, stats, ml, explain).

From now on, during market hours the ingest service publishes SPX/VIX bars every 60 s and the option chain every 90 s
(CBOE, ~15 min delayed). After each close it publishes the closing chain and the daily rows. Spark writes all of
it to Postgres, and stream-bridge keeps market-stream (and so the dashboard) up to date.

## 4. Intraday history

Yahoo serves 1m bars for ~30 days, 5m for 60 days and 1h for ~2 years. Fetch all of it once:

```powershell
docker compose -f docker-compose.yml -f docker-compose.streaming.yml exec ingest python -m app.cli backfill-intraday --max
```

## 5. Historical option chains (optional, 2010-2023)

Without this, backtests before October 2026 price options with Black-Scholes from VIX. With it, 2010-2023
use real end-of-day quotes. Download OptionsDX's free SPX end-of-day files (`spx_eod_YYYYMM.txt`) into
`data\optionsdx\spx\`, then:

```powershell
# One year (about a minute):
docker compose -f docker-compose.yml -f docker-compose.streaming.yml --profile tools run --rm spark-import `
  /opt/spark/bin/spark-submit --master "local[4]" --driver-memory 4g --conf spark.sql.session.timeZone=UTC `
  jobs/import_optionsdx.py --input /data/optionsdx/spx --years 2023
# Every file in the folder:
docker compose -f docker-compose.yml -f docker-compose.streaming.yml --profile tools run --rm spark-import
```

What the import keeps and what the files lack: [`services/stream-processing/README.md`](../services/stream-processing/README.md#optionsdx-import-jobsimport_optionsdxpy-container-spark-import).

## 6. Check for gaps

```powershell
irm http://localhost:8088/v1/gaps/scan -Method Post    # also runs hourly by itself
(irm http://localhost:8088/v1/gaps).counts             # gaps per dataset and status
```

Gaps a free source still has are refilled automatically. The rest are marked `unrecoverable` (see
[`services/ingest/README.md`](../services/ingest/README.md#gap-detector-and-backfill-worker-appgaps-appbackfill)).

On a new setup, expect two things:
- The first automatic scan runs a minute after ingest starts, usually before steps 4 and 5 are done, so it records
  gaps for data you were about to load. Later scans mark them `filled` once the rows are there, even ones already
  marked `unrecoverable`.
- OptionsDX years you haven't imported show up as `unrecoverable` chain gaps (about 250 a year). Import them
  later and the next scan marks them `filled`.

## 7. Dashboard

```powershell
cd services\strategy-dashboard; npm install; npm run dev     # http://localhost:3000
```

## Where things are

| | URL |
|---|---|
| Market API (SPX data, chains) | http://localhost:8081/docs |
| Simulator API (strategies, backtests, paper trading) | http://localhost:8082/docs |
| market-stream (latest quotes, WebSocket) | http://localhost:8090/docs |
| Ingest (pollers, gaps) | http://localhost:8088/docs |
| Kafka UI (topics, messages, DLQ) | http://localhost:8089 |
| Spark UI (streaming queries) | http://localhost:4040 |
| Dashboard | http://localhost:3000 |
| Stubs: gateway, portfolio, stats, ml, explain | :8080, :8083 - :8086 |

Every API has `/health/healthz` and `/health/readyz`. Ingest uses host port 8088 (set `INGEST_HOST_PORT` to change it).

## Stopping

```powershell
docker compose -f docker-compose.yml -f docker-compose.streaming.yml down      # keeps all data
```

`down -v` also deletes the volumes: the Postgres data (including any OptionsDX import), Kafka's topics and Spark's checkpoints.

## Adding a new service
1. Create `services/<service-name>/` with an `app/` package (`main.py`, `config.py`, `routers/`).
2. Add a `pyproject.toml` listing FastAPI and Uvicorn.
3. Add a Dockerfile like the existing services and pick the next free port.
4. Add it to `docker-compose.yml` and the CI workflow.
