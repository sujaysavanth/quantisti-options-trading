# ML service

Builds the weekly dataset for the SPX range forecast, and (in later modules) serves the forecast itself.
The plan: predict where SPX closes at next week's expiry as a range (quantiles), and only ship a model that
beats the range VIX implies.

## Weekly dataset (`app/dataset/`)

One row per week, anchored on the week's **last session** (Friday, or Thursday before a holiday). That is also
the week's SPX expiry.

- **Features** (`features.py`) use data up to and including the anchor's close, nothing later. `build_features`
  is pure and vectorised: daily SPX/VIX/rates in, every week out. The same function builds history and the
  latest week, so training and serving can't drift.
- **Labels** (`labels.py`) are what happened next week: the expiry close as a log return (`close_ret`, the
  forecast target) and the high/low excursions. A week whose next week is incomplete or missing a session gets
  no label.
- **No lookahead** is tested: rebuilding from data cut off at an anchor gives the same features, and changing
  future prices changes nothing in the past (`tests/test_dataset.py`).

Model features (`MODEL_FEATURES`, scale-free so 2010 and 2026 are comparable):

| Group | Features |
|---|---|
| Returns | `ret_1w`, `ret_4w` (log), `range_1w` (week high - low, / close) |
| Realised vol | `rv_5d`, `rv_20d`, `rv_60d` (annualised, decimal) |
| VIX | `vix_close`, `vix_change_1w` (points since last week), `vix_hv_spread` (VIX - 20d realised vol, %), `vix_pct_1y` (0..1) |
| Technical | `rsi_14`, `bb_width`, `atr_pct`, `dist_ma50`, `drawdown_52w`, `volume_ratio` |
| Rates, calendar | `rate_3m` (taken before the anchor: FRED posts a day late), `sessions_next` (4 in holiday weeks) |

`weekly_features` also keeps its original columns (RSI, MACD, Bollinger width, ATR and historical vol in their
original definitions). `weekly_change_pct` and `weekly_high_low_range_pct` used to be measured over the whole
60-day fetch window; they now cover the week.

The first year (2010) is warm-up: the 52-week drawdown and VIX percentile need a year of history, so complete
rows start 2010-12-31 (about 820 weeks to 2026).

## Baselines and evaluation (`app/evaluation/`)

Every forecaster outputs the 5%/10%/50%/90%/95% quantiles of next week's close return and is scored
walk-forward: each test year (2014 onwards) is forecast by a model fitted only on the years before it.
`predict` never receives the test weeks' label columns.

| Baseline | Volatility forecast |
|---|---|
| `vix_raw` | VIX as published, normal quantiles, no fitting: the market's own number |
| `vix_scaled` | the same VIX sigma, with per-quantile multipliers learned from past years (absorbs bias and skew) |
| `rv_20d` | 20-day realised volatility |
| `har_rv` | HAR-RV (Corsi 2009): next week's variance from last day / week / month of squared returns |
| `garch` | GARCH(1,1) on daily returns (`arch`), summed over next week's sessions |
| `straddle` | next-week ATM straddle from real OptionsDX chains (2010-2023 only) |

All but `vix_raw` turn sigma into quantiles the same way (empirical quantiles of return / sigma over the
training years), so they differ only in how well they track volatility. Metrics (`metrics.py`): coverage of the
80%/90% bands, band width, pinball loss, Winkler interval score, and 80% coverage by VIX regime.

```bash
python -m app.cli evaluate --database-url postgresql://quantisti:quantisti@localhost:5432/quantisti
# -> data/ml/reports/baselines.md and .json (git-ignored)
```

## Setup

```bash
# Tables (not applied by scripts/db_apply.sh), in order:
docker compose exec -T postgres psql -U quantisti -d quantisti < services/ml/migrations/001_create_weekly_features_table.sql
docker compose exec -T postgres psql -U quantisti -d quantisti < services/ml/migrations/002_add_vix_features.sql
docker compose exec -T postgres psql -U quantisti -d quantisti < services/ml/migrations/003_weekly_dataset.sql   # safe to re-run

# Build every week (about a second), store it, print a report:
cd services/ml && pip install -e ".[test]"
python -m app.cli build-dataset --database-url postgresql://quantisti:quantisti@localhost:5432/quantisti \
  --export ../../data/ml/weekly.csv
```

## API (port 8085)

| Endpoint | |
|---|---|
| `POST /v1/features/backfill?symbol=SPX` | rebuild all weeks and labels, return a summary |
| `POST /v1/features/compute` | the week containing `week_start_date` (rebuilds if it isn't stored, or with `force_recompute`) |
| `GET /v1/features/weekly/SPX/{any day}` | the stored week containing that day |
| `GET /v1/features/latest/SPX` | the latest complete week |

Only SPX is supported. `/health/healthz`, `/health/readyz`, docs at `/docs`.

## Tests

```bash
cd services/ml && pip install -e ".[test]" && pytest -q
```
