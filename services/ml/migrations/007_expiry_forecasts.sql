-- Forecasts of the close at every listed expiry within 10 sessions, made at each session's close
-- (app/forecasting/horizons.py). One row per origin close and expiry, written once and never recomputed;
-- outcomes come from underlying_daily at the expiry. Safe to re-run.

CREATE TABLE IF NOT EXISTS expiry_forecasts (
    symbol          VARCHAR(50)        NOT NULL,
    origin_date     DATE               NOT NULL,   -- the session whose close the forecast is made at
    expiry_date     DATE               NOT NULL,
    sessions        SMALLINT           NOT NULL,   -- sessions from origin to expiry (the horizon)
    method          VARCHAR(32)        NOT NULL,   -- garch
    origin          VARCHAR(16)        NOT NULL CHECK (origin IN ('live', 'backfill')),
    spot            double precision   NOT NULL,   -- origin close; level = spot * exp(q)
    vix_close       double precision,
    q05             double precision   NOT NULL,   -- quantiles of ln(close[expiry] / close[origin])
    q10             double precision   NOT NULL,
    q50             double precision   NOT NULL,
    q90             double precision   NOT NULL,
    q95             double precision   NOT NULL,
    sigma           double precision,              -- sqrt of the summed variance path (live rows)
    z               double precision[],            -- quantile multipliers for this horizon (q = sigma * z)
    variance_path   double precision[],            -- each session's variance up to the expiry (fraction^2)
    path_dates      DATE[],                        -- the sessions the path covers
    trained_through DATE,
    created_at      TIMESTAMPTZ        NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, origin_date, expiry_date, method)
);

CREATE INDEX IF NOT EXISTS idx_expiry_forecasts_origin ON expiry_forecasts (symbol, origin_date DESC);
