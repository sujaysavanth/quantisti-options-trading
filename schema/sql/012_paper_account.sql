-- Paper account: a $30,000 starting balance, trades that close (manually, or settled 30 minutes before their
-- expiry's close), and exit prices for realised P&L. Rules in services/simulator/app/services/paper_settlement.py.
-- Safe to re-run; existing trades stay open (any past their expiry settle at intrinsic on the first check).

CREATE TABLE IF NOT EXISTS paper_account (
    id               SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    starting_balance NUMERIC(14,2) NOT NULL DEFAULT 30000,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO paper_account (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS status VARCHAR(8) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed'));
ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ;
ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS close_reason TEXT;
ALTER TABLE paper_trade_legs ADD COLUMN IF NOT EXISTS exit_price NUMERIC(12,4);

CREATE INDEX IF NOT EXISTS idx_paper_trades_status ON paper_trades(status);
