# Stats & Risk Service

Risk of the open paper positions (port 8084). Positions come from the portfolio service (`PORTFOLIO_URL`, netted by
contract), prices from market-stream (`MARKET_STREAM_URL`), the rate from `rates_daily`.

| Endpoint | What it returns |
|---|---|
| `GET /v1/risk/greeks` | Delta, gamma, vega, theta in dollars, plus P&L per 1% SPX move from delta and from gamma: totals, by expiry, per position (with the IV used, its source, the model price and the mid) |

How positions are priced (`app/services/exposure.py`, Black-Scholes-Merton in `app/services/pricing.py`): each expiry
at its chain's own moment, with spot = that expiry's put-call-parity forward discounted back and T from the chain's
`quoted_at`, exactly how the stream bridge computes the quote's IVs. Delta per contract therefore equals the quote's
delta. A leg with no IV takes the nearest strike's in the same expiry; a position whose expiry isn't on the quote is
returned under `unpriced` and left out of the totals.

Units, for the signed quantity x100: delta = $ per SPX point, gamma = change in that delta per point, vega = $ per
volatility point, theta = $ per calendar day.

```bash
pip install -e ".[test]" && pytest -q
PORT=8084 PORTFOLIO_URL=http://localhost:8083 MARKET_STREAM_URL=http://localhost:8090 uvicorn app.main:app --port 8084
```
