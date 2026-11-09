# Power Query (M) scripts

Every table is loaded from the CSV files that `scripts/export_dashboard.py` writes to `dashboard/data/`.

## Data folder parameter

Create a text parameter called `DataFolder` (**Manage Parameters → New**). Set its value to the absolute path of `dashboard/data/`, ending with a backslash. For example:

```
C:\path\to\Code\dashboard\data\
```

## Loading the tables

### Shared helper function `fnLoadCsv`

```m
(fileName as text) as table =>
let
    Source   = Csv.Document(File.Contents(DataFolder & fileName),
                            [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true])
in
    Promoted
```

### fact_forecast

```m
let
    Source = fnLoadCsv("fact_forecast.csv"),
    Typed  = Table.TransformColumnTypes(Source, {
        {"series_key", type text}, {"dataset", type text}, {"model", type text},
        {"origin_date", type date}, {"date", type date}, {"horizon", Int64.Type},
        {"actual", type number}, {"forecast", type number}, {"lower", type number},
        {"upper", type number}, {"scale", type number}, {"scored", Int64.Type}}, "en-GB")
in
    Typed
```

### fact_actuals

```m
let
    Source = fnLoadCsv("fact_actuals.csv"),
    Typed  = Table.TransformColumnTypes(Source, {
        {"series_key", type text}, {"dataset", type text}, {"date", type date},
        {"sales", type number}, {"closed", Int64.Type}, {"split", type text}}, "en-GB")
in
    Typed
```

### fact_metrics

```m
let
    Source = fnLoadCsv("fact_metrics.csv"),
    Typed  = Table.TransformColumnTypes(Source, {
        {"series_key", type text}, {"dataset", type text}, {"model", type text},
        {"rmse", type number}, {"mae", type number}, {"mape", type number},
        {"mase", type number}, {"coverage", type number}, {"width_scaled", type number}}, "en-GB")
in
    Typed
```

### dim_date

```m
let
    Source = fnLoadCsv("dim_date.csv"),
    Typed  = Table.TransformColumnTypes(Source, {
        {"date", type date}, {"year", Int64.Type}, {"month", Int64.Type}, {"month_name", type text},
        {"iso_week", Int64.Type}, {"weekday", type text}, {"weekday_number", Int64.Type}}, "en-GB")
in
    Typed
```

### dim_series

```m
let
    Source = fnLoadCsv("dim_series.csv"),
    Typed  = Table.TransformColumnTypes(Source, {{"series_key", type text}, {"dataset", type text},
        {"series_id", type text}}, "en-GB")
in
    Typed
```

### dim_model

```m
let
    Source = fnLoadCsv("dim_model.csv"),
    Typed  = Table.TransformColumnTypes(Source, {{"model", type text}, {"model_label", type text},
        {"family", type text}}, "en-GB")
in
    Typed
```

## Relationships

All relationships are many-to-one with single-direction filtering, from the dimension to the fact table.

| From (many) | To (one) |
|---|---|
| `fact_forecast[date]` | `dim_date[date]` |
| `fact_forecast[series_key]` | `dim_series[series_key]` |
| `fact_forecast[model]` | `dim_model[model]` |
| `fact_actuals[date]` | `dim_date[date]` |
| `fact_actuals[series_key]` | `dim_series[series_key]` |
| `fact_metrics[series_key]` | `dim_series[series_key]` |
| `fact_metrics[model]` | `dim_model[model]` |

**Sort order:** sort `dim_date[weekday]` by `dim_date[weekday_number]`, and `dim_date[month_name]` by `dim_date[month]`.
