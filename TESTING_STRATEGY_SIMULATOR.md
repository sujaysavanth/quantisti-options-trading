# Strategy Simulator - Testing Guide

Complete guide to test the Strategy Simulator service for backtesting option trading strategies.

## Prerequisites

✅ **Already Running:**
- PostgreSQL (port 5432) - `quantisti-postgres` container
- Market Data Service (port 8081) - with Nifty historical data (2015-2025)

✅ **To Start:**
- Strategy Simulator Service (port 8082)

---

## Step 1: Apply Database Schema

The simulator needs its own database tables for strategies, backtests, and metrics.

```powershell
# Apply the Strategy Simulator schema
Get-Content schema\sql\005_strategy_simulator.sql | docker exec -i quantisti-postgres psql -U quantisti -d quantisti
```

**Expected output:**
```
CREATE TABLE
CREATE TABLE
CREATE TABLE
...
INSERT 0 8  (8 pre-defined strategies inserted)
```

**Verify tables were created:**
```powershell
docker exec -it quantisti-postgres psql -U quantisti -d quantisti -c "\dt"
```

**You should see:**
- `strategies`
- `strategy_legs`
- `backtests`
- `backtest_trades`
- `backtest_trade_legs`
- `backtest_metrics`
- `nifty_historical` (from Market Data)
- `nifty_option_chain` (from Market Data)

---

## Step 2: Start the Strategy Simulator Service

```powershell
docker compose up simulator --build
```

**Expected output:**
```
✅ INFO: Started server process [7]
✅ INFO: Starting Strategy Simulator v0.1.0
✅ INFO: Environment: development
✅ INFO: Database connection pool initialized (min=2, max=10)
✅ INFO: Uvicorn running on http://0.0.0.0:8082
```

---

## Step 3: Test the API Endpoints

### **Test 1: Service Health Check**

```powershell
curl http://localhost:8082/health/healthz
```

**Expected:**
```json
{"status": "ok"}
```

---

### **Test 2: List All Pre-defined Strategies**

```powershell
curl http://localhost:8082/v1/strategies
```

**Expected:** List of 8 pre-defined strategies:
```json
{
  "strategies": [
    {
      "id": "...",
      "name": "Long Straddle",
      "strategy_type": "LONG_STRADDLE",
      "description": "Buy ATM call and put with same strike and expiry. Profit from large moves in either direction.",
      "legs": [
        {
          "action": "BUY",
          "option_type": "CE",
          "strike_offset": 0,
          "quantity": 1,
          "leg_order": 1
        },
        {
          "action": "BUY",
          "option_type": "PE",
          "strike_offset": 0,
          "quantity": 1,
          "leg_order": 2
        }
      ]
    },
    ...
  ],
  "count": 8
}
```

**Available Strategies:**
1. **Long Straddle** - Buy ATM call + put (volatility play)
2. **Short Straddle** - Sell ATM call + put (low volatility bet)
3. **Long Strangle** - Buy OTM call + put (cheaper volatility play)
4. **Short Strangle** - Sell OTM call + put (range-bound profit)
5. **Bull Call Spread** - Buy ATM call, sell OTM call (limited profit/loss)
6. **Bear Put Spread** - Buy ATM put, sell OTM put (bearish bet)
7. **Iron Condor** - Sell OTM strangles, buy further OTM protection
8. **Iron Butterfly** - Sell ATM straddle, buy OTM strangle protection

---

### **Test 3: Get Specific Strategy**

```powershell
# First, get strategy ID from the list above, then:
$strategyId = "YOUR_STRATEGY_ID_HERE"
curl "http://localhost:8082/v1/strategies/$strategyId"
```

---

### **Test 4: Create a Backtest**

Let's backtest a **Long Straddle** for January 2024:

```powershell
# First, get the Long Straddle strategy ID
$response = Invoke-RestMethod -Uri "http://localhost:8082/v1/strategies"
$longStraddleId = ($response.strategies | Where-Object {$_.name -eq "Long Straddle"}).id

# Create backtest
$backtest = @{
    strategy_id = $longStraddleId
    name = "Long Straddle - Jan 2024"
    start_date = "2024-01-01"
    end_date = "2024-01-31"
    initial_capital = 100000
    entry_logic = "ON_DATE"
    exit_logic = "ON_EXPIRY"
    stop_loss_pct = $null
    target_pct = $null
    max_holding_days = $null
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8082/v1/backtests" -Method POST -Body $backtest -ContentType "application/json"
```

**Expected response:**
```json
{
  "id": "...",
  "strategy_id": "...",
  "name": "Long Straddle - Jan 2024",
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "initial_capital": 100000,
  "entry_logic": "ON_DATE",
  "exit_logic": "ON_EXPIRY",
  "status": "PENDING",
  "created_at": "..."
}
```

**Save the backtest ID** for next steps!

---

### **Test 5: Run the Backtest**

```powershell
$backtestId = "YOUR_BACKTEST_ID_FROM_STEP_4"

Invoke-RestMethod -Uri "http://localhost:8082/v1/backtests/$backtestId/run" -Method POST
```

**Expected response:**
```json
{
  "id": "...",
  "status": "PENDING",
  ...
}
```

**The backtest runs in the background.** Watch the docker logs:

```
INFO: Starting backtest {id}
INFO: Running backtest {id} with 1 trades
INFO: Calculating metrics for backtest {id}
INFO: Backtest {id} completed successfully
```

This usually takes **5-30 seconds** depending on the date range.

---

### **Test 6: Check Backtest Status**

```powershell
curl "http://localhost:8082/v1/backtests/$backtestId"
```

**Expected (when completed):**
```json
{
  "id": "...",
  "status": "COMPLETED",
  "started_at": "...",
  "completed_at": "..."
}
```

---

### **Test 7: View Backtest Trades**

```powershell
curl "http://localhost:8082/v1/backtests/$backtestId/trades"
```

**Expected response:**
```json
{
  "backtest": {...},
  "trades": [
    {
      "id": "...",
      "trade_number": 1,
      "entry_date": "2024-01-01",
      "exit_date": "2024-01-25",
      "expiry_date": "2024-01-25",
      "entry_spot_price": 21238.1,
      "exit_spot_price": 21507.6,
      "entry_premium": -263.17,  // Negative = debit (we paid)
      "exit_premium": 269.46,     // Positive = credit (we received)
      "pnl": 6.29,                // ₹6.29 profit per lot
      "pnl_pct": 2.39,            // 2.39% return
      "status": "CLOSED",
      "exit_reason": "EXPIRY",
      "holding_days": 24,
      "legs": [
        {
          "action": "BUY",
          "option_type": "CE",
          "strike": 21250.0,
          "entry_price": 140.32,
          "exit_price": 257.6,
          "pnl": 117.28  // Profit on call leg
        },
        {
          "action": "BUY",
          "option_type": "PE",
          "strike": 21250.0,
          "entry_price": 122.85,
          "exit_price": 11.86,
          "pnl": -110.99  // Loss on put leg
        }
      ]
    }
  ],
  "trade_count": 1
}
```

---

### **Test 8: View Performance Metrics** 🎯

```powershell
curl "http://localhost:8082/v1/backtests/$backtestId/metrics"
```

**Expected response:**
```json
{
  "id": "...",
  "metrics": {
    "total_trades": 1,
    "winning_trades": 1,
    "losing_trades": 0,
    "win_rate": 100.0,
    "total_pnl": 314.50,
    "avg_pnl_per_trade": 314.50,
    "max_profit": 314.50,
    "max_loss": 0.0,
    "max_drawdown": 0.0,
    "max_drawdown_pct": 0.0,
    "sharpe_ratio": null,  // Not enough trades
    "sortino_ratio": null,
    "profit_factor": null,
    "avg_holding_days": 24.0,
    "final_capital": 100314.50,
    "total_return_pct": 0.3145  // 0.31% return
  }
}
```

**Key Metrics Explained:**
- **Win Rate**: % of profitable trades
- **Total P&L**: Total profit/loss in INR
- **Max Drawdown**: Largest peak-to-trough decline
- **Sharpe Ratio**: Risk-adjusted returns (higher is better)
- **Profit Factor**: Gross profit / Gross loss
- **Total Return %**: Overall return on initial capital

---

## Step 4: Run More Complex Backtests

### **Example: Weekly Short Straddle for 6 Months**

```powershell
# Get Short Straddle strategy ID
$response = Invoke-RestMethod -Uri "http://localhost:8082/v1/strategies"
$shortStraddleId = ($response.strategies | Where-Object {$_.name -eq "Short Straddle"}).id

# Create backtest with weekly entries
$backtest = @{
    strategy_id = $shortStraddleId
    name = "Short Straddle - Weekly for 6M"
    start_date = "2024-01-01"
    end_date = "2024-06-30"
    initial_capital = 500000
    entry_logic = "WEEKLY"  // Enter every Monday
    exit_logic = "ON_EXPIRY"
    stop_loss_pct = $null
    target_pct = $null
    max_holding_days = $null
} | ConvertTo-Json

$backtest = Invoke-RestMethod -Uri "http://localhost:8082/v1/backtests" -Method POST -Body $backtest -ContentType "application/json"
$backtestId = $backtest.id

# Run it
Invoke-RestMethod -Uri "http://localhost:8082/v1/backtests/$backtestId/run" -Method POST

# Wait 30-60 seconds for completion
Start-Sleep -Seconds 60

# View metrics
curl "http://localhost:8082/v1/backtests/$backtestId/metrics"
```

This will generate **~26 trades** (one per week) and calculate comprehensive metrics including Sharpe ratio.

---

### **Example: Iron Condor with Monthly Entries**

```powershell
# Get Iron Condor strategy ID
$response = Invoke-RestMethod -Uri "http://localhost:8082/v1/strategies"
$ironCondorId = ($response.strategies | Where-Object {$_.name -eq "Iron Condor"}).id

# Create backtest
$backtest = @{
    strategy_id = $ironCondorId
    name = "Iron Condor - Monthly 2024"
    start_date = "2024-01-01"
    end_date = "2024-12-31"
    initial_capital = 1000000
    entry_logic = "MONTHLY"
    exit_logic = "ON_EXPIRY"
} | ConvertTo-Json

$backtest = Invoke-RestMethod -Uri "http://localhost:8082/v1/backtests" -Method POST -Body $backtest -ContentType "application/json"
Invoke-RestMethod -Uri "http://localhost:8082/v1/backtests/$($backtest.id)/run" -Method POST
```

---

## Step 5: View All Backtests

```powershell
# List all backtests
curl http://localhost:8082/v1/backtests

# Filter by strategy
curl "http://localhost:8082/v1/backtests?strategy_id=$strategyId"

# Filter by status
curl "http://localhost:8082/v1/backtests?status=COMPLETED"
```

---

## API Documentation

### **Swagger UI** (Interactive API docs)
http://localhost:8082/docs

### **ReDoc** (Alternative docs)
http://localhost:8082/redoc

---

## Testing Checklist

- [ ] Database schema applied successfully
- [ ] Simulator service started on port 8082
- [ ] Health check returns {"status": "ok"}
- [ ] Can list 8 pre-defined strategies
- [ ] Can create a backtest
- [ ] Backtest runs and completes successfully
- [ ] Can view trades with entry/exit prices
- [ ] Can view performance metrics
- [ ] Metrics include P&L, win rate, max drawdown
- [ ] Can run multiple strategies (Straddle, Strangle, Spreads)
- [ ] Weekly and Monthly entry logic works
- [ ] Results are realistic (based on real Nifty data)

---

## Expected Results

For a **Long Straddle** on **volatile days**, you should see:
- ✅ Positive P&L if market moved significantly
- ✅ Both legs have prices based on Black-Scholes
- ✅ Greeks calculated for each option
- ✅ Realistic premium amounts

For a **Short Straddle** on **range-bound days**:
- ✅ Positive P&L if market stayed flat
- ✅ Maximum profit = premium collected
- ✅ Risk of large losses on big moves

---

## Troubleshooting

### **Error: "Strategy not found"**
- Make sure you applied the database schema (Step 1)
- Check that 8 strategies were inserted

### **Error: "No historical data found"**
- Ensure Market Data service is running on port 8081
- Verify nifty_historical table has data:
  ```powershell
  docker exec -it quantisti-postgres psql -U quantisti -d quantisti -c "SELECT COUNT(*) FROM nifty_historical;"
  ```

### **Backtest stuck in RUNNING status**
- Check docker logs for errors:
  ```powershell
  docker compose logs simulator
  ```
- Common issues:
  - Market Data service not reachable
  - No data for the date range
  - Database connection issues

### **Error: "relation does not exist"**
- You forgot to apply the schema! Go back to Step 1

---

## What's Next?

Now that Strategy Simulator is working, you can:

1. **Build UI** - Create a frontend to visualize backtest results
2. **Add More Strategies** - Create custom strategies via API
3. **Optimize Parameters** - Test different strike offsets, stop losses
4. **Compare Strategies** - Run multiple backtests and compare metrics
5. **Export Results** - Add CSV/Excel export functionality
6. **Real-time Paper Trading** - Use the same strategies for live simulation

---

## Service Summary

**Port:** 8082
**Database:** PostgreSQL (quantisti database)
**Dependencies:** Market Data Service (port 8081)
**Strategies:** 8 pre-built + unlimited custom
**Metrics:** 15+ performance indicators
**Data Range:** 2015-2025 (real Nifty data)

🎉 **Strategy Simulator is fully operational!**
