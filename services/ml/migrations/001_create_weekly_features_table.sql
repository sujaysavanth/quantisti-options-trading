-- Migration: Create weekly_features table for ML feature storage
-- Description: Stores computed features for weekly market data

-- Create table for weekly features
CREATE TABLE IF NOT EXISTS weekly_features (
    id SERIAL PRIMARY KEY,
    week_start_date DATE NOT NULL,
    symbol VARCHAR(50) NOT NULL,

    -- Price features
    weekly_change_pct DECIMAL(10, 2),
    weekly_high_low_range_pct DECIMAL(10, 2),
    volume_ratio DECIMAL(10, 2),

    -- Technical indicators
    rsi_14 DECIMAL(10, 2),
    macd DECIMAL(10, 2),
    macd_signal DECIMAL(10, 2),
    bb_width DECIMAL(10, 2),

    -- Volatility features
    historical_vol_10d DECIMAL(10, 2),
    historical_vol_20d DECIMAL(10, 2),
    atr_14 DECIMAL(10, 2),

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    UNIQUE(week_start_date, symbol)
);

-- Create index for faster lookups
CREATE INDEX idx_weekly_features_symbol_date ON weekly_features(symbol, week_start_date DESC);
CREATE INDEX idx_weekly_features_symbol ON weekly_features(symbol);
CREATE INDEX idx_weekly_features_date ON weekly_features(week_start_date DESC);

-- Create table for weekly strategy performance (labels for ML training)
CREATE TABLE IF NOT EXISTS weekly_strategy_performance (
    id SERIAL PRIMARY KEY,
    week_start_date DATE NOT NULL,
    strategy_id UUID NOT NULL,

    -- Performance metrics
    total_profit DECIMAL(15, 2),
    win_rate DECIMAL(5, 2),
    total_trades INTEGER,
    max_drawdown DECIMAL(15, 2),
    sharpe_ratio DECIMAL(10, 4),

    -- Flag for best strategy of the week
    is_best_strategy BOOLEAN DEFAULT FALSE,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key to strategies table
    FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE,

    -- Constraints
    UNIQUE(week_start_date, strategy_id)
);

-- Create index for faster lookups
CREATE INDEX idx_weekly_strategy_perf_date ON weekly_strategy_performance(week_start_date DESC);
CREATE INDEX idx_weekly_strategy_perf_best ON weekly_strategy_performance(week_start_date, is_best_strategy) WHERE is_best_strategy = TRUE;

-- Add comments
COMMENT ON TABLE weekly_features IS 'Stores computed features for weekly market data used in ML models';
COMMENT ON TABLE weekly_strategy_performance IS 'Stores weekly strategy performance metrics for ML training labels';
