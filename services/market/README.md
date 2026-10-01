# Market Data Service

S&P 500 index (SPX) data and SPX option chains with implied volatility and Greeks.

## Features

- **Underlying history**: daily SPX OHLCV with 30-day realised volatility (`/v1/underlying/historical`, `/v1/underlying/candles/{period}`), latest close and daily change (`/v1/underlying/spot`), VIX closes (`/v1/underlying/vix`).
- **Option chains** (`/v1/options/chain`):
  - `source: snapshot` when `scripts/spx_chain_snapshot.py` has saved listed quotes for that day and expiry. The forward is inferred from put-call parity and IV/Greeks are recomputed from mid quotes, because the free feed's IVs and underlying price don't agree with its quotes.
  - `source: synthetic` otherwise: Black-Scholes-Merton from the day's close, a VIX-anchored put-skewed smile, the FRED 3-month T-bill rate on that date and a 1.3% dividend yield.
- **Expiry calendar** (`/v1/options/expiries`): SPX expiries on the NYSE calendar as they were listed (Fridays; Mon/Wed from 2016; daily from 2022), holidays and early closes included. Time to expiry runs to the 16:00 ET close, so 0DTE chains price intraday.
- Contract rules (5-pt strikes, x100 multiplier, PM settlement) live in `app/market_spec.py`; the simulator keeps an identical copy.

## Quick start

```bash
# 1. Apply the schema (from the repo root)
DATABASE_URL=postgresql://quantisti:quantisti@localhost:5432/quantisti ./scripts/db_apply.sh

# 2. Load SPX, VIX and T-bill history (free sources, no API key)
pip install yfinance psycopg2-binary pandas
python scripts/populate_us_data.py --start-date 2015-01-01

# 3. Optional: save today's listed SPX chains (run daily after the close)
python scripts/spx_chain_snapshot.py --expiries 10

# 4. Run the service
docker compose up market --build

# 5. Try it (or open http://localhost:8081/docs)
curl http://localhost:8081/v1/underlying/spot
curl "http://localhost:8081/v1/options/chain?strike_range=10"
curl "http://localhost:8081/v1/options/expiries?days=14"
```

## Tests

```bash
cd services/market
pip install -e ".[test]"
pytest -q
```
