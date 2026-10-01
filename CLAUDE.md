# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Quantisti: a microservice options-trading simulator for **NIFTY weekly options** (INR, lot size 50, weekly expiry on Tuesday). Python FastAPI services + two Next.js apps. It's a portfolio project; sample/illustrative data on the landing page is intentional. The local folder is named `quant-finance-simulator` but the git remote is `github.com/sujaysavanth/quantisti-options-trading`.

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
# ML tables live separately and are NOT applied by db_apply.sh:
docker compose exec -T postgres psql -U quantisti -d quantisti < services/ml/migrations/001_create_weekly_features_table.sql
python scripts/populate_nifty_data.py --start-date 2015-01-01 --end-date 2024-12-31   # fills nifty_historical from yfinance
```

Single service locally (each service is its own installable package named `app`):
```bash
cd services/<svc> && pip install -e . && PORT=8082 uvicorn app.main:app --reload --port 8082
```

Tests: there is no real test suite. CI (`.github/workflows/ci.yml`) runs `pytest -q || true` per service (non-blocking) and a placeholder lint step, then `docker build` per service. The only test-like file is `services/ml/test_calculators.py`, run as a script from `services/ml`: `python test_calculators.py`.

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

- **market** — NIFTY reference data. `/v1/nifty/{spot,historical,candles/{period}}` read the `nifty_historical` table. `/v1/options/{chain,chain/strikes/{strike},expiries}` **synthesize** the option chain with Black-Scholes (`services/black_scholes.py`, `services/greeks.py`) priced off historical volatility — it is not real exchange data. `data_provider.py` is the core.
- **market-stream** — in-memory latest-quote store + broadcaster. Collectors push via `POST /v1/quotes`; clients read `GET /v1/quotes[/{symbol}]` or subscribe to WebSocket `/ws/quotes`. Nothing is persisted. Feed it with `scripts/mock_quote_publisher.py` or the collectors in `scripts/` (Alpha Vantage, NSE, Yahoo).
- **simulator** — the main business logic:
  - `/v1/strategies` (DB-defined strategy templates + legs) and `/v1/backtests` (create → `POST /{id}/run` executes `BacktestEngine` as a FastAPI background task → `/trades`, `/metrics`). Backtests price legs by calling the market service (`services/market_client.py`); metrics (Sharpe, drawdown, win rate) in `metrics_calculator.py`.
  - `/v1/strategies-live` — `strategy_builder.py` builds weekly strategies (long call/put, straddle, strangle, spreads, iron condor…) from the current market-stream quote, stepping strikes in 50-point increments.
  - `/v1/paper/orders` — paper trades persisted in Postgres (`paper_store.py`), marked to market against market-stream quotes.
  - Downstream URLs: `MARKET_SERVICE_URL`, `MARKET_STREAM_URL` (defaults to compose hostnames `market`, `market_stream`).
- **ml** — feature engineering only (no model/predict endpoint yet). `/v1/features/{compute,weekly/{symbol}/{date},latest/{symbol},backfill}`; calculators in `app/calculators/` (price, technical, volatility) pull candles from the market service and write `weekly_features`.

Service conventions: `app/main.py` wires routers; `app/config.py` is a pydantic-settings `Settings` read from env; `app/db/connection.py` holds a psycopg2 connection pool (raw SQL with `RealDictCursor`, no ORM). Services start even if the DB is down and report it via health checks. CORS is `*` everywhere.

**strategy-dashboard** mixes live and mock data: strategies/paper orders come from the simulator API, while the weekly prediction (range, closing estimate, VIX/PCR context) still comes from `data/mockDashboard.ts` because the ML predict endpoint doesn't exist.

**Schema**: `schema/sql/` numbered files — RBAC (users/roles/permissions/audit, roles Basic/Premium/Admin per `docs/security-rbac.md`), market data, strategies/backtests, paper trading, multi-expiry. Note two files share the `006_` prefix (`006_more_strategies.sql`, `006_paper_trading.sql`); order is alphabetical.

`docs/architecture.md` and `docs/strategy-engine.md` describe the *target* design (Firebase auth, Cloud SQL, SHAP explain, sentiment scoring) — much of it is not built. `infra/` (Terraform, Cloud Run) is README-only.

## Landing page work

`landing/` is being redesigned in an Apple-style direction — follow `docs/landing-redesign-plan.md` (section flow, tokens, motion rules) and `docs/ui-reference.md` (options-chain and trading UI references).
