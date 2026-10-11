# Stats & Risk Service

Risk of the open paper positions (port 8084). Positions come from the portfolio service (`PORTFOLIO_URL`, netted by
contract), prices from market-stream (`MARKET_STREAM_URL`), the rate from `rates_daily`.

| Endpoint | What it returns |
|---|---|
| `GET /v1/risk/stress?falls=10&rises=5` | Every open trade revalued under SPX -10%..+10% x IV -5..+10 pts x now / +1 day, and replays of the largest SPX daily falls and rises in `underlying_daily` (that day's VIX change as the IV shift, one day passing): P&L, % of account, account value after, capital held after, available after, `short_of_capital` (a margin call), worst / best scenario |
| `GET /v1/risk/var` | 1-day VaR and expected shortfall at 95% / 99% by three methods: historical, filtered historical, delta-gamma-vega |
| `GET /v1/risk/var/history?start=&end=` | VaR stored after each close (`risk_var`, schema 014) with the realised next-day P&L, breaches, Kupiec and Christoffersen tests per method |
| `POST /v1/risk/var/run` | Store this session's VaR if it is due |
| `GET /v1/risk/greeks` | Delta, gamma, vega, theta in dollars, plus P&L per 1% SPX move from delta and from gamma: totals, by expiry, per position (with the IV used, its source, the model price and the mid) |

How positions are priced (`app/services/exposure.py`, Black-Scholes-Merton in `app/services/pricing.py`): each expiry
at its chain's own moment, with spot = that expiry's put-call-parity forward discounted back and T from the chain's
`quoted_at`, exactly how the stream bridge computes the quote's IVs. Delta per contract therefore equals the quote's
delta. A leg with no IV takes the nearest strike's in the same expiry; a position whose expiry isn't on the quote is
returned under `unpriced` and left out of the totals.

Stress (`app/services/stress.py`) starts each leg from those same inputs and reprices it with Black-Scholes after the
shock; P&L is shocked minus current model value, so the unshocked scenario is exactly 0. An expiry that passes within
the horizon settles at intrinsic. Capital held after each shock comes from the simulator's
`POST /v1/paper/capital-held` (`SIMULATOR_URL`), so the account's margin rules live only there: defined risk keeps its
max loss, uncovered shorts' CBOE margin follows the shocked spot and marks. VIX is 30-day vol and short-dated IV
usually jumps more on the same day, so the historical replays understate the vol shock for weekly options.

VaR (`app/services/var.py`, run and stored by `var_run.py`), one day passing in every scenario, each SPX return
paired with that day's VIX change as the IV shift:
- **historical**: every SPX day in `underlying_daily` (since 2010), full revaluation. Slow to react to a new regime.
- **filtered historical**: the same days rescaled from their own EWMA volatility (lambda 0.94) to today's, which is
  the ml service's GARCH forecast for the next session (`ML_URL`, `/v1/predict/expiries`), or the latest EWMA when
  ml is down (`sigma_source` says which). Hull & White's volatility-updated historical simulation.
- **delta_gamma_vega**: the book's Greeks over 20,000 joint-normal (return, VIX change) draws fitted to the last 504
  sessions. Thin-tailed; shown as the textbook comparison.

A background task stores every method and confidence once per session, 20 minutes after the close until 20:15 ET.
The backtest compares each stored VaR with the change to the next session's portfolio close snapshot, which also
includes trades opened or closed that day. With 1% expected breaches, ~250 sessions are needed before the tests say
much.

Units, for the signed quantity x100: delta = $ per SPX point, gamma = change in that delta per point, vega = $ per
volatility point, theta = $ per calendar day.

```bash
pip install -e ".[test]" && pytest -q
PORT=8084 PORTFOLIO_URL=http://localhost:8083 MARKET_STREAM_URL=http://localhost:8090 uvicorn app.main:app --port 8084
```
