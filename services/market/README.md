# Market Data Service

**Status:** ✅ Fully Implemented with Black-Scholes Pricing

Market data service providing Nifty 50 index data and options chain with realistic pricing using the Black-Scholes-Merton model.

---

## Features

### ✅ Implemented

- **Historical Nifty Data**: OHLCV data with historical volatility
- **Real-time Spot Price**: Latest Nifty closing price
- **Option Chain Generation**: Complete call and put option chains
- **Black-Scholes Pricing**: European options pricing for all strikes
- **Greeks Calculation**: Delta, Gamma, Theta, Vega, Rho
- **Expiry Management**: Auto-calculates monthly expiries (last Thursday)
- **Database Integration**: PostgreSQL with connection pooling
- **API Documentation**: Interactive Swagger UI at `/docs`

---

## Quick Start

```bash
# 1. Apply database schema
psql $DATABASE_URL -f schema/sql/004_market_data.sql

# 2. Populate Nifty historical data
pip install yfinance psycopg2-binary pandas
python scripts/populate_nifty_data.py

# 3. Run the service
docker compose up market --build

# 4. Test it
curl http://localhost:8081/v1/nifty/spot
curl "http://localhost:8081/v1/options/chain?strike_range=10"

# 5. View API docs
open http://localhost:8081/docs
```

See full documentation in this file below.
