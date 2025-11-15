# ML Features Service - Development Guide

## 🎯 What We Built

A complete feature engineering service skeleton with:
- ✅ Database connection management
- ✅ 3 feature calculator modules (Price, Technical, Volatility)
- ✅ API endpoints for feature management
- ✅ Database schema for feature storage
- ✅ Docker configuration

## 📁 Service Structure

```
services/ml/
├── app/
│   ├── main.py                    # FastAPI app with DB initialization
│   ├── config.py                  # Service configuration
│   ├── db/
│   │   ├── connection.py          # PostgreSQL connection pool
│   │   └── __init__.py
│   ├── models/
│   │   ├── features.py            # Pydantic models for features
│   │   └── __init__.py
│   ├── calculators/               # Feature computation logic
│   │   ├── price_calculator.py    # Price-based features
│   │   ├── technical_calculator.py # Technical indicators (RSI, MACD, BB)
│   │   ├── volatility_calculator.py # Volatility metrics (HV, ATR)
│   │   └── __init__.py
│   ├── services/
│   │   ├── feature_service.py     # Feature computation orchestration
│   │   ├── market_client.py       # Market data fetching (stub)
│   │   └── __init__.py
│   └── routers/
│       ├── features.py            # Feature API endpoints
│       ├── health.py              # Health checks
│       └── __init__.py
├── migrations/
│   └── 001_create_weekly_features_table.sql  # Database schema
├── Dockerfile
├── pyproject.toml                 # Dependencies
└── README.md
```

## 🚀 Next Steps to Make It Functional

### Step 1: Deploy Database Schema

Run the migration to create tables:

```bash
docker compose exec postgres psql -U quantisti -d quantisti -f /path/to/migrations/001_create_weekly_features_table.sql
```

Or copy and run manually:
```bash
docker compose cp services/ml/migrations/001_create_weekly_features_table.sql postgres:/tmp/
docker compose exec postgres psql -U quantisti -d quantisti -f /tmp/001_create_weekly_features_table.sql
```

### Step 2: Build and Start the Service

```bash
docker compose build ml
docker compose up ml
```

Check logs:
```bash
docker compose logs ml
```

You should see:
- "Database connection pool initialized"
- "UUID adapter registered for PostgreSQL"
- "Application startup complete"

### Step 3: Test Health Endpoint

```bash
curl http://localhost:8085/health/healthz
```

Expected response:
```json
{"status": "healthy"}
```

### Step 4: Integrate Market Data Service

**Current blocker**: The `market_client.py` has stub implementations.

**What you need to do**:
1. Check your market service endpoints:
   ```bash
   curl http://localhost:8081/v1/market/
   ```

2. Update `services/ml/app/services/market_client.py`:
   - Replace placeholder URLs with actual market service endpoints
   - Implement `fetch_historical_data()` based on your API
   - Implement `fetch_latest_price()` based on your API

Example:
```python
# In market_client.py, update the URL to match your actual endpoint
url = f"{self.base_url}/v1/market/historical"  # Adjust to your API
```

### Step 5: Implement Feature Storage

Update `services/ml/app/services/feature_service.py`:

**Uncomment and complete**:
- `save_features()` method - Add the actual INSERT query
- `get_features()` method - Add the actual SELECT query

The SQL structure is already defined in the migration file.

### Step 6: Test Feature Computation (End-to-End)

Once market data integration is done:

```bash
curl -X POST http://localhost:8085/v1/features/compute \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "NIFTY",
    "week_start_date": "2024-01-01T00:00:00",
    "force_recompute": false
  }'
```

### Step 7: Backfill Historical Data

Implement the backfill endpoint to generate training data:

```python
# In features.py router
@router.post("/backfill")
async def backfill_features(...):
    # Loop through each week from start_date to end_date
    # Compute features for each week
    # Save to database
```

This creates your ML training dataset.

## 🔧 What's Working Now

- ✅ Service starts successfully
- ✅ Database connection pool works
- ✅ Health endpoints respond
- ✅ Feature calculator logic is implemented
- ✅ API structure is ready

## ⚠️ What Needs Implementation

1. **Market Data Integration** (Priority 1)
   - Update `market_client.py` with real endpoints
   - Test data fetching

2. **Feature Storage** (Priority 2)
   - Complete `save_features()` in `feature_service.py`
   - Complete `get_features()` in `feature_service.py`

3. **Backfill Functionality** (Priority 3)
   - Implement backfill endpoint
   - Generate 2-3 years of historical features

4. **Testing** (Priority 4)
   - Test with real market data
   - Validate feature calculations
   - Check data quality

## 🎓 How Feature Calculators Work

Each calculator is independent and can be tested separately:

```python
from app.calculators.price_calculator import PriceFeatureCalculator
import pandas as pd

# Sample data
data = pd.DataFrame({
    'close': [100, 102, 101, 103, 105],
    'high': [102, 104, 103, 105, 107],
    'low': [99, 101, 100, 102, 104],
    'volume': [1000, 1200, 1100, 1300, 1250]
})

calc = PriceFeatureCalculator()
features = calc.calculate_all(data)
print(features)
# Output: {'weekly_change_pct': 5.0, 'weekly_high_low_range_pct': ..., ...}
```

## 📊 Data Flow for ML Training

```
1. Backfill Features (historical weeks)
   ↓
2. Run Backtests for all strategies (each week)
   ↓
3. Store best performing strategy per week
   ↓
4. Train Model: Features → Best Strategy
   ↓
5. Predict next week's best strategy
```

## 🐛 Troubleshooting

**Service won't start**:
- Check docker-compose logs: `docker compose logs ml`
- Verify database is running: `docker compose ps postgres`

**Database connection fails**:
- Check DATABASE_URL in docker-compose.yml
- Verify postgres service is healthy

**Feature computation returns None**:
- Check market data is being fetched correctly
- Add logging in calculators to debug

## 💡 Tips

1. **Start small**: Get one feature working end-to-end before adding more
2. **Test calculators independently**: They're pure functions, easy to test
3. **Use existing patterns**: Look at simulator service for reference
4. **Add logging**: Use `logger.info()` liberally for debugging

## 📝 Current Limitations (By Design)

These are intentional stubs for you to implement:

- Market data fetching (you know your market service API best)
- Feature storage queries (schema is ready, queries are placeholders)
- Backfill logic (depends on your data availability)
- Model training (future phase)

All the infrastructure is ready - you just need to connect the pieces!
