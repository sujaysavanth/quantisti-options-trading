-- Implied-volatility features for SPX (see VolatilityCalculator.calculate_vix_features)
ALTER TABLE weekly_features ADD COLUMN IF NOT EXISTS vix_close DECIMAL(10, 2);
ALTER TABLE weekly_features ADD COLUMN IF NOT EXISTS vix_change_1w DECIMAL(10, 2);
ALTER TABLE weekly_features ADD COLUMN IF NOT EXISTS vix_hv_spread DECIMAL(10, 2);
