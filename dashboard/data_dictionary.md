# Data dictionary: dashboard tables

All files are UTF-8 CSV written by `scripts/export_dashboard.py`. Dates use ISO 8601 (`YYYY-MM-DD`).

## dim_date

| Column | Type | Description |
|---|---|---|
| date | date | Calendar day (both datasets) |
| year, month, month_name | int / text | Calendar attributes |
| iso_week | int | ISO week number (repeats every year; not used for drill-down) |
| week_start | date | Monday of the week; week level of the date hierarchy for drill-down |
| weekday, weekday_number | text / int | Day name and number (Monday = 1) |

## dim_series

| Column | Type | Description |
|---|---|---|
| series_key | text | Dataset and series identifier, e.g. `M5\|CA_1` or `Rossmann\|store_17`. This is the relationship key |
| dataset | text | `M5` or `Rossmann` |
| series_id | text | Store identifier |
| state | text | M5 only: US state (CA, TX or WI) |
| store, StoreType, Assortment, CompetitionDistance, Promo2 | mixed | Rossmann only: store attributes from `store.csv` |

## dim_model

| Column | Type | Description |
|---|---|---|
| model | text | Model code (`snaive`, `arima`, `ets`, `ffnn`, `lstm`, `hyb_d`, `hyb_ms`, `hyb_z`) |
| model_label | text | Readable name |
| family | text | Benchmark, Statistical, Neural or Hybrid |

## fact_actuals

| Column | Type | Description |
|---|---|---|
| series_key, dataset, date | text / date | Keys |
| sales | number | Recorded daily sales: units (M5) or turnover (Rossmann; the source does not state the currency) |
| closed | int | 1 = known closure (Rossmann `Open = 0`; M5 Christmas Day) |
| split | text | Training, Validation or Test |

## fact_forecast

One row per series, model, seed, forecast origin and horizon day (about 219,500 rows in total: three statistical models once and five network models five times, for both datasets).

| Column | Type | Description |
|---|---|---|
| series_key, dataset, model | text | Keys |
| origin_date | date | First forecast day of the 28-day window |
| date | date | Target day |
| horizon | int | Days ahead (1 to 28) |
| seed | int | Training seed: 0 for the statistical models and the benchmark, 1 to 5 for the five network models (one set of forecasts per seed) |
| actual | number | Recorded sales on the target day |
| forecast | number | Point forecast (clipped at zero) |
| lower, upper | number | 95% split-conformal interval |
| scale | number | MASE denominator: in-sample seasonal-naive MAE of the series |
| scored | int | 1 = trading day with positive sales; all accuracy measures use these rows only |

## fact_metrics

Per-series test metrics: RMSE, MAE, MAPE (%), MASE, interval coverage and scaled interval width. One row per series, model and seed (`seed` as in `fact_forecast`). The mean of `mase` over all rows of a model equals the report's five-seed test MASE.
