# Appendix A: Declaration on the Use of Generative AI {#app:A .appendix letter=A}

[[PENDING: check this declaration against Arden University's current policy on generative AI, and complete any official declaration form that the policy requires.]]

Generative AI was used extensively in this project. The tool was Claude Code, an AI coding assistant from Anthropic, running the Claude Opus 5.5 model inside Visual Studio Code. It worked on the author's computer, within the project folders and under the author's instructions. {tbl:aiuse} sets out how it was used, what the author did and which safeguards applied.

::: table id=tbl:aiuse widths=3.0,4.6,3.8,4.2 size=8.5
caption: Use of generative AI by task
source: Author's own work, based on the project's decisions log.
| Task | Role of the AI assistant | Role of the author | Safeguard |
|---|---|---|---|
| Project definition | [[PENDING: author to state any AI use in the proposal]] | Wrote the approved proposal: aim, objectives and outline method | Supervisor approval of the proposal |
| Literature search and review | Queried OpenAlex and Crossref, screened records, read full texts on publisher pages and wrote reading notes | Approved the discovery route after automated Google Scholar searching proved impossible | Every source checked against its DOI record and full text; claims checked against reading notes |
| Data | Checked the integrity of the files and prepared the series | Downloaded the datasets from Kaggle | Checksums and an integrity report before any experiment |
| Code and experiments | Wrote the code and tests, and ran the experiments | [[PENDING: author to describe their review of the code]] | Automated tests, leakage tests and an experiment log; every reported number produced by executed code |
| Report | Drafted the text, tables and figures in the template | [[PENDING: author to describe their review and editing]] | Citation audit; numbers in tables generated from result files |
| Decisions | Proposed options with justifications in the decisions log | Took the decisions at the review points (data, literature route, format, ethics) | Decisions log with dates |
:::

[[PENDING: the author must confirm that they have reviewed the report and the code and that they take responsibility for their content.]]

# Appendix B: Datasets and Provenance {#app:B .appendix letter=B}

## Sources

Both datasets were downloaded by the author from the Kaggle competition pages and were used without modification:

- M5 Forecasting - Accuracy [@kaggle2020m5]: <https://www.kaggle.com/competitions/m5-forecasting-accuracy/data>
- Rossmann Store Sales [@kaggle2015rossmann]: <https://www.kaggle.com/competitions/rossmann-store-sales/data>

The files were checked on 8 November 2026 before any experiment was run. {tbl:rawcheck} lists the result. All nine files opened completely. The missing cells are expected: in the M5 calendar they are the four event columns on days without an event; in the Rossmann store file they are competition and Promo2 dates for stores without that information; and in the Rossmann test file they are 11 missing opening flags. Neither test file was used, because the test periods of both competitions have no published sales.

::: table id=tbl:rawcheck csv=outputs/tables/report_raw_data_check.csv size=7.5 widths=5.6,1.4,1.6,1.4,1.6,1.2,2.8
caption: Integrity check of the raw Kaggle files
source: Author's own check of the downloaded files (outputs/data_check/raw_data_check.md).
:::

## Rossmann sample

{tbl:stores} lists the 20 sampled stores. The sample was drawn from the 850 eligible stores in proportion to the store type and assortment strata, with at least two stores per stratum and a fixed seed of 2026.

::: table id=tbl:stores csv=outputs/tables/report_rossmann_stores.csv size=8.5 widths=2.2,2.6,2.6,4.0,2.2
caption: Sampled Rossmann stores and their attributes
source: Author's own sample from the Rossmann store file [@kaggle2015rossmann].
:::

# Appendix C: Literature Matrix {#app:C .appendix letter=C}

{tbl:litmatrix} lists the 47 journal articles that met the inclusion criteria of {sec:reviewmethod}, with their focus and the sections of this report in which they are cited.

::: table id=tbl:litmatrix csv=outputs/tables/report_literature_matrix.csv size=7.5 widths=3.6,4.0,6.0,2.0
caption: Literature matrix of the reviewed articles
source: Author's own synthesis.
:::

# Appendix D: Model Specifications and Extended Results {#app:D .appendix letter=D}

## Statistical models

{tbl:specsm5} and {tbl:specsross} list the ARIMA and ETS specifications selected for each series on the tuning-stage training period.

::: table id=tbl:specsm5 csv=outputs/tables/report_stat_specs_m5.csv size=8.5
caption: Selected statistical models for the M5 stores
source: Author's own results (outputs/metrics/m5_statistical_specs.json).
:::

::: table id=tbl:specsross csv=outputs/tables/report_stat_specs_rossmann.csv size=8.5
caption: Selected statistical models for the Rossmann stores
source: Author's own results (outputs/metrics/rossmann_statistical_specs.json).
:::

## Neural networks

{tbl:bestparams} lists the hyperparameters selected by the tuning stage and the corresponding validation MASE.

::: table id=tbl:bestparams csv=outputs/tables/report_best_params.csv size=8
caption: Selected hyperparameters of the neural and hybrid models
source: Author's own results (outputs/metrics/*_best_params.json). Trials: completed tuning trials; trials interrupted by a stopped process, marked as failed and excluded, in brackets.
:::

## Extended results {#sec:appextended}

### M5

{tbl:m5summary} gives the full test summary, {tbl:m5intervals} the interval results, {tbl:m5week} the error by forecast week, {tbl:m5dm} the primary Diebold-Mariano tests, {tbl:m5dmmat} the secondary test statistics as a matrix and {tbl:m5resid} the residual diagnostics (Ljung-Box tests at lags 7 and 14 and the BDS test with embedding dimension 2, applied to the one-step ARIMA residuals). {fig:m5seed} shows the stability across seeds, {fig:m5covh} the coverage by horizon, {fig:m5growth} the growth of error with horizon, {fig:m5store} the error by store and {fig:m5tune} the tuning results.

::: table id=tbl:m5summary csv=outputs/tables/report_test_summary_m5.csv size=8
caption: M5: test summary by model
source: Author's own calculation, generated by make_report_tables.py from the test forecasts.
:::

::: table id=tbl:m5intervals csv=outputs/tables/report_intervals_m5.csv size=8
caption: M5: prediction interval results by model
source: Author's own calculation, generated by make_report_tables.py from the test forecasts.
:::

::: table id=tbl:m5week csv=outputs/tables/report_mase_by_week_m5.csv size=8
caption: M5: mean absolute scaled error (MASE) by forecast week
source: Author's own calculation, generated by make_report_tables.py from the test forecasts.
:::

::: table id=tbl:m5dm csv=outputs/tables/report_dm_m5.csv size=8
caption: M5: Diebold-Mariano tests of the primary hybrid (recursive) against the seven other models
source: Author's own calculation, generated by make_report_tables.py from the test forecasts.
:::

::: table id=tbl:m5dmmat csv=outputs/tables/report_dm_matrix_m5.csv size=8
caption: M5: Diebold-Mariano test statistics as a matrix (secondary, exploratory; Holm over 28 pairs)
source: Author's own calculation, generated by make_report_tables.py from the test forecasts.
:::

::: table id=tbl:m5resid csv=outputs/tables/report_residual_diagnostics_m5.csv size=8
caption: M5: residual diagnostics of the statistical models
source: Author's own calculation, generated by make_report_tables.py from the test forecasts.
:::

::: figure id=fig:m5seed file=outputs/figures/res_m5_seed_stability.png width=15 generator=scripts/run_evaluation.py
caption: M5: accuracy across training seeds
source: Author's own work, generated by run_evaluation.py from the test forecasts.
alt: Plot of mean absolute scaled error (MASE, vertical axis) for each of the five training seeds, one series per neural model, M5 test period.
:::

::: figure id=fig:m5covh file=outputs/figures/res_m5_coverage_by_horizon.png width=15 generator=scripts/run_evaluation.py
caption: M5: interval coverage by forecast horizon
source: Author's own work, generated by run_evaluation.py from the test forecasts.
alt: Line chart of empirical interval coverage (vertical axis) against forecast horizon in days (horizontal axis), one line per model, M5 test period.
:::

::: figure id=fig:m5growth file=outputs/figures/res_m5_error_growth.png width=15 generator=scripts/run_evaluation.py
caption: M5: growth of error with forecast horizon
source: Author's own work, generated by run_evaluation.py from the test forecasts.
alt: Line chart of error (vertical axis) against forecast horizon in days (horizontal axis), one line per model, M5 test period.
:::

::: figure id=fig:m5store file=outputs/figures/res_m5_mase_by_store.png width=15 generator=scripts/run_evaluation.py
caption: M5: mean absolute scaled error (MASE) by store
source: Author's own work, generated by run_evaluation.py from the test forecasts.
alt: Chart of mean absolute scaled error (MASE, vertical axis) for each store (horizontal axis), one series per model, M5 test period.
:::

::: figure id=fig:m5tune file=outputs/figures/res_m5_tuning.png width=15 generator=scripts/run_evaluation.py
caption: M5: tuning results
source: Author's own work, generated by run_evaluation.py from the test forecasts.
alt: Chart of validation error for the hyperparameter settings tried in the tuning stage, M5.
:::

### Rossmann

{tbl:rmsummary} gives the full test summary, {tbl:rmintervals} the interval results, {tbl:rmweek} the error by forecast week, {tbl:rmdm} the primary Diebold-Mariano tests, {tbl:rmdmmat} the secondary test statistics as a matrix and {tbl:rmresid} the residual diagnostics. {fig:rmseed} shows the stability across seeds, {fig:rmcovh} the coverage by horizon, {fig:rmgrowth} the growth of error with horizon, {fig:rmstore} the error by store and {fig:rmtune} the tuning results.

::: table id=tbl:rmsummary csv=outputs/tables/report_test_summary_rossmann.csv size=8
caption: Rossmann: test summary by model
source: Author's own calculation, generated by make_report_tables.py from the test forecasts.
:::

::: table id=tbl:rmintervals csv=outputs/tables/report_intervals_rossmann.csv size=8
caption: Rossmann: prediction interval results by model
source: Author's own calculation, generated by make_report_tables.py from the test forecasts.
:::

::: table id=tbl:rmweek csv=outputs/tables/report_mase_by_week_rossmann.csv size=8
caption: Rossmann: mean absolute scaled error (MASE) by forecast week
source: Author's own calculation, generated by make_report_tables.py from the test forecasts.
:::

::: table id=tbl:rmdm csv=outputs/tables/report_dm_rossmann.csv size=8
caption: Rossmann: Diebold-Mariano tests of the primary hybrid (multi-step errors) against the seven other models
source: Author's own calculation, generated by make_report_tables.py from the test forecasts.
:::

::: table id=tbl:rmdmmat csv=outputs/tables/report_dm_matrix_rossmann.csv size=8
caption: Rossmann: Diebold-Mariano test statistics as a matrix (secondary, exploratory; Holm over 28 pairs)
source: Author's own calculation, generated by make_report_tables.py from the test forecasts.
:::

::: table id=tbl:rmresid csv=outputs/tables/report_residual_diagnostics_rossmann.csv size=8
caption: Rossmann: residual diagnostics of the statistical models
source: Author's own calculation, generated by make_report_tables.py from the test forecasts.
:::

::: figure id=fig:rmseed file=outputs/figures/res_rossmann_seed_stability.png width=15 generator=scripts/run_evaluation.py
caption: Rossmann: accuracy across training seeds
source: Author's own work, generated by run_evaluation.py from the test forecasts.
alt: Plot of mean absolute scaled error (MASE, vertical axis) for each of the five training seeds, one series per neural model, Rossmann test period.
:::

::: figure id=fig:rmcovh file=outputs/figures/res_rossmann_coverage_by_horizon.png width=15 generator=scripts/run_evaluation.py
caption: Rossmann: interval coverage by forecast horizon
source: Author's own work, generated by run_evaluation.py from the test forecasts.
alt: Line chart of empirical interval coverage (vertical axis) against forecast horizon in days (horizontal axis), one line per model, Rossmann test period.
:::

::: figure id=fig:rmgrowth file=outputs/figures/res_rossmann_error_growth.png width=15 generator=scripts/run_evaluation.py
caption: Rossmann: growth of error with forecast horizon
source: Author's own work, generated by run_evaluation.py from the test forecasts.
alt: Line chart of error (vertical axis) against forecast horizon in days (horizontal axis), one line per model, Rossmann test period.
:::

::: figure id=fig:rmstore file=outputs/figures/res_rossmann_mase_by_store.png width=15 generator=scripts/run_evaluation.py
caption: Rossmann: mean absolute scaled error (MASE) by store
source: Author's own work, generated by run_evaluation.py from the test forecasts.
alt: Chart of mean absolute scaled error (MASE, vertical axis) for each store (horizontal axis), one series per model, Rossmann test period.
:::

::: figure id=fig:rmtune file=outputs/figures/res_rossmann_tuning.png width=15 generator=scripts/run_evaluation.py
caption: Rossmann: tuning results
source: Author's own work, generated by run_evaluation.py from the test forecasts.
alt: Chart of validation error for the hyperparameter settings tried in the tuning stage, Rossmann.
:::


## Secondary analysis: all pairs and hybrid components {#sec:appsecondary}

These analyses were added after the primary analysis of {sec:development} was fixed, and they are exploratory. The matrices adjust the p-values over all 28 pairs of models for each seed, with squared loss, and show the mean statistic and the median adjusted p-value over seeds. Because the family is larger than the seven comparisons of the primary analysis, p-values near 0.05 can differ between the two. The ablation tables compare each hybrid variant with ARIMA and the LSTM in the same 28-pair family. The test statistics are also given as tables ({tbl:m5dmmat}, {tbl:rmdmmat}).

::: figure id=fig:m5dm file=outputs/figures/res_m5_dm_matrix.png width=15 generator=scripts/run_evaluation.py
caption: M5: pairwise Diebold-Mariano test results between models (secondary, exploratory; Holm over 28 pairs)
source: Author's own work, generated by run_evaluation.py from the test forecasts.
alt: Matrix with one row and one column per model, each cell showing the outcome of the Diebold-Mariano test for that pair, for the M5 test period.
:::

::: figure id=fig:rmdm file=outputs/figures/res_rossmann_dm_matrix.png width=15 generator=scripts/run_evaluation.py
caption: Rossmann: pairwise Diebold-Mariano test results between models (secondary, exploratory; Holm over 28 pairs)
source: Author's own work, generated by run_evaluation.py from the test forecasts.
alt: Matrix with one row and one column per model, each cell showing the outcome of the Diebold-Mariano test for that pair, for the Rossmann test period.
:::

::: table id=tbl:m5ablation csv=outputs/tables/report_hybrid_ablation_m5.csv size=8
caption: M5: hybrid variants compared with their component models (secondary, exploratory; Holm over 28 pairs)
source: Author's own calculation, generated by make_report_tables.py from the test forecasts.
:::

::: table id=tbl:rmablation csv=outputs/tables/report_hybrid_ablation_rossmann.csv size=8
caption: Rossmann: hybrid variants compared with their component models (secondary, exploratory; Holm over 28 pairs)
source: Author's own calculation, generated by make_report_tables.py from the test forecasts.
:::

# Appendix E: Test Plan and Results {#app:E .appendix letter=E}

## Automated tests

The final run had 71 automated tests, and all passed. {tbl:unittests} lists every test with its result.

::: table id=tbl:unittests csv=outputs/tables/report_unit_tests.csv size=8 widths=3.6,9.0,1.6,1.4
caption: Automated tests and results
source: Author's own test run (pytest).
:::

## Dashboard functional tests

{tbl:dashtests} is the functional test plan for the dashboard. The expected values are computed in Python and stored with the exported data, so that the dashboard measures can be checked against the figures in this report. The dashboard has been built. The last column of {tbl:dashtests} gives the status of each test. A check marked "screenshot" compares a value on the exported pages ({sec:appbuilt}) with the acceptance value; it was not a DAX query, because no live connection to the report was available. All other tests are to be run by the author.

::: table id=tbl:dashtests widths=1.2,2.6,3.8,4.0,4.4 size=7.5
caption: Functional test plan for the dashboard
source: Author's own work (dashboard/README.md).
| ID | Test | Steps | Expected result | Status |
|---|---|---|---|---|
| TP-01 | Data load | Refresh all queries | Six tables load without errors; row counts equal those printed by the export | To be run by the author |
| TP-02 | Relationships | Open the model view | Seven many-to-one, single-direction relationships | To be run by the author |
| TP-03 | Sort orders | Show weekday and month | Monday to Sunday; January to December | To be run by the author |
| TP-04 | Dataset slicer | Select M5, then Rossmann | Every visual changes; stores of one dataset never appear under the other | To be run by the author |
| TP-05 | Store slicer | Select one store | Page 1 shows that store only | To be run by the author |
| TP-06 | Model and origin slicers | Select one model and one origin | Page 1 shows 28 days from that origin | To be run by the author |
| TP-07 | Actual sales measure | One dataset and model, all stores and origins | Equals the acceptance value for total actual sales | To be run by the author |
| TP-08 | Forecast sales measure | As TP-07 | Equals the acceptance value for total forecast | To be run by the author |
| TP-09 | MAE measure | As TP-07 | Equals the acceptance value for mean absolute error | To be run by the author |
| TP-10 | Coverage measure | As TP-07 | Equals the acceptance value for interval coverage | Screenshot: six of eight models match (94.0, 92.6, 93.6, 92.8, 90.3 and 93.6%); the other two were not visible |
| TP-11 | Mean absolute scaled error (MASE) measure | As TP-07 | Store-average MASE equals the acceptance value | Screenshot: seven of eight models match (all but the LSTM, which was not visible) |
| TP-12 | Best model card | Clear the model slicer | Shows the model with the lowest MASE | Screenshot: Hybrid-Z, MASE 0.746, the lowest; matches |
| TP-13 | Planning cards | One store and one origin | Safety stock proxy equals upper bound minus forecast over the 28 days; stock-out and overstock risk days equal their acceptance values | Not reconciled: with all models selected, the cards (forecast sales 70,733,426; 1,044.7 and 261.7 risk days) equal neither the sum nor the mean of the eight models' acceptance values. To be re-run with one model |
| TP-14 | Accessibility | Checklist in {tbl:a11y} | All checks pass | Partly; see {tbl:a11y} |
| TP-15 | Drill-down | Drill from a week (week start date) to its days and back | Daily values sum to the weekly value | To be run by the author |
| TP-16 | Static review of measures | Compare each DAX measure with its Python definition | Same scored-day filter and formula | To be run by the author |
:::

# Appendix F: Dashboard Specification {#app:F .appendix letter=F}

## Pages

The dashboard has three pages that share slicers for dataset, store, model and forecast origin. {fig:wireforecast}, {fig:wiremodels} and {fig:wireplanning} are design wireframes of the pages; they are drawings of the specification, not screenshots. The built pages are in {sec:appbuilt}.

::: figure id=fig:wireforecast file=outputs/figures/dash_wireframe_forecast.png width=15
caption: Design wireframe of the forecast page
source: Author's own design.
alt: Wireframe with four slicers at the top, a large line chart of actual and forecast sales with a 95% band, two cards for mean absolute scaled error (MASE) and interval coverage, a column chart of error by horizon and a detail table.
:::

::: figure id=fig:wiremodels file=outputs/figures/dash_wireframe_models.png width=15
caption: Design wireframe of the model comparison page
source: Author's own design.
alt: Wireframe with a bar chart of mean absolute scaled error (MASE) by model, a line chart of error by horizon for each model, a matrix of MASE by store and model, a best-model card and a bar chart of interval coverage by model.
:::

::: figure id=fig:wireplanning file=outputs/figures/dash_wireframe_planning.png width=15
caption: Design wireframe of the planning page
source: Author's own design.
alt: Wireframe with four cards for forecast sales, safety stock proxy, stock-out risk days and overstock risk days, a weekly column chart of forecast and upper bound, and a bar chart of bias by store.
:::

## Built dashboard {#sec:appbuilt}

{fig:builtforecast}, {fig:builtmodels} and {fig:builtplanning} are screenshots of the three pages of the built Power BI report (M5, all stores, all models, all origins). They are the author's PDF export of the report; the wireframes above remain the design.

::: figure id=fig:builtforecast file=outputs/figures/dash_built_forecast.png width=15
caption: Built dashboard: forecast page
source: Author's own work (Power BI Desktop screenshot).
alt: Screenshot of the forecast page with four slicers, a line chart of daily actual and forecast sales with a dotted 95% interval, cards for mean absolute scaled error (MASE), interval coverage, mean absolute error and bias, a column chart of error by days ahead and a table of daily detail.
:::

::: figure id=fig:builtmodels file=outputs/figures/dash_built_models.png width=15
caption: Built dashboard: model comparison page
source: Author's own work (Power BI Desktop screenshot).
alt: Screenshot of the model comparison page with a best-model card, four metric buttons, a bar chart of store-average MASE by model, interval coverage by model, a line chart of MASE by days ahead and a table of MASE by store and model.
:::

::: figure id=fig:builtplanning file=outputs/figures/dash_built_planning.png width=15
caption: Built dashboard: planning page
source: Author's own work (Power BI Desktop screenshot).
alt: Screenshot of the planning page with cards for forecast sales, safety stock proxy, stock-out risk days and overstock risk days, a weekly chart of forecast and upper bound, a bar chart of bias by store and a table of stores by stock-out risk.
:::

Differences between the built pages and the design, from a comparison of the screenshots with the wireframes:

- Forecast page: two further cards (mean absolute error and bias) and, in the detail table, the horizon and an inside-the-interval flag. The slicer is labelled "Forecast origin (number)".
- Model page: a metric switch (MASE, RMSE, MAE, MAPE) was added. Models are labelled Hybrid-D, Hybrid-MS and Hybrid-Z, whereas the report calls them the direct, multi-step errors and recursive hybrids.
- Planning page: a table of stores by stock-out risk was added. With all models selected, the risk-day counts are fractional, because they are averaged over seeds.
- All pages: the footer text is shown inside quotation marks.
- With no model selected, the cards show values for all models together, which have no counterpart in the acceptance values; a single model should be selected when checking them.

The export script wrote three dimension tables (1,941 dates, 30 series and eight models) and three fact tables (38,250 actuals, 62,720 forecast rows and 240 metric rows), and acceptance values for every dataset and model. The export uses seed 1 for the networks, so its network MASE values differ slightly from the five-seed means (for example, 0.881 against 0.864 for the M5 FFNN).

## Design decisions {#sec:appdesign}

The dashboard was designed for accessibility and for safe reading of the numbers. The points below are design decisions; the checks that have recorded results are in {tbl:a11y}.

- **Palette.** The report theme uses dark blue (#1F4E79), green (#548235), orange (#C55A11) and purple (#7030A0) as the main colours, with grey for the other series. It is not the Okabe-Ito palette. Whether it is distinguishable under colour-vision deficiencies has not yet been checked (A2).
- **Redundant encoding.** Models are designed to differ by line style and marker as well as colour; cards carry a coloured bar and a text label; the best model and the others are distinguished by colour and by order.
- **Contrast.** Body text is dark grey or black on white or light grey (7.9:1 to 17.7:1 in the theme). The orange and green card labels are large bold text, designed for the 3:1 threshold for large text, not 4.5:1 (A1).
- **Font sizes.** The theme sets 10 points for labels, 12 for headers and 14 for titles. Some notes and subtitles in the report file are set at 8 and 9 points, below the specification (A7).
- **Alt text and tab order.** Every visual in the report file has alt text and an explicit tab-order value (A4, A5).
- **Single-dataset guard.** M5 sales are units and Rossmann sales are turnover in euros, so measures that sum sales return blank unless one dataset is selected, to prevent the two being mixed.
- **Dynamic titles.** Titles and subtitles name the selection and the units.
- **Field parameter.** The metric switch on the model page is designed as a field parameter, so that one chart serves four measures.
- **Reference lines.** The coverage chart is designed with a reference line at 95%, and the MASE card shows the seasonal naive value as a benchmark.
- **Drill-down.** The weekly chart is designed to drill from week to day.

## Measures

The main Data Analysis Expressions (DAX) measures are listed below. Every measure is restricted to scored days, as in the Python evaluation. Measures that sum sales return a blank unless exactly one dataset is selected, because M5 sales are units and Rossmann sales are turnover. The report's MASE is the mean of the per-store values, which the measure "MASE (store average)" reproduces.

```
Actual Sales (scored) =
IF ( HASONEVALUE ( dim_series[dataset] ),
    CALCULATE ( SUM ( fact_forecast[actual] ), fact_forecast[scored] = 1 ) )

Forecast Sales (scored) =
IF ( HASONEVALUE ( dim_series[dataset] ),
    CALCULATE ( SUM ( fact_forecast[forecast] ), fact_forecast[scored] = 1 ) )

Forecast Upper 95% (scored) =
IF ( HASONEVALUE ( dim_series[dataset] ),
    CALCULATE ( SUM ( fact_forecast[upper] ), fact_forecast[scored] = 1 ) )

MASE (store average) =
AVERAGE ( fact_metrics[mase] )

Interval Coverage % =
AVERAGEX ( FILTER ( fact_forecast, fact_forecast[scored] = 1 ),
    IF ( fact_forecast[actual] >= fact_forecast[lower]
         && fact_forecast[actual] <= fact_forecast[upper], 1, 0 ) )

Safety Stock Proxy =
[Forecast Upper 95% (scored)] - [Forecast Sales (scored)]

Overstock Risk Days =
COUNTROWS ( FILTER ( fact_forecast,
    fact_forecast[scored] = 1 && fact_forecast[actual] < fact_forecast[lower] ) )
```

The complete set of measures, including the lower bound, the stock-out count and the pooled error measures, is in the dashboard folder of the repository with the Power Query scripts and the build steps.

## Accessibility checklist

::: table id=tbl:a11y widths=1.0,4.6,4.4,5.6 size=8
caption: Accessibility checklist for the dashboard
source: Author's own work, based on @choiseo2024 and @nelli2024.
| # | Check | How it is verified | Result |
|---|---|---|---|
| A1 | Text contrast at least 4.5:1 against the background | Theme colours checked in a contrast checker | Partly (static check of the report file): dark text 7.9:1 to 17.7:1; orange and green card labels 3.9:1 to 4.5:1 (large bold text) |
| A2 | Every chart readable in greyscale | Greyscale export or a colour-vision simulator | To be run by the author |
| A3 | No information carried by colour alone | Models differ by line style or marker as well as colour | To be run by the author |
| A4 | Alternative text on every visual | Format pane of each visual | Pass (static check of the report file): 77 of 77 visuals have alt text |
| A5 | Logical keyboard tab order | Tab through each page | Tab-order values are set for 77 of 77 visuals; the order was not walked through; to be run by the author |
| A6 | All slicers usable with the keyboard | Operate each slicer with Tab, arrow keys and Enter | To be run by the author |
| A7 | Minimum font sizes of 12 points for text and 10 points for axis labels | Visual formatting | Not met (static check of the report file): 8 and 9 points are used in 30 settings |
| A8 | Report usable with a high-contrast theme | Reopen the report under a high-contrast theme | To be run by the author |
:::

# Appendix G: User Study Materials {#app:G .appendix letter=G}

**Status: ethical approval granted; study not yet conducted. No participant data exist, and no usability results are reported.**

## Protocol

The proposal set out the design of the study, and ethical approval for a study involving participants has been granted. The commitments below are taken from the proposal. The tasks and interview questions are the instruments prepared for the study.

[[PENDING: align the tasks, questions and data-handling details with the protocol approved by the Arden Research Ethics Committee.]]

- **Participants:** a small purposive sample of three to five people with experience in retail or supply-chain analytics, recruited from professional networks.
- **Procedure:** each participant completes short structured tasks on the dashboard, then the System Usability Scale (SUS) questionnaire and a brief semi-structured interview.
- **Tasks:**
  1. Find the forecast for a named store for the next four weeks and read the expected sales for the first week.
  2. State whether actual sales stayed within the 95% range in a named week.
  3. Identify which model was most accurate for a named store.
  4. Read the safety stock proxy and explain in your own words what it means.
  5. Find the store with the largest over-forecasting bias.
- **Measures:** task completion, errors, the SUS score (target 80 or more, interpreted as excellent usability [@hammad2026]) and interview themes.
- **Interview questions:**
  1. Which information on the dashboard would you use in your work, and for which decision?
  2. Was anything unclear or misleading?
  3. How far would you trust these forecasts, and what would increase your trust?
  4. What is missing?

## System Usability Scale

The ten items below are the standard System Usability Scale [@brooke1996]. Participants rate each statement from 1 (strongly disagree) to 5 (strongly agree). Odd-numbered items score the rating minus one; even-numbered items score five minus the rating; the sum is multiplied by 2.5 to give a score from 0 to 100.

1. I think that I would like to use this system frequently.
2. I found the system unnecessarily complex.
3. I thought the system was easy to use.
4. I think that I would need the support of a technical person to be able to use this system.
5. I found the various functions in this system were well integrated.
6. I thought there was too much inconsistency in this system.
7. I would imagine that most people would learn to use this system very quickly.
8. I found the system very cumbersome to use.
9. I felt very confident using the system.
10. I needed to learn a lot of things before I could get going with this system.


## Consent and data handling

As stated in the proposal, participants provide written informed consent. Interview notes and questionnaire responses are pseudonymised at the point of capture, stored separately from the consent forms on Arden-approved storage, and deleted six months after submission in line with the Arden ethics policy. Only aggregated results will be reported.

# Appendix H: Project Plan and Increments {#app:H .appendix letter=H}

[[PENDING: project plan table to be completed from the decisions and experiment logs]]

# Appendix I: Repository and Reproduction Guide {#app:I .appendix letter=I}

## Structure

The repository contains the code, tests, documentation and generated outputs of the project. The raw Kaggle files are not included. {tbl:repo} describes the main folders.

::: table id=tbl:repo widths=3.6,12.0 size=8.5
caption: Main folders of the repository
source: Author's own work.
| Folder or file | Content |
|---|---|
| src | Python package: data loading, preprocessing, models, hybrids, evaluation, tests of predictive accuracy, dashboard export |
| scripts | One command-line script per stage, the experiment queue, the report-table generator, summarise_results.py (writes result_facts.json, the figures quoted in the results), the pausable runner run_chunks.py, and the helpers retime_arima.py and clean_optuna.py (re-timing of an ARIMA search; marking interrupted Optuna trials as failed) |
| scripts/literature | Search, verification and library-export scripts of the literature protocol |
| tests | Automated tests, including the leakage tests |
| notebooks | Nine executed notebooks that walk through the outputs of each stage |
| dashboard | Data dictionary, Power Query scripts, DAX measures, build guide and test plan |
| docbuild | Builder of this report from Markdown chapters in the university template |
| data | Download instructions and reference checksums of the Kaggle files |
| outputs | Forecasts, metrics, tables, figures and logs written by the pipeline |
| DECISIONS_LOG.md | Design decisions with alternatives and justifications |
| EXPERIMENT_LOG.csv | One row per tuning trial and final run, with parameters, seed, runtime, energy estimate and metrics |
:::

## Reproduction

The results can be reproduced with Python 3.13 and the package versions pinned in the repository. The steps are:

1. Create a virtual environment and install the pinned requirements.
2. Download the two Kaggle datasets, place them as described in the data folder and confirm their checksums with the data-check script.
3. Run the stages in order: exploratory analysis, statistical models, neural and hybrid models, evaluation, dashboard export and report tables. Each stage checkpoints its progress and can be restarted after an interruption.
4. Run the automated tests.

The networks were trained on a central processing unit only, with deterministic operations and fixed seeds. Results on other hardware or library versions may differ slightly in the last digits, because floating-point operations are not guaranteed to be identical across platforms.
