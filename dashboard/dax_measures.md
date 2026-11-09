# DAX measures

These are the measures of the forecasting dashboard. Create them in a dedicated measures table, for example with **Enter data**, named `_Measures`.

## How the measures read the data

| Rule | Explanation |
|---|---|
| Scored days only | Every accuracy measure is restricted to scored days (`fact_forecast[scored] = 1`), which are trading days with positive sales. This is the same rule the Python evaluation uses, so the dashboard reproduces the figures in the dissertation. |
| Slicers | All measures respond to the slicers for dataset, store (`dim_series`), model (`dim_model`), forecast origin and date. |
| Neural models | `fact_forecast` holds seed 1 only (`src/export_powerbi.py`). |

## Volume measures

```dax
Actual Sales (scored) =
CALCULATE ( SUM ( fact_forecast[actual] ), fact_forecast[scored] = 1 )

Forecast Sales (scored) =
CALCULATE ( SUM ( fact_forecast[forecast] ), fact_forecast[scored] = 1 )

Forecast Upper 95% (scored) =
CALCULATE ( SUM ( fact_forecast[upper] ), fact_forecast[scored] = 1 )

Forecast Lower 95% (scored) =
CALCULATE ( SUM ( fact_forecast[lower] ), fact_forecast[scored] = 1 )
```

## Accuracy measures

```dax
Forecast Error =
[Actual Sales (scored)] - [Forecast Sales (scored)]

Bias % =
DIVIDE ( [Forecast Sales (scored)] - [Actual Sales (scored)], [Actual Sales (scored)] )

MAE =
AVERAGEX (
    FILTER ( fact_forecast, fact_forecast[scored] = 1 ),
    ABS ( fact_forecast[actual] - fact_forecast[forecast] )
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

RMSE =
SQRT (
    AVERAGEX (
        FILTER ( fact_forecast, fact_forecast[scored] = 1 ),
        ( fact_forecast[actual] - fact_forecast[forecast] ) ^ 2
    )
)
```

## Uncertainty measures

```dax
Interval Coverage % =
AVERAGEX (
    FILTER ( fact_forecast, fact_forecast[scored] = 1 ),
    IF ( fact_forecast[actual] >= fact_forecast[lower]
         && fact_forecast[actual] <= fact_forecast[upper], 1, 0 )
)

Mean Interval Width =
AVERAGEX (
    FILTER ( fact_forecast, fact_forecast[scored] = 1 ),
    fact_forecast[upper] - fact_forecast[lower]
)
```

## Planning indicators

**Safety Stock Proxy:** the extra stock needed above the point forecast so that the upper 95% bound would be covered. It is a planning aid, not an optimised inventory policy.

```dax
Safety Stock Proxy =
[Forecast Upper 95% (scored)] - [Forecast Sales (scored)]
```

**Stock-out Risk Days:** the number of scored days on which actual sales exceeded the upper bound.

```dax
Stock-out Risk Days =
COUNTROWS (
    FILTER ( fact_forecast, fact_forecast[scored] = 1 && fact_forecast[actual] > fact_forecast[upper] )
)
```

**Overstock Risk Days:** the number of scored days on which actual sales fell below the lower bound.

```dax
Overstock Risk Days =
COUNTROWS (
    FILTER ( fact_forecast, fact_forecast[scored] = 1 && fact_forecast[actual] < fact_forecast[lower] )
)
```

**Best Model (MASE):** the model with the lowest MASE in the current filter context. Use it in a card.

```dax
Best Model (MASE) =
VAR scores =
    ADDCOLUMNS ( VALUES ( dim_model[model_label] ), "@mase", [MASE] )
RETURN
    MAXX ( TOPN ( 1, scores, [@mase], ASC ), dim_model[model_label] )
```

## Checking the measures (test plan TP-07 to TP-10)

The file `data/acceptance_values.json` holds four reference values per dataset and model, computed in Python:

- total actual sales
- total forecast
- mean absolute error
- coverage of the 95% interval

**To check:**

1. Set the slicers to a single dataset and a single model.
2. Read the values of `Actual Sales (scored)`, `Forecast Sales (scored)`, `MAE` and `Interval Coverage %`.
3. Compare them with the JSON values. They must agree to rounding.
