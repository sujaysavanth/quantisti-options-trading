-- Stored weekly forecasts (batch scoring): one row per anchor and method, written once when the week's
-- forecast is made and never recomputed. Outcomes come from weekly_labels when the following week closes,
-- which is what monitoring compares against. Safe to re-run.

CREATE TABLE IF NOT EXISTS weekly_forecasts (
    symbol          VARCHAR(50)      NOT NULL,
    anchor_date     DATE             NOT NULL,   -- the Friday (or last session) the forecast is made at
    expiry_date     DATE             NOT NULL,   -- next week's last session: the close being forecast
    method          VARCHAR(32)      NOT NULL,   -- garch | gbm_sigma | vix_raw
    role            VARCHAR(16)      NOT NULL CHECK (role IN ('served', 'second_opinion', 'reference')),
    origin          VARCHAR(16)      NOT NULL CHECK (origin IN ('live', 'backfill')),
    spot            double precision NOT NULL,   -- the anchor's close; price level = spot * exp(q)
    vix_close       double precision,            -- at the anchor, for coverage by regime
    q05             double precision NOT NULL,   -- quantiles of ln(close[expiry] / close[anchor])
    q10             double precision NOT NULL,
    q50             double precision NOT NULL,
    q90             double precision NOT NULL,
    q95             double precision NOT NULL,
    trained_through DATE,                        -- the last week whose outcome the fit could use
    details         TEXT,                        -- e.g. the feature groups, or why this method is served
    created_at      TIMESTAMPTZ      NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, anchor_date, method)
);

CREATE INDEX IF NOT EXISTS idx_weekly_forecasts_role ON weekly_forecasts (symbol, role, anchor_date DESC);
