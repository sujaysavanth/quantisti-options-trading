-- Strategy Simulator Database Schema
-- This schema supports backtesting option strategies

-- Strategy templates (pre-defined or custom strategies)
CREATE TABLE IF NOT EXISTS strategies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    strategy_type VARCHAR(50) NOT NULL,
    description TEXT,
    user_id UUID, -- NULL for system strategies
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Strategy legs (individual positions that make up the strategy)
CREATE TABLE IF NOT EXISTS strategy_legs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    action VARCHAR(10) NOT NULL CHECK (action IN ('BUY', 'SELL')),
    option_type VARCHAR(2) NOT NULL CHECK (option_type IN ('CE', 'PE')),
    strike_offset INT NOT NULL, -- Offset from ATM in points (e.g., 0, +50, -100)
    quantity INT NOT NULL CHECK (quantity > 0),
    leg_order INT NOT NULL, -- Order of execution
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Backtest configurations and runs
CREATE TABLE IF NOT EXISTS backtests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID NOT NULL REFERENCES strategies(id),
    name VARCHAR(100) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_capital DECIMAL(15,2) NOT NULL CHECK (initial_capital > 0),
    entry_logic VARCHAR(50) NOT NULL DEFAULT 'ON_DATE', -- ON_DATE, DAILY, WEEKLY, MONTHLY
    exit_logic VARCHAR(50) NOT NULL DEFAULT 'ON_EXPIRY', -- ON_EXPIRY, STOP_LOSS, TARGET, DAYS
    stop_loss_pct DECIMAL(5,2), -- Stop loss as percentage
    target_pct DECIMAL(5,2), -- Target profit as percentage
    max_holding_days INT, -- Maximum days to hold position
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- Individual trades within a backtest
CREATE TABLE IF NOT EXISTS backtest_trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    backtest_id UUID NOT NULL REFERENCES backtests(id) ON DELETE CASCADE,
    trade_number INT NOT NULL,
    entry_date DATE NOT NULL,
    exit_date DATE,
    expiry_date DATE NOT NULL,
    entry_spot_price DECIMAL(10,2) NOT NULL,
    exit_spot_price DECIMAL(10,2),
    entry_premium DECIMAL(10,2) NOT NULL, -- Total premium paid/received
    exit_premium DECIMAL(10,2),
    pnl DECIMAL(15,2),
    pnl_pct DECIMAL(8,4),
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED')),
    exit_reason VARCHAR(50), -- EXPIRY, STOP_LOSS, TARGET, MAX_DAYS
    holding_days INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at TIMESTAMPTZ
);

-- Individual legs of each trade
CREATE TABLE IF NOT EXISTS backtest_trade_legs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id UUID NOT NULL REFERENCES backtest_trades(id) ON DELETE CASCADE,
    action VARCHAR(10) NOT NULL CHECK (action IN ('BUY', 'SELL')),
    option_type VARCHAR(2) NOT NULL CHECK (option_type IN ('CE', 'PE')),
    strike DECIMAL(10,2) NOT NULL,
    expiry_date DATE NOT NULL,
    quantity INT NOT NULL,
    entry_price DECIMAL(10,2) NOT NULL,
    exit_price DECIMAL(10,2),
    entry_iv DECIMAL(6,4), -- Implied volatility at entry
    exit_iv DECIMAL(6,4),
    pnl DECIMAL(15,2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Backtest performance metrics
CREATE TABLE IF NOT EXISTS backtest_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    backtest_id UUID NOT NULL UNIQUE REFERENCES backtests(id) ON DELETE CASCADE,
    total_trades INT NOT NULL,
    winning_trades INT NOT NULL,
    losing_trades INT NOT NULL,
    win_rate DECIMAL(5,2) NOT NULL,
    total_pnl DECIMAL(15,2) NOT NULL,
    avg_pnl_per_trade DECIMAL(15,2) NOT NULL,
    max_profit DECIMAL(15,2) NOT NULL,
    max_loss DECIMAL(15,2) NOT NULL,
    max_drawdown DECIMAL(15,2) NOT NULL,
    max_drawdown_pct DECIMAL(8,4) NOT NULL,
    sharpe_ratio DECIMAL(8,4),
    sortino_ratio DECIMAL(8,4),
    profit_factor DECIMAL(8,4), -- Gross profit / Gross loss
    avg_holding_days DECIMAL(8,2),
    final_capital DECIMAL(15,2) NOT NULL,
    total_return_pct DECIMAL(8,4) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_strategies_type ON strategies(strategy_type);
CREATE INDEX IF NOT EXISTS idx_strategies_user ON strategies(user_id);
CREATE INDEX IF NOT EXISTS idx_strategy_legs_strategy ON strategy_legs(strategy_id);
CREATE INDEX IF NOT EXISTS idx_backtests_strategy ON backtests(strategy_id);
CREATE INDEX IF NOT EXISTS idx_backtests_status ON backtests(status);
CREATE INDEX IF NOT EXISTS idx_backtests_dates ON backtests(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_backtest_trades_backtest ON backtest_trades(backtest_id);
CREATE INDEX IF NOT EXISTS idx_backtest_trades_dates ON backtest_trades(entry_date, exit_date);
CREATE INDEX IF NOT EXISTS idx_backtest_trade_legs_trade ON backtest_trade_legs(trade_id);

-- Insert pre-defined strategies
INSERT INTO strategies (name, strategy_type, description) VALUES
('Long Straddle', 'LONG_STRADDLE', 'Buy ATM call and put with same strike and expiry. Profit from large moves in either direction.'),
('Short Straddle', 'SHORT_STRADDLE', 'Sell ATM call and put with same strike and expiry. Profit from low volatility.'),
('Long Strangle', 'LONG_STRANGLE', 'Buy OTM call and put. Lower cost than straddle, needs larger move to profit.'),
('Short Strangle', 'SHORT_STRANGLE', 'Sell OTM call and put. Profit from low volatility with defined risk.'),
('Bull Call Spread', 'BULL_CALL_SPREAD', 'Buy lower strike call, sell higher strike call. Limited profit and loss.'),
('Bear Put Spread', 'BEAR_PUT_SPREAD', 'Buy higher strike put, sell lower strike put. Profit from downward move.'),
('Iron Condor', 'IRON_CONDOR', 'Sell OTM call spread and put spread. Profit from range-bound market.'),
('Iron Butterfly', 'IRON_BUTTERFLY', 'Sell ATM straddle, buy OTM strangle. Profit from low volatility.')
ON CONFLICT DO NOTHING;

-- Get strategy IDs (for leg insertion)
DO $$
DECLARE
    straddle_id UUID;
    short_straddle_id UUID;
    strangle_id UUID;
    short_strangle_id UUID;
    bull_call_id UUID;
    bear_put_id UUID;
    iron_condor_id UUID;
    iron_butterfly_id UUID;
BEGIN
    -- Get strategy IDs
    SELECT id INTO straddle_id FROM strategies WHERE strategy_type = 'LONG_STRADDLE' LIMIT 1;
    SELECT id INTO short_straddle_id FROM strategies WHERE strategy_type = 'SHORT_STRADDLE' LIMIT 1;
    SELECT id INTO strangle_id FROM strategies WHERE strategy_type = 'LONG_STRANGLE' LIMIT 1;
    SELECT id INTO short_strangle_id FROM strategies WHERE strategy_type = 'SHORT_STRANGLE' LIMIT 1;
    SELECT id INTO bull_call_id FROM strategies WHERE strategy_type = 'BULL_CALL_SPREAD' LIMIT 1;
    SELECT id INTO bear_put_id FROM strategies WHERE strategy_type = 'BEAR_PUT_SPREAD' LIMIT 1;
    SELECT id INTO iron_condor_id FROM strategies WHERE strategy_type = 'IRON_CONDOR' LIMIT 1;
    SELECT id INTO iron_butterfly_id FROM strategies WHERE strategy_type = 'IRON_BUTTERFLY' LIMIT 1;

    -- Long Straddle legs
    INSERT INTO strategy_legs (strategy_id, action, option_type, strike_offset, quantity, leg_order) VALUES
    (straddle_id, 'BUY', 'CE', 0, 1, 1),
    (straddle_id, 'BUY', 'PE', 0, 1, 2);

    -- Short Straddle legs
    INSERT INTO strategy_legs (strategy_id, action, option_type, strike_offset, quantity, leg_order) VALUES
    (short_straddle_id, 'SELL', 'CE', 0, 1, 1),
    (short_straddle_id, 'SELL', 'PE', 0, 1, 2);

    -- Long Strangle legs (100 points OTM)
    INSERT INTO strategy_legs (strategy_id, action, option_type, strike_offset, quantity, leg_order) VALUES
    (strangle_id, 'BUY', 'CE', 100, 1, 1),
    (strangle_id, 'BUY', 'PE', -100, 1, 2);

    -- Short Strangle legs (100 points OTM)
    INSERT INTO strategy_legs (strategy_id, action, option_type, strike_offset, quantity, leg_order) VALUES
    (short_strangle_id, 'SELL', 'CE', 100, 1, 1),
    (short_strangle_id, 'SELL', 'PE', -100, 1, 2);

    -- Bull Call Spread legs (Buy ATM, Sell 100 OTM)
    INSERT INTO strategy_legs (strategy_id, action, option_type, strike_offset, quantity, leg_order) VALUES
    (bull_call_id, 'BUY', 'CE', 0, 1, 1),
    (bull_call_id, 'SELL', 'CE', 100, 1, 2);

    -- Bear Put Spread legs (Buy ATM, Sell 100 OTM)
    INSERT INTO strategy_legs (strategy_id, action, option_type, strike_offset, quantity, leg_order) VALUES
    (bear_put_id, 'BUY', 'PE', 0, 1, 1),
    (bear_put_id, 'SELL', 'PE', -100, 1, 2);

    -- Iron Condor legs (Sell 100 OTM call/put spread, Buy 200 OTM call/put)
    INSERT INTO strategy_legs (strategy_id, action, option_type, strike_offset, quantity, leg_order) VALUES
    (iron_condor_id, 'BUY', 'PE', -200, 1, 1),
    (iron_condor_id, 'SELL', 'PE', -100, 1, 2),
    (iron_condor_id, 'SELL', 'CE', 100, 1, 3),
    (iron_condor_id, 'BUY', 'CE', 200, 1, 4);

    -- Iron Butterfly legs (Sell ATM straddle, Buy 100 OTM strangle)
    INSERT INTO strategy_legs (strategy_id, action, option_type, strike_offset, quantity, leg_order) VALUES
    (iron_butterfly_id, 'BUY', 'PE', -100, 1, 1),
    (iron_butterfly_id, 'SELL', 'PE', 0, 1, 2),
    (iron_butterfly_id, 'SELL', 'CE', 0, 1, 3),
    (iron_butterfly_id, 'BUY', 'CE', 100, 1, 4);
END $$;
