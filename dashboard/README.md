# Forecasting dashboard: build guide, specification and test plan

This folder holds everything needed to build the Power BI dashboard of the project. The `.pbix` file itself must be assembled in Power BI Desktop, because the report layer cannot be generated reliably from code. The data model, measures, page layout and tests are specified here so that the build is repeatable.

| File | Content |
|---|---|
| `data/` | CSV star schema and `acceptance_values.json`, written by `scripts/export_dashboard.py` (which calls `src/export_powerbi.py`). `fact_actuals.csv` and `fact_forecast.csv` hold daily store-level sales derived from Kaggle data, so they are not in the repository: run the pipeline and the export script to create them |
| `data_dictionary.md` | Columns of every table |
| `power_query.md` | Power Query (M) scripts, relationships and sort orders |
| `dax_measures.md` | DAX measures and how to check them |
| `README.md` | This guide: build steps, page specification, accessibility checklist and test plan |

The page wireframes and the star-schema diagram are produced by `scripts/make_design_figures.py` (`outputs/figures/dash_*.png`). They are design drawings, not screenshots.

## 1. Build steps

1. Run the pipeline up to the export (from `Code/`):

   ```
   python scripts/run_evaluation.py
   python scripts/export_dashboard.py
   ```

2. Open Power BI Desktop and create a blank report.
3. Create the text parameter `DataFolder` and the helper function `fnLoadCsv` (`power_query.md`).
4. Create the six queries `dim_date`, `dim_series`, `dim_model`, `fact_actuals`, `fact_forecast` and `fact_metrics` from `power_query.md`, then **Close & Apply**.
5. In the model view, create the seven relationships listed in `power_query.md`. Set all of them to many-to-one with single-direction filtering. Delete any relationship that Power BI detected automatically and that is not in the list.
6. Set the sort orders: `dim_date[weekday]` by `weekday_number` and `dim_date[month_name]` by `month`.
7. Create the measures table `_Measures` and add every measure from `dax_measures.md`. Format `MAPE %`, `Bias %` and `Interval Coverage %` as percentages with one decimal place, and `MASE` with three decimal places.
8. Apply the theme settings in Section 3, then build the three pages in Section 2.
9. Run the test plan in Section 5 and record the results.
10. Save the report as `dashboard/forecasting_dashboard.pbix`.

## 2. Page specification

All pages share four slicers at the top: **Dataset**, **Store** (`dim_series[series_id]`), **Model** (`dim_model[model_label]`) and **Forecast origin** (`fact_forecast[origin_date]`). Use **View → Sync slicers** so that a selection carries across pages.

### Page 1: Forecast versus actual

Audience: store managers.

| Visual | Fields | Notes |
|---|---|---|
| Line chart | Axis `dim_date[date]`; values `Actual Sales (scored)`, `Forecast Sales (scored)`, `Forecast Lower 95% (scored)`, `Forecast Upper 95% (scored)` | Actual as a solid dark line, forecast as a dashed line, bounds as thin dotted lines. Use **Error bars** or the bound lines to show the band |
| Card | `MASE` | Title "Accuracy (mean absolute scaled error, MASE; below 1 beats the naive in-sample error)" |
| Card | `Interval Coverage %` | Title "Share of days inside the 95% interval" |
| Column chart | Axis `fact_forecast[horizon]`; value `MASE` | Shows how error grows with the horizon |
| Table | Date, actual, forecast, lower, upper | For export to ordering systems |

### Page 2: Model comparison

Audience: planners and analysts.

| Visual | Fields | Notes |
|---|---|---|
| Bar chart | Axis `dim_model[model_label]`; value `MASE` | Sort ascending; data labels on |
| Line chart | Axis `fact_forecast[horizon]`; legend `dim_model[model_label]`; value `MASE` | One line style per model, so the chart remains readable in greyscale |
| Matrix | Rows `dim_series[series_id]`; columns `dim_model[model_label]`; value `MASE` | Conditional formatting by value, plus the number itself |
| Card | `Best Model (MASE)` | Responds to the slicers |
| Bar chart | Axis `dim_model[model_label]`; value `Interval Coverage %` | Add a constant line at 95% |

### Page 3: Planning

Audience: planners.

| Visual | Fields | Notes |
|---|---|---|
| Cards | `Forecast Sales (scored)`, `Safety Stock Proxy`, `Stock-out Risk Days`, `Overstock Risk Days` | Each card has a subtitle explaining the measure in one sentence |
| Clustered column chart | Axis hierarchy `dim_date[week_start]` then `dim_date[date]`; values `Forecast Sales (scored)`, `Forecast Upper 95% (scored)` | Weekly view for ordering; drill down to days |
| Bar chart | Axis `dim_series[series_id]`; value `Bias %` | Constant line at zero; positive values mean over-forecasting |

The safety stock proxy is the gap between the upper bound of the 95% interval and the point forecast. It is a planning aid, not an optimised inventory policy.

## 3. Theme and accessibility settings

| Setting | Value | Reason |
|---|---|---|
| Font | Segoe UI, at least 12 pt for body text and 10 pt for axis labels | Legibility |
| Palette | Dark blue `#1F4E79`, green `#548235`, orange `#C55A11`, purple `#7030A0`, greys | Distinguishable under common colour-vision deficiencies |
| Line styles and markers | Different for every model (same mapping as the report figures) | No information carried by colour alone |
| Data labels | On for bars and cards | Values readable without hovering |
| Alt text | Set for every visual (**Format → General → Alt text**) | Screen readers |
| Tab order | **View → Selection → Tab order**: slicers first, then visuals from top left to bottom right | Keyboard navigation |
| Titles | Every visual has a descriptive title | Context for screen-reader users |

## 4. Accessibility checklist

| # | Check | How to verify |
|---|---|---|
| A1 | Text contrast at least 4.5:1 against the background | Check theme colours in a contrast checker |
| A2 | Every chart readable in greyscale | Print to PDF in greyscale, or use a colour-blindness simulator |
| A3 | No information carried by colour alone | Models differ by line style or marker as well as colour |
| A4 | Alt text on every visual | Inspect **Format → General → Alt text** |
| A5 | Logical keyboard tab order | Tab through each page |
| A6 | All slicers usable with the keyboard | Operate each slicer with Tab, arrow keys and Enter |
| A7 | Minimum font sizes respected | Inspect visual formatting |
| A8 | Report works with the Windows high-contrast theme | Switch on a high-contrast theme and reopen the report |

## 5. Functional test plan

Expected values come from `data/acceptance_values.json`, which `scripts/export_dashboard.py` computes in Python from the same CSV files. Record the observed value and the result in the last two columns.

| ID | Test | Steps | Expected result | Observed | Result |
|---|---|---|---|---|---|
| TP-01 | Data load | Refresh all queries | Six tables load without errors; row counts equal those printed by the export script | | Passed (confirmed by the author) |
| TP-02 | Relationships | Open the model view | Exactly the seven relationships in `power_query.md`, all many-to-one and single-direction | | Passed (confirmed by the author) |
| TP-03 | Sort orders | Show weekday and month in a table | Monday to Sunday; January to December | | Passed (confirmed by the author) |
| TP-04 | Dataset slicer | Select M5, then Rossmann | Every visual changes; no Rossmann store appears under M5 | | Passed (confirmed by the author) |
| TP-05 | Store slicer | Select one store | Page 1 shows that store only | | Passed (confirmed by the author) |
| TP-06 | Model and origin slicers | Select one model and one origin | Page 1 shows 28 days from that origin | | Passed (confirmed by the author) |
| TP-07 | Actual Sales (scored) | One dataset and one model, all stores, origins and seeds (no seed slicer) | Equals `total_actual_scored` (mean over seeds; to rounding) | | Passed (confirmed by the author) |
| TP-08 | Forecast Sales (scored) | As TP-07 | Equals `total_forecast_scored` | | Passed (confirmed by the author) |
| TP-09 | MAE | As TP-07 | Equals `mean_abs_error` (all seeds pooled with equal weight) | | Passed (confirmed by the author) |
| TP-10 | Interval Coverage % | As TP-07 | Equals `coverage` | | Passed (confirmed by the author) |
| TP-11 | MASE (store average) | As TP-07 | Equals `mase_store_average`, which is the report's five-seed test MASE (`<dataset>_test_summary.csv`) | | Passed (confirmed by the author) |
| TP-12 | Best Model (MASE) | Clear the model slicer | Shows the model with the lowest MASE in the bar chart; the values equal the report's five-seed test MASE | | Passed (confirmed by the author) |
| TP-13 | Planning cards | One store, one origin | Safety stock proxy equals upper minus forecast summed over the 28 days; with all stores and origins, Stock-out and Overstock Risk Days (mean over the seeds) equal `stockout_risk_days` and `overstock_risk_days` | | Passed (confirmed by the author) |
| TP-14 | Accessibility | Checklist A1 to A8 | All checks pass | | A2 and A3 passed (confirmed by the author); A5, A6 and A8 have no recorded result |
| TP-15 | Drill-down | On page 3, drill down from a week (`week_start`) to its days and back up | Daily values sum to the weekly value; drilling up restores the weekly view | | Passed (confirmed by the author) |
| TP-16 | Static review of DAX | Compare each measure in `dax_measures.md` with the Python definition in `src/evaluation.py` and `src/export_powerbi.py` | Same filter (scored days), same formula; differences documented | | Passed (confirmed by the author) |

The author confirms that tests TP-01 to TP-16 passed; the accessibility test TP-14 passed for checks A2 and A3, while A5, A6 and A8 have no recorded result.
