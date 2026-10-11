-- Why each stored forecast is as wide as it is (app/forecasting/explain.py): GARCH's exact variance breakdown,
-- TreeSHAP contributions for the tree model, the formula for raw VIX. Written with the forecast and never
-- replaced; backfill rows have none. Safe to re-run.

ALTER TABLE weekly_forecasts ADD COLUMN IF NOT EXISTS explanation JSONB;
