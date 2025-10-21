-- Market data schema for Nifty historical and option chain data

-- Historical Nifty spot prices (downloaded from Yahoo Finance or NSE)
CREATE TABLE IF NOT EXISTS nifty_historical (
    date DATE PRIMARY KEY,
    open DECIMAL(10,2) NOT NULL,
    high DECIMAL(10,2) NOT NULL,
    low DECIMAL(10,2) NOT NULL,
    close DECIMAL(10,2) NOT NULL,
    volume BIGINT NOT NULL,
    historical_volatility DECIMAL(6,4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Option chain data (can be generated or cached)
CREATE TABLE IF NOT EXISTS nifty_option_chain (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    strike DECIMAL(10,2) NOT NULL,
    option_type VARCHAR(2) NOT NULL CHECK (option_type IN ('CE', 'PE')),
    spot_price DECIMAL(10,2) NOT NULL,

    -- Option pricing
    price DECIMAL(10,2),
    bid DECIMAL(10,2),
    ask DECIMAL(10,2),

    -- Greeks
    delta DECIMAL(8,6),
    gamma DECIMAL(10,8),
    theta DECIMAL(10,6),
    vega DECIMAL(10,6),
    rho DECIMAL(10,6),

    -- Market data
    implied_volatility DECIMAL(6,4),
    open_interest BIGINT,
    volume BIGINT,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(date, expiry_date, strike, option_type)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_nifty_historical_date ON nifty_historical(date DESC);
CREATE INDEX IF NOT EXISTS idx_option_chain_date ON nifty_option_chain(date DESC, expiry_date);
CREATE INDEX IF NOT EXISTS idx_option_chain_strike ON nifty_option_chain(strike, option_type);
CREATE INDEX IF NOT EXISTS idx_option_chain_expiry ON nifty_option_chain(expiry_date);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_nifty_historical_updated_at BEFORE UPDATE ON nifty_historical
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_nifty_option_chain_updated_at BEFORE UPDATE ON nifty_option_chain
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Comments for documentation
COMMENT ON TABLE nifty_historical IS 'Historical daily OHLCV data for Nifty index';
COMMENT ON TABLE nifty_option_chain IS 'Option chain data with Greeks and pricing information';
COMMENT ON COLUMN nifty_historical.historical_volatility IS 'Annualized historical volatility (rolling 30-day)';
COMMENT ON COLUMN nifty_option_chain.option_type IS 'CE for Call European, PE for Put European';
