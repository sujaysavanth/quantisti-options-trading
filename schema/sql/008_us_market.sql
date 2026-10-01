-- Convert a database created for NIFTY to SPX. Safe to re-run: each step only
-- touches rows that are still in the old format, and fresh databases (seeded by
-- the updated 004-007) pass through unchanged.

-- NIFTY market data is replaced by underlying_daily / option_chain_snapshots (004).
DROP TABLE IF EXISTS nifty_option_chain;
DROP TABLE IF EXISTS nifty_historical;

-- Option types: 'CE'/'PE' -> 'C'/'P'. Strategy offsets were in NIFTY points;
-- 100 NIFTY points (~0.4% of 25,000) is about 25 SPX points, so scale by 0.25 and
-- snap to the 5-point strike grid. Both happen in one UPDATE, so a re-run, which
-- finds no 'CE'/'PE' rows, cannot rescale twice.
ALTER TABLE strategy_legs DROP CONSTRAINT IF EXISTS strategy_legs_option_type_check;
UPDATE strategy_legs
SET option_type = CASE option_type WHEN 'CE' THEN 'C' ELSE 'P' END,
    strike_offset = (ROUND(strike_offset * 0.25 / 5.0) * 5)::INT
WHERE option_type IN ('CE', 'PE');
ALTER TABLE strategy_legs ADD CONSTRAINT strategy_legs_option_type_check CHECK (option_type IN ('C', 'P'));

-- Past backtest legs keep their strikes (they are NIFTY history); only the labels change.
ALTER TABLE backtest_trade_legs DROP CONSTRAINT IF EXISTS backtest_trade_legs_option_type_check;
UPDATE backtest_trade_legs
SET option_type = CASE option_type WHEN 'CE' THEN 'C' ELSE 'P' END
WHERE option_type IN ('CE', 'PE');
ALTER TABLE backtest_trade_legs ADD CONSTRAINT backtest_trade_legs_option_type_check CHECK (option_type IN ('C', 'P'));

-- Starting capital is now in USD.
ALTER TABLE backtests ALTER COLUMN initial_capital SET DEFAULT 100000;
