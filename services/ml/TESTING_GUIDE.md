# ML Features Service - Testing Guide

## Complete End-to-End Testing

This guide will walk you through testing the fully implemented ML Features Service.

---

## Prerequisites

1. **All services running:**
   ```bash
   docker compose up postgres market ml
   ```

2. **Database schema deployed:**
   ```bash
   # From project root
   cd C:\projects\quantisti\quantisti-options-trading

   type services\ml\migrations\001_create_weekly_features_table.sql | docker compose exec -T postgres psql -U quantisti -d quantisti
   ```

3. **Verify tables exist:**
   ```bash
   docker compose exec postgres psql -U quantisti -d quantisti -c "\dt weekly*"
   ```

   Expected output:
   ```
   public | weekly_features             | table | quantisti
   public | weekly_strategy_performance | table | quantisti
   ```

---

## Test 1: Health Check

```bash
curl http://localhost:8085/health/healthz
```

**Expected:**
```json
{"status":"ok"}
```

---

## Test 2: View API Documentation

Open in browser:
```
http://localhost:8085/docs
```

You should see all endpoints including:
- POST /v1/features/compute
- GET /v1/features/weekly/{symbol}/{date}
- GET /v1/features/latest/{symbol}
- POST /v1/features/backfill

---

## Test 3: Compute Features for a Single Week

### PowerShell:
```powershell
Invoke-RestMethod -Uri "http://localhost:8085/v1/features/compute" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{
    "symbol": "NIFTY",
    "week_start_date": "2024-01-01T00:00:00",
    "force_recompute": false
  }'
```

### curl:
```bash
curl -X POST http://localhost:8085/v1/features/compute \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "NIFTY",
    "week_start_date": "2024-01-01T00:00:00",
    "force_recompute": false
  }'
```

**Expected Response:**
```json
{
  "features": {
    "week_start_date": "2024-01-01T00:00:00",
    "symbol": "NIFTY",
    "price_features": {
      "weekly_change_pct": 2.35,
      "weekly_high_low_range_pct": 4.12,
      "volume_ratio": 1.15
    },
    "technical_indicators": {
      "rsi_14": 58.42,
      "macd": 45.23,
      "macd_signal": 42.10,
      "bb_width": 3.45
    },
    "volatility_features": {
      "historical_vol_10d": 12.34,
      "historical_vol_20d": 11.89,
      "atr_14": 156.78
    },
    "created_at": "2025-11-15T06:30:00.000Z"
  },
  "message": "Features computed and saved successfully"
}
```

**What this tests:**
- ✅ Market data fetching from market service
- ✅ Feature calculation (price, technical, volatility)
- ✅ Database storage
- ✅ Response formatting

---

## Test 4: Retrieve Computed Features

After computing features for a week, retrieve them:

### PowerShell:
```powershell
Invoke-RestMethod -Uri "http://localhost:8085/v1/features/weekly/NIFTY/2024-01-01T00:00:00"
```

### curl:
```bash
curl http://localhost:8085/v1/features/weekly/NIFTY/2024-01-01T00:00:00
```

**Expected:**
Same feature data as Test 3, but with message "Features retrieved successfully"

**What this tests:**
- ✅ Database retrieval
- ✅ Feature reconstruction from database

---

## Test 5: Get Latest Features

```bash
curl http://localhost:8085/v1/features/latest/NIFTY
```

**Expected:**
Returns the most recently computed features for NIFTY.

---

## Test 6: Backfill Historical Data (Background Task)

This will compute features for multiple weeks in the background.

### PowerShell:
```powershell
Invoke-RestMethod -Uri "http://localhost:8085/v1/features/backfill?symbol=NIFTY&start_date=2024-01-01T00:00:00&end_date=2024-02-01T00:00:00&interval_days=7" `
  -Method Post
```

### curl:
```bash
curl -X POST "http://localhost:8085/v1/features/backfill?symbol=NIFTY&start_date=2024-01-01T00:00:00&end_date=2024-02-01T00:00:00&interval_days=7"
```

**Expected Response:**
```json
{
  "status": "started",
  "message": "Backfill started for NIFTY from 2024-01-01 to 2024-02-01",
  "estimated_weeks": 4,
  "note": "Check logs for progress. Features will be available as they're computed."
}
```

**Monitor Progress:**
```bash
docker compose logs ml -f
```

You'll see logs like:
```
Starting backfill for NIFTY from 2024-01-01 to 2024-02-01
Computing features for NIFTY week 2024-01-01
✓ Saved features for 2024-01-01
Computing features for NIFTY week 2024-01-08
✓ Saved features for 2024-01-08
...
Backfill complete: 4 succeeded, 0 failed
```

**What this tests:**
- ✅ Background task execution
- ✅ Batch feature computation
- ✅ Multiple week processing
- ✅ Training dataset generation

---

## Test 7: Verify Database Storage

Check the database directly:

```bash
docker compose exec postgres psql -U quantisti -d quantisti
```

Then run:
```sql
-- Count features
SELECT COUNT(*) FROM weekly_features;

-- View features for NIFTY
SELECT week_start_date, symbol, weekly_change_pct, rsi_14, historical_vol_10d
FROM weekly_features
WHERE symbol = 'NIFTY'
ORDER BY week_start_date DESC
LIMIT 5;

-- Exit
\q
```

**Expected:**
You should see all the features you computed.

---

## Test 8: Force Recompute

Compute features again with force_recompute=true:

```powershell
Invoke-RestMethod -Uri "http://localhost:8085/v1/features/compute" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{
    "symbol": "NIFTY",
    "week_start_date": "2024-01-01T00:00:00",
    "force_recompute": true
  }'
```

**What this tests:**
- ✅ Feature recomputation
- ✅ Database upsert (ON CONFLICT)

---

## Test 9: Check Market Service Integration

Verify market service is providing data:

```bash
curl "http://localhost:8081/v1/nifty/historical?start_date=2024-01-01&end_date=2024-01-05"
```

**Expected:**
```json
{
  "symbol": "NIFTY",
  "data": [
    {
      "date": "2024-01-01",
      "open": 21650.50,
      "high": 21725.80,
      "low": 21580.25,
      "close": 21698.85,
      "volume": 285000000
    },
    ...
  ],
  "count": 5,
  "start_date": "2024-01-01",
  "end_date": "2024-01-05"
}
```

If this fails, the ML service won't be able to compute features.

---

## Troubleshooting

### Problem: "Failed to compute features"

**Solution:**
1. Check market service is running: `docker compose ps market`
2. Check market service has data: Test 9 above
3. Check logs: `docker compose logs ml -f`

### Problem: "No data found for date range"

**Solution:**
- Market service database may be empty
- Check if market service has historical data populated
- Try a different date range with known data

### Problem: Database connection error

**Solution:**
```bash
# Restart services
docker compose restart postgres ml

# Check database is accessible
docker compose exec postgres psql -U quantisti -d quantisti -c "SELECT 1"
```

### Problem: Features not saving

**Solution:**
```bash
# Check if tables exist
docker compose exec postgres psql -U quantisti -d quantisti -c "\dt weekly*"

# If not, run migration again
type services\ml\migrations\001_create_weekly_features_table.sql | docker compose exec -T postgres psql -U quantisti -d quantisti
```

---

## Performance Testing

### Test with Large Date Range

Generate 1 year of weekly features (52 weeks):

```bash
curl -X POST "http://localhost:8085/v1/features/backfill?symbol=NIFTY&start_date=2023-01-01T00:00:00&end_date=2024-01-01T00:00:00&interval_days=7"
```

Monitor memory and CPU usage:
```bash
docker stats ml-1
```

---

## Success Criteria

All tests passing means:
- ✅ ML service is fully functional
- ✅ Market data integration works
- ✅ Feature calculators work correctly
- ✅ Database storage/retrieval works
- ✅ Background tasks execute properly
- ✅ Ready for ML model training

---

## Next Steps After Testing

1. **Generate Training Dataset:**
   - Backfill 2-3 years of historical features
   - Use simulator service to backtest strategies for each week
   - Store best performing strategy per week in `weekly_strategy_performance`

2. **Train ML Model:**
   - Export features + labels to pandas DataFrame
   - Train classification model: Features → Best Strategy
   - Save model for prediction

3. **Build Prediction API:**
   - Add model loading in service startup
   - Create `/v1/predict/weekly-strategy` endpoint
   - Predict best strategy for upcoming week

4. **Visualization:**
   - Create dashboard to show predictions
   - Compare predicted vs actual performance
   - Display feature importance

---

## Quick Test Script

Save this as `test_ml_service.ps1`:

```powershell
# Test script for ML Features Service

Write-Host "Testing ML Features Service..." -ForegroundColor Green

# Test 1: Health
Write-Host "`n1. Testing health endpoint..." -ForegroundColor Yellow
Invoke-RestMethod -Uri "http://localhost:8085/health/healthz"

# Test 2: Compute features
Write-Host "`n2. Computing features for 2024-01-01..." -ForegroundColor Yellow
$result = Invoke-RestMethod -Uri "http://localhost:8085/v1/features/compute" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"symbol": "NIFTY", "week_start_date": "2024-01-01T00:00:00", "force_recompute": false}'

Write-Host "Features computed: $($result.message)" -ForegroundColor Green

# Test 3: Retrieve features
Write-Host "`n3. Retrieving computed features..." -ForegroundColor Yellow
$features = Invoke-RestMethod -Uri "http://localhost:8085/v1/features/weekly/NIFTY/2024-01-01T00:00:00"

Write-Host "RSI: $($features.features.technical_indicators.rsi_14)" -ForegroundColor Cyan
Write-Host "Weekly Change: $($features.features.price_features.weekly_change_pct)%" -ForegroundColor Cyan

Write-Host "`n✅ All tests passed!" -ForegroundColor Green
```

Run with:
```powershell
.\test_ml_service.ps1
```
