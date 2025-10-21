#!/bin/bash
# Quick test script for Market Data API

set -e

echo "🚀 Testing Market Data API"
echo "=========================="
echo ""

BASE_URL="http://localhost:8081"

# Test 1: Health check
echo "1️⃣  Testing health endpoint..."
curl -s "$BASE_URL/health/healthz" | jq
echo ""

# Test 2: Root endpoint
echo "2️⃣  Testing root endpoint..."
curl -s "$BASE_URL/" | jq
echo ""

# Test 3: Get spot price
echo "3️⃣  Testing Nifty spot price..."
curl -s "$BASE_URL/v1/nifty/spot" | jq
echo ""

# Test 4: Get historical data (last 30 days)
echo "4️⃣  Testing historical candles (1 month)..."
curl -s "$BASE_URL/v1/nifty/candles/1m" | jq '.symbol, .count, .start_date, .end_date, .data[0]'
echo ""

# Test 5: Get option chain
echo "5️⃣  Testing option chain (5 strikes)..."
curl -s "$BASE_URL/v1/options/chain?strike_range=5" | jq '{symbol, spot_price, date, expiry_date, total_call_oi, total_put_oi, pcr, option_count: (.options | length)}'
echo ""

# Test 6: Get full option chain with details
echo "6️⃣  Testing option chain with full details (first 2 options)..."
curl -s "$BASE_URL/v1/options/chain?strike_range=3" | jq '.options[0:2]'
echo ""

# Test 7: Get expiries
echo "7️⃣  Testing available expiries..."
curl -s "$BASE_URL/v1/options/expiries" | jq
echo ""

echo "✅ All tests completed!"
echo ""
echo "📖 View interactive API docs at: $BASE_URL/docs"
