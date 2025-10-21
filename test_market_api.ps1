# Market Data API Test Script for Windows PowerShell
# Run this script to test all Market Data API endpoints

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Market Data API Testing Script" -ForegroundColor Cyan
Write-Host "============================================================`n" -ForegroundColor Cyan

$baseUrl = "http://localhost:8081"

# Test 1: Health Check
Write-Host "Test 1: Health Check" -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$baseUrl/health" -Method Get
    Write-Host "✅ Health check passed" -ForegroundColor Green
    Write-Host ($response | ConvertTo-Json -Depth 3)
    Write-Host ""
} catch {
    Write-Host "❌ Health check failed: $_" -ForegroundColor Red
    Write-Host ""
}

# Test 2: Get Latest Spot Price
Write-Host "Test 2: Get Latest Nifty Spot Price" -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$baseUrl/v1/nifty/spot" -Method Get
    Write-Host "✅ Spot price retrieved" -ForegroundColor Green
    Write-Host ($response | ConvertTo-Json -Depth 3)
    Write-Host ""
} catch {
    Write-Host "❌ Failed to get spot price: $_" -ForegroundColor Red
    Write-Host ""
}

# Test 3: Get Historical Data (Last 30 days)
Write-Host "Test 3: Get Historical Data (Last 30 days)" -ForegroundColor Yellow
try {
    $endDate = (Get-Date).ToString("yyyy-MM-dd")
    $startDate = (Get-Date).AddDays(-30).ToString("yyyy-MM-dd")
    $response = Invoke-RestMethod -Uri "$baseUrl/v1/nifty/historical?start_date=$startDate&end_date=$endDate" -Method Get
    Write-Host "✅ Historical data retrieved ($($response.data.Count) records)" -ForegroundColor Green
    Write-Host "First record:" ($response.data[0] | ConvertTo-Json -Depth 3)
    Write-Host ""
} catch {
    Write-Host "❌ Failed to get historical data: $_" -ForegroundColor Red
    Write-Host ""
}

# Test 4: Get 1 Month Candles
Write-Host "Test 4: Get 1 Month Candles" -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$baseUrl/v1/nifty/candles/1m" -Method Get
    Write-Host "✅ 1 month candles retrieved ($($response.data.Count) candles)" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "❌ Failed to get candles: $_" -ForegroundColor Red
    Write-Host ""
}

# Test 5: Get Option Chain
Write-Host "Test 5: Get Option Chain" -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$baseUrl/v1/options/chain" -Method Get
    Write-Host "✅ Option chain retrieved" -ForegroundColor Green
    Write-Host "Symbol: $($response.symbol)"
    Write-Host "Spot Price: ₹$($response.spot_price)"
    Write-Host "Date: $($response.date)"
    Write-Host "Expiry: $($response.expiry_date)"
    Write-Host "Options count: $($response.options.Count)"
    Write-Host "First option:" ($response.options[0] | ConvertTo-Json -Depth 3)
    Write-Host ""
} catch {
    Write-Host "❌ Failed to get option chain: $_" -ForegroundColor Red
    Write-Host ""
}

# Test 6: Get Specific Strike
Write-Host "Test 6: Get Specific Strike (ATM)" -ForegroundColor Yellow
try {
    # First get the spot price to calculate ATM strike
    $spotResponse = Invoke-RestMethod -Uri "$baseUrl/v1/nifty/spot" -Method Get
    $spotPrice = $spotResponse.close
    $atmStrike = [Math]::Round($spotPrice / 50) * 50  # Round to nearest 50

    $response = Invoke-RestMethod -Uri "$baseUrl/v1/options/chain/strikes/$atmStrike" -Method Get
    Write-Host "✅ Strike $atmStrike options retrieved" -ForegroundColor Green
    Write-Host ($response | ConvertTo-Json -Depth 3)
    Write-Host ""
} catch {
    Write-Host "❌ Failed to get strike options: $_" -ForegroundColor Red
    Write-Host ""
}

# Test 7: Get Available Expiries
Write-Host "Test 7: Get Available Expiries" -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$baseUrl/v1/options/expiries" -Method Get
    Write-Host "✅ Expiries retrieved" -ForegroundColor Green
    Write-Host ($response | ConvertTo-Json -Depth 3)
    Write-Host ""
} catch {
    Write-Host "❌ Failed to get expiries: $_" -ForegroundColor Red
    Write-Host ""
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Testing Complete!" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
