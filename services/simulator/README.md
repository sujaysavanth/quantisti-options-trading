# Simulator Service

Executes option strategy simulations, basic paper trading, and scenario analysis routines.

- **Status:** Backtest APIs plus lightweight paper-trading endpoints backed by the live Market Stream service (trades persist in Postgres).
- **Engines:** Backtest engine, metrics calculator, and in-memory paper trade store (persisting to DB is TBD).
- **Endpoints:** `/health/healthz`, `/v1/strategies/*`, `/v1/strategies-live`, `/v1/backtests/*`, `/v1/paper/orders`.

## Paper Trading Quickstart

1. Apply the paper-trading schema (`psql $DATABASE_URL -f schema/sql/006_paper_trading.sql`).
2. Make sure the Market Stream service and collectors (Yahoo spot + NSE option chain) are running so the simulator can fetch live quotes.
3. Start the simulator (`docker compose up simulator` or `uvicorn app.main:app --reload`).
4. POST to `POST http://localhost:8082/v1/paper/orders` with a payload like:

```json
{
  "symbol": "NIFTY",
  "nickname": "Dummy Condor",
  "legs": [
    {"strike": 19500, "option_type": "PUT", "expiry": "2025-11-25", "quantity": 1, "side": "SELL"},
    {"strike": 19300, "option_type": "PUT", "expiry": "2025-11-25", "quantity": 1, "side": "BUY"}
  ]
}
```

5. Fetch `GET http://localhost:8082/v1/paper/orders` to see MTM/P&L for each leg. A Next.js page at `/paper` in the strategy dashboard app provides a basic UI for these actions, and trades can be deleted via `DELETE /v1/paper/orders/{id}`.

## Live Strategy Suggestions

- Start Market Stream + collectors.
- Call `GET http://localhost:8082/v1/strategies-live?symbol=NIFTY` to receive a set of instantiated strategies (directional, spreads, condors, straddles/strangles) built from the current chain, including legs with identifiers and basic P&L metrics. Use these to populate the UI instead of mock strategies.
