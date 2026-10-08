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

Model features (feature version 2), in groups (`FEATURE_GROUPS`) so ML-3 can add one group at a time and keep it
only if the walk-forward score improves:

| Group | Features | Source |
|---|---|---|
| `price` | `ret_1w`, `ret_4w` (log), `range_1w` (week high - low, / close) | SPX daily |
| `realised_vol` | `rv_5d`, `rv_20d`, `rv_60d` (annualised, decimal) | SPX daily |
| `vix` | `vix_close`, `vix_change_1w`, `vix_hv_spread` (VIX - 20d realised vol), `vix_pct_1y` | VIX |
| `vix_term` | `vix9d`, `vix9d_ratio` (VIX9D/VIX), `vix_term` (VIX/VIX3M; > 1 = inverted), `vvix` | `index_daily` (CBOE) |
| `tail` | `skew_index` (CBOE SKEW) | `index_daily` |
| `credit_macro` | `baa10y`, `baa10y_chg_4w`, `t10y2y`, `rate_3m` (all taken before the anchor: FRED posts a day late) | `index_daily`, `rates_daily` |
| `technical` | `rsi_14`, `bb_width`, `atr_pct`, `dist_ma50`, `volume_ratio` | SPX daily |
| `support_resistance` | `dist_high_20d`, `dist_low_20d`, `drawdown_52w`, `dist_low_52w` | SPX daily |
| `calendar` | `sessions_next` (4 in holiday weeks) | NYSE calendar |
| `options` | `atm_iv_1w` (next week's ATM straddle, annualised), `skew_25d` (25-delta put IV - call IV), `pc_volume_ratio` | the anchor's chain for next week's expiry (`options.py`) |

`CORE_FEATURES` (every group but `options`) exist for every week from 2011-01-07 (once VIX9D has history).
The option features exist where real chains do: OptionsDX 2010-2023 (98% of weeks) and CBOE from October 2026;
**not 2024 to September 2026**, so models must handle them missing. An event calendar (Fed meetings, CPI and jobs
reports in the coming week) is planned for the next sprint.

**Open-interest levels** (`oi_levels.py`, table `weekly_oi_levels`) are recorded every week from live CBOE chains
but are not a model feature yet: OptionsDX has no open interest, so there is no history to train on. Put wall,
call wall, max pain and a naive dealer gamma exposure (GEX) for next week's expiry; after about a year they can
be tested. `python -m app.cli oi-levels --date 2026-10-06` shows them for any collected day.

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

## Models (`app/forecasting/`)

**Development and holdout.** Every choice (model, settings, feature groups, calibration) is made on the
development years **2014-2020**. The holdout years **2021 onwards** are scored once, with the choice frozen in
`services/ml/model_choice.json` (committed). `holdout` refuses a second run unless forced, and a forced re-run is
recorded next to the first result.

| Model | What it does |
|---|---|
| `ridge_sigma` | linear model of log next-week realised variance; missing option features median-filled with a flag |
| `gbm_sigma` | the same target with gradient-boosted trees |
| `ebm_sigma` | the same target with an explainable boosting machine (one plottable curve per feature) |
| `gbm_quantile` | trees predicting each quantile of z = return / VIX sigma directly (how to stretch VIX's range) |

The three volatility models turn sigma into quantiles exactly as the baselines do, with the mapping learned from
out-of-fold predictions (a flexible model's in-sample sigma is overconfident and would give bands that are too
narrow). Every forecaster except raw VIX also gets a `+conformal` version: each year's bands are widened or
narrowed per VIX regime from the out-of-sample misses of earlier years (`conformal.py`). Diebold-Mariano tests
(`evaluation/significance.py`) say whether a gain over scaled VIX and the best baseline is more than luck.

```bash
python -m app.cli evaluate --models        # development years: baselines + models (+ conformal) -> models_dev.md
python -m app.cli ablate --model gbm_sigma # forward feature-group selection on the development years
python -m app.cli freeze --model gbm_quantile --groups vix,vix_term,support_resistance --conformal --reason "..."
python -m app.cli holdout                  # the frozen choice on 2021 onwards, once -> holdout.md
```

## Experiment tracking and the model registry (`app/tracking.py`, `app/registry.py`)

Every `evaluate`, `ablate`, `freeze` and `holdout` run is recorded with MLflow: parameters (models, feature groups,
period), the git commit (and whether the tree had uncommitted changes), the feature version, a fingerprint of the
data, every score (pinball, coverage overall and per regime, Diebold-Mariano p-values) and the report files.
Storage is local and git-ignored: `data/ml/mlflow.db` (SQLite) and `data/ml/mlruns`. Set `ML_TRACKING=off` to
skip it, or `MLFLOW_TRACKING_URI` to use a server.

```bash
mlflow ui --backend-store-uri sqlite:///data/ml/mlflow.db --port 5050    # from the repo root: http://localhost:5050
```

`freeze` also fits the chosen forecaster on every development-period week and registers it as
`spx-weekly-range` (with its per-regime conformal adjustments), which the prediction endpoint will load.

## Research contender: Chronos-2 (`app/forecasting/chronos2.py`)

Amazon's pretrained time-series model, used zero-shot: the weekly return series up to each anchor, alone
(`chronos2`) or with VIX, VIX9D/VIX, VIX/VIX3M and 20-day realised vol as covariates (`chronos2_cov`). It needs
PyTorch, so it lives in an optional install that is not in the service image or CI:

```bash
pip install -e ".[research]"          # torch + chronos-forecasting; the model downloads on first use
python -m app.cli evaluate --models --groups vix,options,vix_term --research
```

TabPFN was considered and left out: TabPFN-2.5 is non-commercial, needs a Prior Labs account, and restricts
competitive benchmarking.

## Setup

```bash
# Tables (not applied by scripts/db_apply.sh), in order:
docker compose exec -T postgres psql -U quantisti -d quantisti < services/ml/migrations/001_create_weekly_features_table.sql
docker compose exec -T postgres psql -U quantisti -d quantisti < services/ml/migrations/002_add_vix_features.sql
docker compose exec -T postgres psql -U quantisti -d quantisti < services/ml/migrations/003_weekly_dataset.sql   # safe to re-run
docker compose exec -T postgres psql -U quantisti -d quantisti < services/ml/migrations/004_more_features.sql    # safe to re-run
# The index features need index_daily filled (schema/sql/011 + ingest `backfill-daily --indexes`).

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
