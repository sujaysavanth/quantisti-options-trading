-- Paper trading persistence tables

CREATE TABLE IF NOT EXISTS paper_trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(32) NOT NULL,
    nickname VARCHAR(120),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS paper_trade_legs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id UUID NOT NULL REFERENCES paper_trades(id) ON DELETE CASCADE,
    identifier VARCHAR(120),
    strike NUMERIC(10,2) NOT NULL,
    option_type VARCHAR(4) NOT NULL CHECK (option_type IN ('CALL', 'PUT')),
    expiry_date DATE NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    side VARCHAR(4) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    entry_price NUMERIC(12,4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_paper_trades_symbol ON paper_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_paper_trade_legs_trade ON paper_trade_legs(trade_id);
