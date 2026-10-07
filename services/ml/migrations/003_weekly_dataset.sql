-- Point-in-time weekly dataset for the range forecast (services/ml/app/dataset/).
-- Safe to re-run.
--
-- weekly_features gains the week's anchor (its last session, whose close the features are taken at),
-- the model features, and full precision: DECIMAL(10,2) rounded realised vol and VIX spreads to 0.01.
-- weekly_labels holds what happened the following week; features and labels join on (symbol, anchor_date).

ALTER TABLE weekly_features
    ALTER COLUMN weekly_change_pct         TYPE double precision,
    ALTER COLUMN weekly_high_low_range_pct TYPE double precision,
    ALTER COLUMN volume_ratio              TYPE double precision,
    ALTER COLUMN rsi_14                    TYPE double precision,
    ALTER COLUMN macd                      TYPE double precision,
    ALTER COLUMN macd_signal               TYPE double precision,
    ALTER COLUMN bb_width                  TYPE double precision,
    ALTER COLUMN historical_vol_10d        TYPE double precision,
    ALTER COLUMN historical_vol_20d        TYPE double precision,
    ALTER COLUMN atr_14                    TYPE double precision,
    ALTER COLUMN vix_close                 TYPE double precision,
    ALTER COLUMN vix_change_1w             TYPE double precision,
    ALTER COLUMN vix_hv_spread             TYPE double precision;

ALTER TABLE weekly_features
    ADD COLUMN IF NOT EXISTS anchor_date     DATE,
    ADD COLUMN IF NOT EXISTS ret_1w          double precision,   -- log return over the week
    ADD COLUMN IF NOT EXISTS ret_4w          double precision,
    ADD COLUMN IF NOT EXISTS range_1w        double precision,   -- (week high - week low) / close
    ADD COLUMN IF NOT EXISTS rv_5d           double precision,   -- realised vol, annualised, decimal
    ADD COLUMN IF NOT EXISTS rv_20d          double precision,
    ADD COLUMN IF NOT EXISTS rv_60d          double precision,
    ADD COLUMN IF NOT EXISTS vix_pct_1y      double precision,   -- VIX percentile over the last year, 0..1
    ADD COLUMN IF NOT EXISTS atr_pct         double precision,
    ADD COLUMN IF NOT EXISTS dist_ma50       double precision,
    ADD COLUMN IF NOT EXISTS drawdown_52w    double precision,
    ADD COLUMN IF NOT EXISTS rate_3m         double precision,
    ADD COLUMN IF NOT EXISTS sessions_next   INT,                -- sessions in the coming week (4 in holiday weeks)
    ADD COLUMN IF NOT EXISTS feature_version INT;

CREATE UNIQUE INDEX IF NOT EXISTS weekly_features_symbol_anchor ON weekly_features (symbol, anchor_date);

CREATE TABLE IF NOT EXISTS weekly_labels (
    symbol           VARCHAR(50) NOT NULL,
    anchor_date      DATE        NOT NULL,     -- this week's last close
    next_anchor_date DATE        NOT NULL,     -- next week's last close (its expiry)
    sessions         INT         NOT NULL,
    close_ret        double precision NOT NULL,   -- ln(close[next] / close[anchor]): the forecast target
    high_ret         double precision NOT NULL,   -- ln(next week's high / close[anchor])
    low_ret          double precision NOT NULL,   -- ln(next week's low  / close[anchor])
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, anchor_date)
);

COMMENT ON TABLE weekly_labels IS 'Next-week outcomes for each weekly anchor; the target for the range forecast';
