# Testing Guide - Market Data API

Complete guide to test the Quantisti Market Data API with Nifty options pricing.

---

## Prerequisites

- Docker & Docker Compose installed
- Python 3.11+ installed
- `curl` and `jq` for testing (optional but recommended)

---

## Step-by-Step Testing

### Step 1: Start PostgreSQL Database

```bash
# Navigate to project root
cd /path/to/quantisti-options-trading

# Start PostgreSQL container
docker compose -f docker-compose.db.yml up -d

# Verify it's running
docker ps | grep postgres
```

**Expected output:** Container `quantisti-postgres` is running on port 5432

---

### Step 2: Apply Database Schemas

```bash
# Set database connection
export DATABASE_URL=postgresql://quantisti:quantisti@localhost:5432/quantisti

# Apply RBAC schema (if not already done)
psql $DATABASE_URL -f schema/sql/001_create_tables.sql
psql $DATABASE_URL -f schema/sql/002_seed_rbac.sql

# Apply Market Data schema
psql $DATABASE_URL -f schema/sql/004_market_data.sql
```

**Expected output:** `CREATE TABLE`, `CREATE INDEX` messages

**Verify:**
```bash
psql $DATABASE_URL -c "\dt"
```
You should see: `nifty_historical`, `nifty_option_chain` tables

---

### Step 3: Populate Historical Nifty Data

```bash
# Install Python dependencies
pip install yfinance psycopg2-binary pandas numpy

# Download and populate data (2015-2024, ~10 years)
python scripts/populate_nifty_data.py --start-date 2015-01-01
```

**Expected output:**
```
Downloading Nifty data from 2015-01-01 to 2024-12-31...
[*********************100%%**********************]  1 of 1 completed
Downloaded 2451 rows of data
Calculating historical volatility...
✅ Successfully inserted/updated 2451 rows

📊 Database Summary:
   Total rows: 2451
   Date range: 2015-01-01 to 2024-12-31
   Avg close: ₹15,234.67
   Avg volume: 234,567,890
```

**Verify data exists:**
```bash
psql $DATABASE_URL -c "SELECT COUNT(*), MIN(date), MAX(date) FROM nifty_historical;"
```

Expected: ~2,450 rows, date range 2015-2024

---

### Step 4: Start Market Data Service

**Option A: Using Docker (Recommended)**

```bash
# Build and start the Market service
docker compose up market --build

# Or run in background
docker compose up -d market --build
```

**Option B: Local Development**

```bash
# Navigate to service directory
cd services/market

# Install dependencies
pip install -e .

# Start the service
uvicorn app.main:app --reload --port 8081
```

**Expected output:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Starting Market Service v0.1.0
INFO:     Environment: development
INFO:     Database connection pool initialized
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8081
```

**Verify service is running:**
```bash
curl http://localhost:8081/health/healthz
```

Expected: `{"status":"ok"}`

---

### Step 5: Test API Endpoints

#### Quick Test - Run Test Script

```bash
# Run automated test script
bash scripts/test_market_api.sh
```

This will test all endpoints automatically!

---

#### Manual Testing

**1. Health Check**
```bash
curl http://localhost:8081/health/healthz
```
Response:
```json
{"status": "ok"}
```

---

**2. Service Info**
```bash
curl http://localhost:8081/ | jq
```
Response:
```json
{
  "service": "Market Service",
  "version": "0.1.0",
  "status": "running",
  "endpoints": {
    "docs": "/docs",
    "health": "/health/healthz",
    "nifty_spot": "/v1/nifty/spot",
    "nifty_historical": "/v1/nifty/historical",
    "option_chain": "/v1/options/chain"
  }
}
```

---

**3. Get Nifty Spot Price**
```bash
curl http://localhost:8081/v1/nifty/spot | jq
```
Response:
```json
{
  "symbol": "NIFTY",
  "price": 21698.85,
  "timestamp": "2024-12-31T00:00:00",
  "change": null,
  "change_percent": null,
  "volume": 285000000
}
```

---

**4. Get Historical Data (Specific Date Range)**
```bash
curl "http://localhost:8081/v1/nifty/historical?start_date=2024-01-01&end_date=2024-01-31" | jq
```
Response:
```json
{
  "symbol": "NIFTY",
  "count": 21,
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "data": [
    {
      "date": "2024-01-01",
      "open": 21650.50,
      "high": 21725.80,
      "low": 21580.25,
      "close": 21698.85,
      "volume": 285000000,
      "historical_volatility": 0.1245
    }
  ]
}
```

---

**5. Get Candles for Predefined Periods**
```bash
# Last 1 month
curl http://localhost:8081/v1/nifty/candles/1m | jq '.symbol, .count'

# Last 1 year
curl http://localhost:8081/v1/nifty/candles/1y | jq '.symbol, .count'

# Available periods: 1d, 1w, 1m, 3m, 6m, 1y, 5y
```

---

**6. Get Option Chain (Most Important!)**
```bash
# Get option chain with 10 strikes above/below ATM
curl "http://localhost:8081/v1/options/chain?strike_range=10" | jq
```

Response:
```json
{
  "symbol": "NIFTY",
  "spot_price": 21725.50,
  "date": "2024-12-31",
  "expiry_date": "2025-01-30",
  "total_call_oi": 15000000,
  "total_put_oi": 18000000,
  "pcr": 1.20,
  "options": [
    {
      "strike": 21700.0,
      "option_type": "CE",
      "expiry_date": "2025-01-30",
      "price": 156.25,
      "bid": 155.50,
      "ask": 157.00,
      "greeks": {
        "delta": 0.52,
        "gamma": 0.00012,
        "theta": -15.35,
        "vega": 8.74,
        "rho": 5.23
      },
      "implied_volatility": 0.1245,
      "open_interest": 145000,
      "volume": 52000,
      "intrinsic_value": 25.50,
      "time_value": 130.75,
      "in_the_money": true
    },
    {
      "strike": 21700.0,
      "option_type": "PE",
      "expiry_date": "2025-01-30",
      "price": 130.75,
      "greeks": { ... },
      "in_the_money": false
    }
    // ... more options
  ]
}
```

---

**7. Get Option Chain for Historical Date**
```bash
# Get option chain for a specific past date
curl "http://localhost:8081/v1/options/chain?date=2024-06-15&strike_range=5" | jq '.spot_price, .date, .expiry_date'
```

---

**8. Get Specific Strike**
```bash
curl "http://localhost:8081/v1/options/chain/strikes/21700" | jq
```

---

**9. Get Available Expiries**
```bash
curl http://localhost:8081/v1/options/expiries | jq
```
Response:
```json
{
  "current_date": "2024-12-31",
  "expiries": [
    {
      "expiry_date": "2025-01-30",
      "days_to_expiry": 30,
      "type": "monthly"
    },
    {
      "expiry_date": "2025-02-27",
      "days_to_expiry": 58,
      "type": "monthly"
    },
    {
      "expiry_date": "2025-03-27",
      "days_to_expiry": 86,
      "type": "monthly"
    }
  ]
}
```

---

### Step 6: Interactive API Documentation

Open your browser and visit:

**Swagger UI:** http://localhost:8081/docs

**ReDoc:** http://localhost:8081/redoc

Here you can:
- See all available endpoints
- Try out API calls interactively
- See request/response schemas
- View detailed documentation

---

## Testing Scenarios

### Scenario 1: Backtest an Iron Condor Strategy

```bash
# 1. Get historical spot price for Jan 15, 2024
curl "http://localhost:8081/v1/nifty/historical?start_date=2024-01-15&end_date=2024-01-15" | jq '.data[0].close'

# 2. Get option chain for that date
curl "http://localhost:8081/v1/options/chain?date=2024-01-15&strike_range=20" | jq > iron_condor.json

# 3. Analyze the Greeks and prices in the JSON file
cat iron_condor.json | jq '.options[] | select(.option_type == "CE") | {strike, price, delta}'
```

### Scenario 2: Track Volatility Over Time

```bash
# Get 1 year of data and extract volatility
curl "http://localhost:8081/v1/nifty/candles/1y" | jq '.data[] | {date, close, historical_volatility}' > volatility.json

# You can now plot this data!
```

### Scenario 3: Find ATM Options

```bash
# Get current spot
SPOT=$(curl -s http://localhost:8081/v1/nifty/spot | jq -r '.price')

# Get option chain and filter for ATM (strike closest to spot)
curl -s "http://localhost:8081/v1/options/chain?strike_range=3" | \
  jq --arg spot "$SPOT" '.options[] | select(.strike >= ($spot | tonumber - 50) and .strike <= ($spot | tonumber + 50))'
```

---

## Troubleshooting

### Issue: "No historical data found"

**Solution:**
```bash
# Re-run data population
python scripts/populate_nifty_data.py --start-date 2015-01-01

# Verify data
psql $DATABASE_URL -c "SELECT COUNT(*) FROM nifty_historical;"
```

### Issue: Database connection error

**Solution:**
```bash
# Check PostgreSQL is running
docker ps | grep postgres

# Restart if needed
docker compose -f docker-compose.db.yml restart

# Test connection
psql $DATABASE_URL -c "SELECT 1"
```

### Issue: Service won't start

**Solution:**
```bash
# Check logs
docker compose logs market

# Or if running locally
# Check for port conflicts
lsof -i :8081
```

### Issue: Import errors (scipy, psycopg2)

**Solution:**
```bash
cd services/market
pip install -e .

# Or install individually
pip install scipy psycopg2-binary numpy fastapi uvicorn pydantic
```

---

## Performance Testing

### Load Test with Apache Bench

```bash
# Test spot price endpoint (1000 requests, 10 concurrent)
ab -n 1000 -c 10 http://localhost:8081/v1/nifty/spot

# Test option chain generation (100 requests)
ab -n 100 -c 5 "http://localhost:8081/v1/options/chain?strike_range=10"
```

### Check Response Times

```bash
# Time a single request
time curl -s http://localhost:8081/v1/options/chain?strike_range=20 > /dev/null

# Expected: < 1 second for option chain generation
```

---

## Next Steps

Once you've verified the API works:

1. ✅ Test with different date ranges
2. ✅ Verify Black-Scholes pricing makes sense (ITM calls > OTM calls)
3. ✅ Check Greeks are correct (Delta between -1 and 1, etc.)
4. ✅ Use this data to train your ML models
5. ✅ Build the Trading Simulator on top of this API

---

## Quick Reference

| Endpoint | Purpose | Example |
|----------|---------|---------|
| `/health/healthz` | Health check | `curl localhost:8081/health/healthz` |
| `/v1/nifty/spot` | Current price | `curl localhost:8081/v1/nifty/spot` |
| `/v1/nifty/historical` | OHLCV data | `curl "localhost:8081/v1/nifty/historical?start_date=2024-01-01&end_date=2024-01-31"` |
| `/v1/nifty/candles/{period}` | Quick historical | `curl localhost:8081/v1/nifty/candles/1m` |
| `/v1/options/chain` | Option chain | `curl "localhost:8081/v1/options/chain?strike_range=10"` |
| `/v1/options/expiries` | Expiry dates | `curl localhost:8081/v1/options/expiries` |
| `/docs` | API docs | Browser: `http://localhost:8081/docs` |

---

**Happy Testing! 🚀**

For issues or questions, check the logs:
```bash
docker compose logs -f market
```
