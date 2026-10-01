-- Market data for the S&P 500 (SPX): underlying history, VIX, risk-free rates
-- and collected option chain snapshots. Populated by scripts/populate_us_data.py
-- and scripts/spx_chain_snapshot.py.

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Daily OHLCV for the underlying index
CREATE TABLE IF NOT EXISTS underlying_daily (
    symbol VARCHAR(16) NOT NULL,
    date DATE NOT NULL,
    open DECIMAL(12,2) NOT NULL,
    high DECIMAL(12,2) NOT NULL,
    low DECIMAL(12,2) NOT NULL,
    close DECIMAL(12,2) NOT NULL,
    volume BIGINT NOT NULL DEFAULT 0,
    historical_volatility DECIMAL(6,4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, date)
);

-- CBOE VIX daily close: 30-day implied volatility of SPX, in vol points (e.g. 15.2)
CREATE TABLE IF NOT EXISTS vix_daily (
    date DATE PRIMARY KEY,
    close DECIMAL(8,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Risk-free rate by date, as a decimal (FRED DGS3MO 3-month T-bill, e.g. 0.0425)
CREATE TABLE IF NOT EXISTS rates_daily (
    date DATE PRIMARY KEY,
    rate DECIMAL(8,6) NOT NULL,
    source VARCHAR(32) NOT NULL DEFAULT 'FRED:DGS3MO',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Listed option chains captured from a data source (delayed quotes)
CREATE TABLE IF NOT EXISTS option_chain_snapshots (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(16) NOT NULL,
    snapshot_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    strike DECIMAL(12,2) NOT NULL,
    option_type CHAR(1) NOT NULL CHECK (option_type IN ('C', 'P')),
    underlying_price DECIMAL(12,2),
    bid DECIMAL(12,4),
    ask DECIMAL(12,4),
    last DECIMAL(12,4),
    implied_volatility DECIMAL(8,4),
    open_interest BIGINT,
    volume BIGINT,
    source VARCHAR(32) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (symbol, snapshot_date, expiry_date, strike, option_type, source)
);

CREATE INDEX IF NOT EXISTS idx_underlying_daily_date ON underlying_daily(symbol, date DESC);
CREATE INDEX IF NOT EXISTS idx_chain_snapshots_lookup ON option_chain_snapshots(symbol, snapshot_date, expiry_date);

CREATE OR REPLACE TRIGGER update_underlying_daily_updated_at BEFORE UPDATE ON underlying_daily
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_option_chain_snapshots_updated_at BEFORE UPDATE ON option_chain_snapshots
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE underlying_daily IS 'Daily OHLCV for the option underlying (SPX via Yahoo ^GSPC)';
COMMENT ON COLUMN underlying_daily.historical_volatility IS 'Annualised close-to-close volatility, rolling 30 sessions';
COMMENT ON TABLE vix_daily IS 'CBOE VIX daily close, used as the at-the-money implied vol for synthesized chains';
COMMENT ON TABLE rates_daily IS 'Risk-free rate by date for option pricing';
COMMENT ON TABLE option_chain_snapshots IS 'Real listed option quotes captured daily; preferred over synthesized chains when present';
