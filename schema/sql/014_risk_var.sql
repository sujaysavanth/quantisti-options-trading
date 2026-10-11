-- Value at risk of the open paper trades, stored by the stats service once per session after the close (the same
-- window as the portfolio's close snapshot), per method and confidence. The next session's close snapshot gives the
-- realised P&L that backtests it (GET /v1/risk/var/history). Safe to re-run.

CREATE TABLE IF NOT EXISTS risk_var (
    session        DATE NOT NULL,
    method         VARCHAR(24) NOT NULL,             -- historical | filtered_historical | delta_gamma_vega
    confidence     NUMERIC(4,3) NOT NULL,            -- 0.95, 0.99
    var            NUMERIC(14,2) NOT NULL,           -- 1-day loss not exceeded with that confidence (positive dollars)
    es             NUMERIC(14,2) NOT NULL,           -- expected shortfall: the average loss beyond the VaR
    account_value  NUMERIC(14,2),
    open_trades    INT NOT NULL,
    details        JSONB NOT NULL DEFAULT '{}',      -- scenario count, vol used, lookback
    computed_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (session, method, confidence)
);
