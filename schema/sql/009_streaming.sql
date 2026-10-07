-- Tables for the Kafka/Spark streaming pipeline. Safe to re-run.

-- Intraday OHLCV bars for SPX and VIX, written by the streaming pipeline.
CREATE TABLE IF NOT EXISTS intraday_bars (
    symbol      VARCHAR(16)  NOT NULL,
    interval    VARCHAR(4)   NOT NULL CHECK (interval IN ('1m', '5m', '1h')),
    ts          TIMESTAMPTZ  NOT NULL,          -- bar start time (UTC)
    open        DECIMAL(12,4) NOT NULL,
    high        DECIMAL(12,4) NOT NULL,
    low         DECIMAL(12,4) NOT NULL,
    close       DECIMAL(12,4) NOT NULL,
    volume      BIGINT       NOT NULL DEFAULT 0,
    source      VARCHAR(32)  NOT NULL,          -- e.g. 'yahoo'
    ingested_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, interval, ts),
    CHECK (high >= low AND open > 0 AND close > 0)
);

-- Missing data found by the gap detector, and what happened to it.
CREATE TABLE IF NOT EXISTS ingest_gaps (
    dataset    VARCHAR(16) NOT NULL CHECK (dataset IN ('daily', 'vix', 'rates', 'intraday', 'chain')),
    symbol     VARCHAR(16) NOT NULL,            -- 'SPX', 'VIX', or '1m'/'5m'/'1h' suffix e.g. 'SPX:1m'
    gap_date   DATE        NOT NULL,            -- the trading session that is missing data
    detail     TEXT,                            -- e.g. 'bars 212/390'
    status     VARCHAR(16) NOT NULL DEFAULT 'requested'
               CHECK (status IN ('requested', 'filled', 'unrecoverable')),
    attempts   INT         NOT NULL DEFAULT 0,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (dataset, symbol, gap_date)
);

CREATE INDEX IF NOT EXISTS idx_ingest_gaps_status ON ingest_gaps(status, gap_date);

-- Chain snapshots: when each quote was taken, and the vendor's own IV/delta.
ALTER TABLE option_chain_snapshots ADD COLUMN IF NOT EXISTS quoted_at    TIMESTAMPTZ;
ALTER TABLE option_chain_snapshots ADD COLUMN IF NOT EXISTS vendor_iv    DECIMAL(8,4);
ALTER TABLE option_chain_snapshots ADD COLUMN IF NOT EXISTS vendor_delta DECIMAL(8,6);

-- Rows saved before this column existed came from the after-close snapshot script.
UPDATE option_chain_snapshots SET quoted_at = created_at WHERE quoted_at IS NULL;
