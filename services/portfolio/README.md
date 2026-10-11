# Portfolio Service

The paper portfolio (port 8083). The simulator owns the paper trades; this service reads them over HTTP
(`SIMULATOR_URL`, `MARKET_STREAM_URL` for the SPX price) and owns only `portfolio_snapshots` (`schema/sql/013_portfolio.sql`).

| Endpoint | What it returns |
|---|---|
| `GET /v1/portfolio/positions` | Open legs netted by contract across trades (+ long / - short), average entry, mark, market value, unrealised P&L, and the open trades behind them |
| `GET /v1/portfolio/equity?kind=close\|intraday&start=&end=&positions=true` | Stored snapshots: the equity curve |
| `GET /v1/portfolio/trades?status=closed\|open\|all` | Trade history (default closed) |
| `GET /v1/portfolio/trades.csv` | The same, one row per leg |
| `POST /v1/portfolio/snapshots/run` | Take the snapshot due now, if any |

Snapshots (`app/services/schedule.py`): every 15 minutes in session, stamped at the bucket start, and one per session
after the close, taken from 20 minutes after the close (quotes are ~15 minutes delayed) until 20:15 ET (CBOE's
overnight session). A background task checks every minute (`SNAPSHOT_CHECK_SECONDS`; `SNAPSHOTS_ENABLED=false` turns
it off). A missed close stays missing rather than being taken at the next day's prices.

```bash
pip install -e ".[test]" && pytest -q
PORT=8083 SIMULATOR_URL=http://localhost:8082 MARKET_STREAM_URL=http://localhost:8090 uvicorn app.main:app --port 8083
```
