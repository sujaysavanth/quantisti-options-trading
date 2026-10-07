-- Feature version 2 (services/ml/app/dataset/features.py FEATURE_GROUPS) and the weekly open-interest recorder.
-- Safe to re-run.

ALTER TABLE weekly_features
    -- term structure and vol of vol (index_daily, CBOE)
    ADD COLUMN IF NOT EXISTS vix9d           double precision,
    ADD COLUMN IF NOT EXISTS vix9d_ratio     double precision,   -- VIX9D / VIX: > 1 means short-term stress
    ADD COLUMN IF NOT EXISTS vix_term        double precision,   -- VIX / VIX3M: > 1 means an inverted curve
    ADD COLUMN IF NOT EXISTS vvix            double precision,
    ADD COLUMN IF NOT EXISTS skew_index      double precision,   -- CBOE SKEW
    -- credit and macro (index_daily, FRED; taken strictly before the anchor)
    ADD COLUMN IF NOT EXISTS baa10y          double precision,
    ADD COLUMN IF NOT EXISTS baa10y_chg_4w   double precision,
    ADD COLUMN IF NOT EXISTS t10y2y          double precision,
    -- support / resistance
    ADD COLUMN IF NOT EXISTS dist_high_20d   double precision,
    ADD COLUMN IF NOT EXISTS dist_low_20d    double precision,
    ADD COLUMN IF NOT EXISTS dist_low_52w    double precision,
    -- next week's option chain at the anchor (missing 2024 .. Sep 2026: no real chains)
    ADD COLUMN IF NOT EXISTS atm_iv_1w       double precision,
    ADD COLUMN IF NOT EXISTS skew_25d        double precision,
    ADD COLUMN IF NOT EXISTS pc_volume_ratio double precision;

-- Open-interest levels for next week's expiry, from live CBOE chains (OptionsDX has no open interest).
-- Recorded weekly so that, after about a year, they can be tested as features. Not used by models yet.
CREATE TABLE IF NOT EXISTS weekly_oi_levels (
    symbol      VARCHAR(50)      NOT NULL,
    anchor_date DATE             NOT NULL,   -- the week's last session: the chain is from its close
    expiry_date DATE             NOT NULL,   -- next week's expiry
    source      VARCHAR(16)      NOT NULL,
    spot        double precision NOT NULL,
    put_wall    double precision,            -- strike <= spot with the most put open interest
    call_wall   double precision,            -- strike >= spot with the most call open interest
    max_pain    double precision,            -- settlement with the smallest total payout to holders
    gex         double precision,            -- naive dealer gamma exposure, $ per 1% move
    contracts   BIGINT           NOT NULL,   -- open interest counted (strikes within 5% of spot)
    created_at  TIMESTAMPTZ      NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ      NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, anchor_date)
);
