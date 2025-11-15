# ML Features Service

Machine learning and feature engineering service for the Quantisti options trading platform.

## Purpose

- **Feature Engineering**: Compute and store technical features from market data
- **ML Models**: Host predictive models for strategy recommendations (planned)
- **Training Data**: Generate labeled datasets from backtest results

## Architecture

```
Market Service → Feature Calculators → Feature Store (PostgreSQL) → ML Models
                                              ↓
                                    Strategy Simulator (labels)
```

## Features Computed

### Price Features
- Weekly percentage change
- High-low range percentage
- Volume ratio vs average

### Technical Indicators
- RSI (14-period)
- MACD & Signal line
- Bollinger Bands width

### Volatility Features
- Historical volatility (10-day, 20-day)
- ATR (Average True Range)

## API Endpoints

### Feature Management
- `POST /v1/features/compute` - Compute features for a specific week
- `GET /v1/features/weekly/{symbol}/{date}` - Get features for a specific week
- `GET /v1/features/latest/{symbol}` - Get latest features (TODO)
- `POST /v1/features/backfill` - Backfill historical features (TODO)

### Health
- `GET /health/healthz` - Health check
- `GET /health/ready` - Readiness check

## Database Schema

### `weekly_features`
Stores computed features for each week:
- Price features
- Technical indicators
- Volatility metrics

### `weekly_strategy_performance`
Stores strategy performance by week (for ML training labels):
- Performance metrics
- Best strategy flag

## Setup

### Database Migration

Run the migration to create required tables:

```bash
psql -U quantisti -d quantisti -f services/ml/migrations/001_create_weekly_features_table.sql
```

### Running the Service

```bash
# With Docker Compose
docker compose up ml

# Access at http://localhost:8085
```

## Development Status

### ✅ Completed
- Service skeleton and structure
- Database connection management
- Feature calculator modules (price, technical, volatility)
- API endpoint structure
- Database schema design

### 🚧 In Progress
- Market data integration (needs market service API implementation)
- Feature persistence (needs database schema deployment)
- Feature retrieval endpoints

### 📋 TODO
- Implement market data fetching from market service
- Complete database save/load operations
- Implement backfill functionality for historical data
- Add ML model training pipeline
- Add prediction endpoints
- Add feature validation and quality checks

## Next Steps

1. **Deploy Database Schema**: Run the migration to create tables
2. **Integrate Market Service**: Update `market_client.py` with actual market service endpoints
3. **Test Feature Computation**: Compute features for sample weeks
4. **Backfill Historical Data**: Generate training dataset (2-3 years)
5. **Train Initial Model**: Build first prediction model
6. **Deploy Model**: Add prediction endpoints

## Configuration

Environment variables:
- `DATABASE_URL`: PostgreSQL connection string
- `MARKET_SERVICE_URL`: Market data service URL
- `ENV`: Environment (development/production)

## Dependencies

- FastAPI: Web framework
- pandas/numpy: Data processing
- psycopg2: PostgreSQL client
- httpx: HTTP client for market service
