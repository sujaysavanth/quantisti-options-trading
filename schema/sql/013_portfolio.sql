-- Portfolio snapshots: the paper account's value and open positions, taken by the portfolio service every 15 minutes
-- in session (kind 'intraday', stamped at the start of the 15-minute bucket) and once after each close (kind 'close',
-- stamped at the session close). The equity curve and performance stats read these. Safe to re-run.

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id               BIGSERIAL PRIMARY KEY,
    kind             VARCHAR(8) NOT NULL CHECK (kind IN ('intraday', 'close')),
    taken_at         TIMESTAMPTZ NOT NULL,          -- the bucket start or the session close
    observed_at      TIMESTAMPTZ NOT NULL,          -- when the service actually took it
    session          DATE NOT NULL,
    starting_balance NUMERIC(14,2) NOT NULL,
    account_value    NUMERIC(14,2) NOT NULL,
    realised_pnl     NUMERIC(14,2) NOT NULL,
    unrealised_pnl   NUMERIC(14,2) NOT NULL,
    capital_held     NUMERIC(14,2) NOT NULL,
    available        NUMERIC(14,2) NOT NULL,
    open_trades      INT NOT NULL,
    closed_trades    INT NOT NULL,
    spot             NUMERIC(12,4),                 -- SPX from the live quote, if there was one
    positions        JSONB NOT NULL DEFAULT '[]',   -- net positions at the time (see app/services/positions.py)
    UNIQUE (kind, taken_at)
);

CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_session ON portfolio_snapshots(session);
