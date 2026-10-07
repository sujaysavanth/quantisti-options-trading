-- Daily index series used as features by the range forecast: VIX9D, VIX3M, VVIX, SKEW (CBOE) and
-- BAA10Y, T10Y2Y (FRED). Written by the Spark daily query from market.daily (dataset 'index');
-- the list lives in services/ingest/app/sources/indexes.py. Safe to re-run.

CREATE TABLE IF NOT EXISTS index_daily (
    symbol     VARCHAR(16)      NOT NULL,
    date       DATE             NOT NULL,
    close      double precision NOT NULL,   -- in the series' own units: vol points, index points, or percent
    source     VARCHAR(16)      NOT NULL,   -- 'cboe' or 'fred'
    created_at TIMESTAMPTZ      NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ      NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, date)
);

-- The gap detector also watches these series.
ALTER TABLE ingest_gaps DROP CONSTRAINT IF EXISTS ingest_gaps_dataset_check;
ALTER TABLE ingest_gaps ADD CONSTRAINT ingest_gaps_dataset_check
    CHECK (dataset IN ('daily', 'vix', 'rates', 'index', 'intraday', 'chain'));
