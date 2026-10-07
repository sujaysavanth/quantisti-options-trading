# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Quantisti: a microservice options-trading simulator for **SPX (S&P 500 index) options**: USD, x100 multiplier, 5-pt strikes, European/cash-settled, daily expiries on the NYSE calendar. It was originally built for NIFTY (India); `schema/sql/008_us_market.sql` converts old databases. Python FastAPI services + two Next.js apps. It's a portfolio project; sample/illustrative data on the landing page is intentional. The local folder is named `quant-finance-simulator` but the git remote is `github.com/sujaysavanth/quantisti-options-trading`.

## Commands

Full stack (Postgres + all services):
```bash
docker compose --env-file .env.development up --build          # dev, gateway AUTH_DISABLED=true via docker-compose.override.yml
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up --build
docker compose up postgres market simulator market_stream       # just the pieces the dashboard needs
# Streaming data pipeline (Kafka, ingest, stream-bridge, Spark) on top of the base file:
docker compose -f docker-compose.yml -f docker-compose.streaming.yml up -d --build
```

Database (schema is plain SQL, no migration tool):
```bash
DATABASE_URL=postgresql://quantisti:quantisti@localhost:5432/quantisti ./scripts/db_apply.sh   # applies schema/sql/*.sql in glob order
# ML tables live separately and are NOT applied by db_apply.sh (001, 002, then 003; 003 is safe to re-run):
docker compose exec -T postgres psql -U quantisti -d quantisti < services/ml/migrations/001_create_weekly_features_table.sql
python scripts/populate_us_data.py --start-date 2010-01-01   # daily history (needs `pip install -e services/ingest`); the pipeline keeps it current
```
Loading order for a fresh database is in `docs/getting-started.md`: schema, daily history, intraday backfill
(`exec ingest python -m app.cli backfill-intraday --max`), OptionsDX import (`services/stream-processing/README.md`),
then a gap scan (`POST localhost:8088/v1/gaps/scan`). `scripts/spx_chain_snapshot.py` still writes one chain
straight to Postgres without Kafka, but the pipeline now collects chains automatically.

Single service locally (each service is its own installable package named `app`):
```bash
cd services/<svc> && pip install -e . && PORT=8082 uvicorn app.main:app --reload --port 8082
```

Tests: pytest suites in `services/{market,simulator,ml,ingest}/tests` (calendar, pricing, chain building, backtest legs, metrics, VIX features, pollers, gap detection), and `services/stream-processing/tests`, which run in the Spark image: `docker compose -f docker-compose.yml -f docker-compose.streaming.yml run --rm --no-deps spark pytest -q`. Run per service: `cd services/market && pip install -e ".[test]" && pytest -q` (single test: `pytest tests/test_market_spec.py::test_next_expiry -q`). CI (`.github/workflows/ci.yml`, every branch and PR) is blocking: those test suites, the Spark tests against a Postgres service container, `ruff check services scripts` (rules in `ruff.toml`: E9 + pyflakes), `npm run build` for both frontends, and every Docker image.

Frontends (Node, independent npm projects):
```bash
cd landing && npm install && npm run dev            # marketing site, :3000 (Next 15 / React 19)
cd services/strategy-dashboard && npm install && npm run dev   # trading dashboard (Next 14 / React 18, Recharts)
npm run build / npm run lint                        # in either app
```
The dashboard reads `NEXT_PUBLIC_SIMULATOR_API` (default `http://localhost:8082`) and `NEXT_PUBLIC_MARKET_STREAM_API` (default `http://localhost:8090`).

## Architecture

Ports: gateway 8080, market 8081, simulator 8082, portfolio 8083, stats 8084, ml 8085, explain 8086, market-stream 8090. Streaming stack: ingest **8088** on the host (8087 in the container; `INGEST_HOST_PORT`), Kafka UI 8089, Spark UI 4040, Kafka `localhost:9094` for host tools (`kafka:9092` inside compose). Every service exposes `/health/healthz` and `/health/readyz`, and FastAPI docs at `/docs`.

**Implemented** services (the rest — gateway, portfolio, stats, explain — are health-only stubs):

- **market** — SPX data. `/v1/underlying/{spot,historical,candles/{period},vix}` read `underlying_daily` / `vix_daily` (`/spot` is deliberately the latest *close*: backtests and ml rely on it); `/v1/underlying/intraday?symbol=&interval=&date=` reads `intraday_bars`. `/v1/options/chain` returns `source: snapshot` (real quotes from `option_chain_snapshots`, one source per day by `SNAPSHOT_SOURCE_PRIORITY`; forward from put-call parity, IV recomputed from mids — vendor IV/spot are unreliable) or `source: synthetic` (Black-Scholes, VIX-anchored smile, FRED rate by date). While a session runs (no daily row yet), the default date is today and spot is the latest intraday bar (`spot_source`), and snapshots are priced at their `quoted_at` (`as_of`) — rules in `services/live.py`. `pcr` uses open interest, else volume (OptionsDX has no OI), labelled by `pcr_basis` (`model` for synthetic). Chain logic is pure functions in `services/chains.py`; `data_provider.py` does the DB reads. `/v1/options/expiries` follows the real listing history.
- **`market_spec.py`** (in market, copied verbatim into simulator, ingest, ml and `stream-processing/jobs` — keep identical; `services/ingest/tests/test_market_spec_copy.py` checks) is the single source for contract rules and the expiry calendar (`exchange_calendars` XNYS): `round_to_strike`, `next_expiry(on, min_dte, offset)`, `valuation_time` (close of the day, or now if intraday), `year_fraction` to the 16:00 ET close (early closes included).
- **market-stream** — in-memory latest-quote store + broadcaster. Collectors push via `POST /v1/quotes`; clients read `GET /v1/quotes[/{symbol}]` or subscribe to WebSocket `/ws/quotes`. Nothing is persisted. Normally fed by `stream-bridge` (below) with ~15-min-delayed CBOE chains; `scripts/yahoo_collector.py` and `scripts/mock_quote_publisher.py` still work without Kafka.
- **ingest** (`services/ingest`, see its README) — polls free sources (CBOE delayed chains, Yahoo bars/daily, CBOE VIX, FRED) on the NYSE schedule and publishes versioned JSON envelopes to Kafka (`market.bars.1m`, `market.daily`, `options.chain.quotes`). It never writes market data to Postgres. Gap detector (`app/gaps/`) checks Postgres against the calendar into `ingest_gaps` and publishes `ingest.backfill.requests`; the backfill worker refetches onto the normal topics; a gap is `filled` only when a later check sees the rows. Same image runs **stream-bridge** (`python -m app.bridge`): Kafka -> market-stream. Chain sources plug in via the `ChainSource` protocol (`CHAIN_SOURCE`).
- **stream-processing** (`services/stream-processing`, Spark 3.5, see its README) — four Structured Streaming queries upsert Kafka into `underlying_daily`/`vix_daily`/`rates_daily`, `option_chain_snapshots` and `intraday_bars` (1m as published, 5m windows from 1m); bad messages go to `ingest.dlq`. Upserts make replays harmless. `jobs/import_optionsdx.py` (container `spark-import`, compose profile `tools`) loads OptionsDX 2010-2023 end-of-day chains from git-ignored `data/optionsdx/spx/`.
- **simulator** — the main business logic:
  - `/v1/strategies` (DB-defined strategy templates + legs) and `/v1/backtests` (create → `POST /{id}/run` executes `BacktestEngine` as a FastAPI background task → `/trades`, `/metrics`). Backtests enter at the close on NYSE sessions, price legs via the market service, use the nearest expiry >= 1 day out (`expiry_offset` = weeks further for calendars), size legs x100, and settle at the expiry close; trades whose expiry is past the loaded data are skipped. Metrics in `metrics_calculator.py` (Sharpe/Sortino on returns on capital, annualised by entry frequency).
  - `/v1/strategies-live` — `strategy_builder.py` builds weekly strategies (long call/put, straddle, strangle, spreads, iron condor…) from the current market-stream quote, stepping strikes in 25-point increments (`STEP`).
  - `/v1/paper/orders` — paper trades persisted in Postgres (`paper_store.py`), marked to market against market-stream quotes.
  - Downstream URLs: `MARKET_SERVICE_URL`, `MARKET_STREAM_URL` (defaults to compose hostnames `market`, `market_stream`).
- **ml** — weekly dataset for the SPX range forecast (no model/predict endpoint yet; plan in progress). `app/dataset/`: weeks anchored on their last session (= SPX expiry); `build_features` is pure and vectorised over `underlying_daily`/`vix_daily`/`rates_daily`, point in time (tested for lookahead), shared by training and serving; `build_labels` = next week's expiry-close log return plus high/low. Stored in `weekly_features` (legacy columns + `MODEL_FEATURES`) and `weekly_labels`. `POST /v1/features/backfill` rebuilds all weeks in ~1 s; `python -m app.cli build-dataset [--export ...]`. `app/evaluation/`: quantile metrics (pinball, coverage, Winkler, coverage by VIX regime), baselines (raw/scaled VIX, 20d RV, HAR-RV, GARCH via `arch`, ATM straddle from OptionsDX) and a walk-forward runner by test year; `python -m app.cli evaluate` writes `data/ml/reports/baselines.{md,json}`. Has its own `market_spec.py` copy.

Service conventions: `app/main.py` wires routers; `app/config.py` is a pydantic-settings `Settings` read from env; `app/db/connection.py` holds a psycopg2 connection pool (raw SQL with `RealDictCursor`, no ORM). Services start even if the DB is down and report it via health checks. CORS is `*` everywhere.

**strategy-dashboard** mixes live and mock data: strategies/paper orders come from the simulator API, while the weekly prediction (range, closing estimate, VIX/PCR context) still comes from `data/mockDashboard.ts` because the ML predict endpoint doesn't exist.

**Schema**: `schema/sql/` numbered files — RBAC (users/roles/permissions/audit, roles Basic/Premium/Admin per `docs/security-rbac.md`), market data, strategies/backtests, paper trading, multi-expiry, `008` NIFTY->SPX conversion, `009` streaming (`intraday_bars`, `ingest_gaps`, `quoted_at`/vendor IV columns on chain snapshots), `010` Yahoo overnight OI fix. `db_apply.sh` re-runs every file, so keep migrations idempotent (seeds are insert-if-missing). Option types are `C`/`P` in strategy/backtest tables but `CALL`/`PUT` in paper trading and market-stream. Two files share the `006_` prefix; order is alphabetical.

Free-data limits: chains are ~15 min delayed; 2024 until live collection started (2026-10-01) has no real chains (synthetic); Yahoo keeps 1m bars ~30 days, 5m 60 days, 1h ~2 years; OptionsDX lacks 43 sessions and all open interest. In Git Bash, prefix docker commands containing `/opt/...` with `MSYS_NO_PATHCONV=1`.

`docs/architecture.md` and `docs/strategy-engine.md` describe the *target* design (Firebase auth, Cloud SQL, SHAP explain, sentiment scoring) — much of it is not built. `infra/` (Terraform, Cloud Run) is README-only.

## Landing page work

`landing/` uses an Apple-style design with illustrative SPX data computed by Black-Scholes in `landing/data/showcase.ts` — follow `docs/landing-redesign-plan.md` (section flow, tokens, motion rules) and `docs/ui-reference.md` (options-chain and trading UI references).
