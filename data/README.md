# Data

The raw data are **not** included in this repository. They are the files of two Kaggle competitions, which must be downloaded from Kaggle after signing in and accepting each competition's rules:

| Dataset | Kaggle page | Files used |
|---|---|---|
| M5 Forecasting - Accuracy | https://www.kaggle.com/competitions/m5-forecasting-accuracy/data | `calendar.csv`, `sales_train_evaluation.csv` (the other files were checked but not used) |
| Rossmann Store Sales | https://www.kaggle.com/competitions/rossmann-store-sales/data | `train.csv`, `store.csv` (the other files were checked but not used) |

## Expected layout

By default the code looks for the files in a folder called `Dataset` next to the `Code` folder:

```
Dataset/
  m5-forecasting-accuracy/
    calendar.csv
    sales_train_evaluation.csv
    sales_train_validation.csv
    sell_prices.csv
    sample_submission.csv
  rossmann-store-sales/
    train.csv
    test.csv
    store.csv
    sample_submission.csv
```

To use another location, set the environment variable `RAW_DATA_DIR` to the folder that contains the two competition folders.

## Checking a download

`checksums.sha256` lists the SHA-256 checksum of every file used in the dissertation. To confirm that a download is identical:

```
python scripts/check_raw_data.py --verify
```

To produce the full integrity report (rows, columns, column names and missing cells):

```
python scripts/check_raw_data.py
```

## Derived data

Every derived file (prepared panels, forecasts, metrics, tables, figures and the dashboard extracts) is written under `outputs/` or `dashboard/data/` by the pipeline scripts. Large intermediate files in `outputs/interim/` and trained models in `outputs/models/` are excluded from version control. So are the files that carry daily store-level sales derived from the Kaggle data: `outputs/forecasts/` (the forecasts contain the actual sales), `dashboard/data/fact_actuals.csv`, `dashboard/data/fact_forecast.csv`. The dashboard export PDF `reports/PowerBI/Dashboard.pdf` is tracked: its pages are the same as the `dash_built_*` images in `outputs/figures/` and it shows only a few aggregated daily values. The Power BI file (`*.pbix`) stays excluded, because it stores the competition data. To regenerate them, download the raw files as described above, run the pipeline (`Resume-Pipeline.bat`, which writes `outputs/forecasts/`), then `python scripts/export_dashboard.py` (it calls `src/export_powerbi.py` and writes `dashboard/data/`).
