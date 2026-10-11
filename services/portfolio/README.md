# Portfolio Service

The paper portfolio (port 8083). The simulator owns the paper trades; this service reads them over HTTP
(`SIMULATOR_URL`, `MARKET_STREAM_URL` for the SPX price) and owns only `portfolio_snapshots` (`schema/sql/013_portfolio.sql`).

| Endpoint | What it returns |
|---|---|
| `GET /v1/portfolio/positions` | Open legs netted by contract across trades (+ long / - short), average entry, mark, market value, unrealised P&L, and the open trades behind them |
| `GET /v1/portfolio/equity?kind=close\|intraday&start=&end=&positions=true` | Stored snapshots: the equity curve |
| `GET /v1/portfolio/performance?start=&end=` | Total / period return, volatility, Sharpe and Sortino (vs the 3-month T-bill), max drawdown, SPX over the same sessions with beta, trade stats overall and per strategy; `meaningful` and `notes` flag small samples |
| `GET /v1/portfolio/trades?status=closed\|open\|all` | Trade history (default closed) |
| `GET /v1/portfolio/trades.csv` | The same, one row per leg |
| `POST /v1/portfolio/snapshots/run` | Take the snapshot due now, if any |

Snapshots (`app/services/schedule.py`): every 15 minutes in session, stamped at the bucket start, and one per session
after the close, taken from 20 minutes after the close (quotes are ~15 minutes delayed) until 20:15 ET (CBOE's
overnight session). A background task checks every minute (`SNAPSHOT_CHECK_SECONDS`; `SNAPSHOTS_ENABLED=false` turns
it off). A missed close stays missing rather than being taken at the next day's prices.

Performance (`app/services/performance.py`) uses the close snapshots, the simulator's closed trades and, read straight from
Postgres, SPX closes (`underlying_daily`) and the T-bill rate (`rates_daily`). Sharpe/Sortino use the backtest
definitions, daily and annualised by sqrt(252). Volatility, Sharpe, Sortino and beta stay null below 20 daily returns;
trade stats are flagged below 10 closed trades.

```bash
pip install -e ".[test]" && pytest -q
PORT=8083 SIMULATOR_URL=http://localhost:8082 MARKET_STREAM_URL=http://localhost:8090 uvicorn app.main:app --port 8083
```
