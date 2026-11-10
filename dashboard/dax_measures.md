# DAX measures

These are the measures of the forecasting dashboard. Create them in a dedicated measures table, for example with **Enter data**, named `_Measures`.

## How the measures read the data

| Rule | Explanation |
|---|---|
| Scored days only | Every accuracy and volume measure is restricted to scored days (`fact_forecast[scored] = 1`): trading days with positive sales. This is the same rule as the Python evaluation (`src/evaluation.py`). |
| One dataset at a time | M5 sales are units and Rossmann sales are turnover, so every measure that **sums sales** returns BLANK unless exactly one dataset is selected (`HASONEVALUE ( dim_series[dataset] )`). Scale-free measures (MASE, coverage, risk-day counts) work across datasets. |
| Slicers | All measures respond to the slicers for dataset, store (`dim_series`), model (`dim_model`), forecast origin and date. |
| Neural models | `fact_forecast` and `fact_metrics` hold seed 1 only (`src/export_powerbi.py`). The report averages the neural results over five seeds, so the dashboard reproduces the seed-1 values, not the five-seed means. |
| Which MASE | The report's MASE is the **mean of the per-store MASE values**. The dashboard measure `MASE (store average)` reproduces it. The measure `MASE` pools all scored days of the current selection and equals the per-store value when one store is selected. |

## Base volume measures (one dataset only)

```dax
Actual Sales (scored) =
IF (
    HASONEVALUE ( dim_series[dataset] ),
    CALCULATE ( SUM ( fact_forecast[actual] ), fact_forecast[scored] = 1 )
)

Forecast Sales (scored) =
IF (
    HASONEVALUE ( dim_series[dataset] ),
    CALCULATE ( SUM ( fact_forecast[forecast] ), fact_forecast[scored] = 1 )
)

Forecast Upper 95% (scored) =
IF (
    HASONEVALUE ( dim_series[dataset] ),
    CALCULATE ( SUM ( fact_forecast[upper] ), fact_forecast[scored] = 1 )
)

Forecast Lower 95% (scored) =
IF (
    HASONEVALUE ( dim_series[dataset] ),
    CALCULATE ( SUM ( fact_forecast[lower] ), fact_forecast[scored] = 1 )
)
```

## Accuracy measures

Python definitions (`src/evaluation.py`, per store, scored days only): MAE = mean |actual - forecast|; RMSE = sqrt(mean (actual - forecast)^2); MAPE = mean |actual - forecast| / actual; MASE = mean |actual - forecast| / scale. The report then averages the per-store values.

```dax
Forecast Error =
[Actual Sales (scored)] - [Forecast Sales (scored)]

Bias % =
DIVIDE ( [Forecast Sales (scored)] - [Actual Sales (scored)], [Actual Sales (scored)] )

MAE =
IF (
    HASONEVALUE ( dim_series[dataset] ),
    AVERAGEX (
        FILTER ( fact_forecast, fact_forecast[scored] = 1 ),
        ABS ( fact_forecast[actual] - fact_forecast[forecast] )
    )
)

RMSE =
IF (
    HASONEVALUE ( dim_series[dataset] ),
    SQRT (
        AVERAGEX (
            FILTER ( fact_forecast, fact_forecast[scored] = 1 ),
            ( fact_forecast[actual] - fact_forecast[forecast] ) ^ 2
        )
    )
)

MAPE % =
AVERAGEX (
    FILTER ( fact_forecast, fact_forecast[scored] = 1 ),
    DIVIDE ( ABS ( fact_forecast[actual] - fact_forecast[forecast] ), fact_forecast[actual] )
)

MASE =
AVERAGEX (
    FILTER ( fact_forecast, fact_forecast[scored] = 1 ),
    DIVIDE ( ABS ( fact_forecast[actual] - fact_forecast[forecast] ), fact_forecast[scale] )
)

MASE (store average) =
AVERAGE ( fact_metrics[mase] )

RMSE (store average) =
IF ( HASONEVALUE ( dim_series[dataset] ), AVERAGE ( fact_metrics[rmse] ) )

MAPE % (store average) =
AVERAGE ( fact_metrics[mape] ) / 100
```

`fact_metrics` holds the per-store values computed in Python over all test origins, so the store-average measures respond to the dataset, store and model slicers but not to the origin or date slicers.

## Uncertainty measures

```dax
Interval Coverage % =
AVERAGEX (
    FILTER ( fact_forecast, fact_forecast[scored] = 1 ),
    IF ( fact_forecast[actual] >= fact_forecast[lower]
         && fact_forecast[actual] <= fact_forecast[upper], 1, 0 )
)

Mean Interval Width =
IF (
    HASONEVALUE ( dim_series[dataset] ),
    AVERAGEX (
        FILTER ( fact_forecast, fact_forecast[scored] = 1 ),
        fact_forecast[upper] - fact_forecast[lower]
    )
)
```

## Planning indicators

**Safety Stock Proxy:** the extra stock needed above the point forecast so that the upper 95% bound would be covered. It is a planning aid, not an optimised inventory policy.

```dax
Safety Stock Proxy =
[Forecast Upper 95% (scored)] - [Forecast Sales (scored)]
```

**Stock-out Risk Days:** scored days on which actual sales exceeded the upper bound.

```dax
Stock-out Risk Days =
COUNTROWS (
    FILTER ( fact_forecast, fact_forecast[scored] = 1 && fact_forecast[actual] > fact_forecast[upper] )
)
```

**Overstock Risk Days:** scored days on which actual sales fell below the lower bound.

```dax
Overstock Risk Days =
COUNTROWS (
    FILTER ( fact_forecast, fact_forecast[scored] = 1 && fact_forecast[actual] < fact_forecast[lower] )
)
```

**Best Model (MASE):** the model with the lowest store-average MASE in the current filter context.

```dax
Best Model (MASE) =
VAR scores =
    ADDCOLUMNS ( VALUES ( dim_model[model_label] ), "@mase", [MASE (store average)] )
RETURN
    MAXX ( TOPN ( 1, scores, [@mase], ASC ), dim_model[model_label] )
```

## Checking the measures (test plan TP-07 to TP-11)

The file `data/acceptance_values.json` holds reference values per dataset and model, computed in Python from the exported rows (seed 1 for neural models):

| JSON key | Measure |
|---|---|
| `total_actual_scored` | Actual Sales (scored) |
| `total_forecast_scored` | Forecast Sales (scored) |
| `mean_abs_error` | MAE |
| `coverage` | Interval Coverage % |
| `mase_store_average` | MASE (store average) |
| `stockout_risk_days` | Stock-out Risk Days |
| `overstock_risk_days` | Overstock Risk Days |

**To check:**

1. Set the slicers to a single dataset and a single model, with all stores and origins.
2. Read the measures listed above.
3. Compare them with the JSON values. They must agree to rounding.
