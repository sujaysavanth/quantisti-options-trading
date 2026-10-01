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
```

Database (schema is plain SQL, no migration tool):
```bash
DATABASE_URL=postgresql://quantisti:quantisti@localhost:5432/quantisti ./scripts/db_apply.sh   # applies schema/sql/*.sql in glob order
# ML tables live separately and are NOT applied by db_apply.sh (001 then 002):
docker compose exec -T postgres psql -U quantisti -d quantisti < services/ml/migrations/001_create_weekly_features_table.sql
python scripts/populate_us_data.py --start-date 2015-01-01   # ^GSPC, CBOE VIX, FRED DGS3MO -> underlying_daily / vix_daily / rates_daily
python scripts/spx_chain_snapshot.py --expiries 10           # daily after the close: real listed chains -> option_chain_snapshots
```

Single service locally (each service is its own installable package named `app`):
```bash
cd services/<svc> && pip install -e . && PORT=8082 uvicorn app.main:app --reload --port 8082
```

Tests: pytest suites in `services/{market,simulator,ml}/tests` (calendar, pricing, chain building, backtest legs, metrics, VIX features). Run per service: `cd services/market && pip install -e ".[test]" && pytest -q` (single test: `pytest tests/test_market_spec.py::test_next_expiry -q`). CI (`.github/workflows/ci.yml`) still runs them non-blocking (`pytest -q || true`) with a placeholder lint step. `services/ml/test_calculators.py` is an older script, run directly.

Frontends (Node, independent npm projects):
```bash
cd landing && npm install && npm run dev            # marketing site, :3000 (Next 15 / React 19)
cd services/strategy-dashboard && npm install && npm run dev   # trading dashboard (Next 14 / React 18, Recharts)
npm run build / npm run lint                        # in either app
```
The dashboard reads `NEXT_PUBLIC_SIMULATOR_API` (default `http://localhost:8082`) and `NEXT_PUBLIC_MARKET_STREAM_API` (default `http://localhost:8090`).

## Architecture

Ports: gateway 8080, market 8081, simulator 8082, portfolio 8083, stats 8084, ml 8085, explain 8086, market-stream 8090. Every service exposes `/health/healthz` and `/health/readyz`, and FastAPI docs at `/docs`.

**Implemented** services (the rest — gateway, portfolio, stats, explain — are health-only stubs; `services/ml-features` is just a README):

- **market** — SPX data. `/v1/underlying/{spot,historical,candles/{period},vix}` read `underlying_daily` / `vix_daily`. `/v1/options/chain` returns `source: snapshot` (real quotes from `option_chain_snapshots`; forward from put-call parity, IV recomputed from mids — Yahoo's own IV/spot are unreliable) or `source: synthetic` (Black-Scholes from the close, VIX-anchored smile, FRED rate by date). Chain logic is pure functions in `services/chains.py`; `data_provider.py` does the DB reads. `/v1/options/expiries` follows the real listing history.
- **`market_spec.py`** (in market, copied verbatim into simulator — keep identical) is the single source for contract rules and the expiry calendar (`exchange_calendars` XNYS): `round_to_strike`, `next_expiry(on, min_dte, offset)`, `valuation_time` (close of the day, or now if intraday), `year_fraction` to the 16:00 ET close (early closes included).
- **market-stream** — in-memory latest-quote store + broadcaster. Collectors push via `POST /v1/quotes`; clients read `GET /v1/quotes[/{symbol}]` or subscribe to WebSocket `/ws/quotes`. Nothing is persisted. Feed it with `scripts/yahoo_collector.py` (index) or `scripts/mock_quote_publisher.py` (OCC-symbol option legs); there's no free real-time SPX options feed.
- **simulator** — the main business logic:
  - `/v1/strategies` (DB-defined strategy templates + legs) and `/v1/backtests` (create → `POST /{id}/run` executes `BacktestEngine` as a FastAPI background task → `/trades`, `/metrics`). Backtests enter at the close on NYSE sessions, price legs via the market service, use the nearest expiry >= 1 day out (`expiry_offset` = weeks further for calendars), size legs x100, and settle at the expiry close; trades whose expiry is past the loaded data are skipped. Metrics in `metrics_calculator.py` (Sharpe/Sortino on returns on capital, annualised by entry frequency).
  - `/v1/strategies-live` — `strategy_builder.py` builds weekly strategies (long call/put, straddle, strangle, spreads, iron condor…) from the current market-stream quote, stepping strikes in 25-point increments (`STEP`).
  - `/v1/paper/orders` — paper trades persisted in Postgres (`paper_store.py`), marked to market against market-stream quotes.
  - Downstream URLs: `MARKET_SERVICE_URL`, `MARKET_STREAM_URL` (defaults to compose hostnames `market`, `market_stream`).
- **ml** — feature engineering only (no model/predict endpoint yet). `/v1/features/{compute,weekly/{symbol}/{date},latest/{symbol},backfill}`; calculators in `app/calculators/` (price, technical, volatility) pull candles (and VIX, for VIX level/change and VIX-minus-realised-vol) from the market service and write `weekly_features`.

Service conventions: `app/main.py` wires routers; `app/config.py` is a pydantic-settings `Settings` read from env; `app/db/connection.py` holds a psycopg2 connection pool (raw SQL with `RealDictCursor`, no ORM). Services start even if the DB is down and report it via health checks. CORS is `*` everywhere.

**strategy-dashboard** mixes live and mock data: strategies/paper orders come from the simulator API, while the weekly prediction (range, closing estimate, VIX/PCR context) still comes from `data/mockDashboard.ts` because the ML predict endpoint doesn't exist.

**Schema**: `schema/sql/` numbered files — RBAC (users/roles/permissions/audit, roles Basic/Premium/Admin per `docs/security-rbac.md`), market data, strategies/backtests, paper trading, multi-expiry, `008` NIFTY->SPX conversion. `db_apply.sh` re-runs every file, so keep migrations idempotent (seeds are insert-if-missing). Option types are `C`/`P` in strategy/backtest tables but `CALL`/`PUT` in paper trading and market-stream. Two files share the `006_` prefix; order is alphabetical.

`docs/architecture.md` and `docs/strategy-engine.md` describe the *target* design (Firebase auth, Cloud SQL, SHAP explain, sentiment scoring) — much of it is not built. `infra/` (Terraform, Cloud Run) is README-only.

## Landing page work

`landing/` uses an Apple-style design with illustrative SPX data computed by Black-Scholes in `landing/data/showcase.ts` — follow `docs/landing-redesign-plan.md` (section flow, tokens, motion rules) and `docs/ui-reference.md` (options-chain and trading UI references).
