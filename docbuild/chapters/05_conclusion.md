# Conclusion {#sec:conclusion}

## Summary of Findings {#sec:findings}

[[PENDING: summary of the main findings, written from the final evaluation outputs.]]

## Achievement of the Objectives {#sec:objachieved}

{tbl:objectives} assesses each objective of {sec:objectives} against the evidence in this report.

::: table id=tbl:objectives widths=1.4,6.2,1.9,6.1 size=8.5
caption: Achievement of the project objectives
source: Author's own assessment.
| # | Objective (abridged) | Status | Evidence |
|---|---|---|---|
| 1 | Structured literature review of statistical, machine learning and hybrid methods for retail | Met, with a smaller source base than planned | {sec:factfinding}: 47 verified articles from 2023 to 2026, comparison of 12 hybrid studies, requirements |
| 2 | Prepare and explore a public retail dataset: missing values, seasonality, features | Met and extended to two datasets | {sec:data} and {sec:prep}: integrity check, closures, anomaly rule, covariates, splits |
| 3 | Implement and benchmark ARIMA, ETS, a feed-forward network and an LSTM with RMSE, MAPE and MASE | [[PENDING: status]] | [[PENDING: evidence]] |
| 4 | Develop and tune a hybrid ARIMA-LSTM and compare it with the Diebold-Mariano test | [[PENDING: status]] | [[PENDING: evidence]] |
| 5 | Deploy the best model in a Power BI dashboard and evaluate its usability with at least three users | Partly met | {sec:dashboard}: data model, measures, specification and test plan; the dashboard file and the user study are outstanding |
:::

## Contribution {#sec:contributionfinal}

[[PENDING: contribution paragraph written from the final results.]]

## Recommendations for Practice {#sec:recommendations}

[[PENDING: recommendations written from the final results.]]

## Further Work {#sec:futurework}

Several extensions follow directly from the limitations in {sec:limitations}:

- **User evaluation.** The approved user study should be run with practitioners to test whether the dashboard supports ordering and planning decisions, using the protocol in {app:G}.
- **Re-estimation and retraining.** The models could be re-estimated at each origin or at a fixed interval, to measure how much accuracy is gained for how much extra computation [@zanotti2026].
- **Hierarchical and item-level forecasting.** Store forecasts could be reconciled with category and item forecasts, so that orders and revenue plans are consistent at every level.
- **Richer information.** Prices, weather and local events could be added where they are known in advance, and the network inputs could be extended accordingly.
- **Better intervals.** Conformal methods designed for multi-step time series, with weighted or adaptive calibration, could replace the split conformal intervals [@schlembach2025].
- **Measured energy.** Energy could be measured with a software meter rather than estimated from rated power [@scala2025].

## Entrepreneurial Potential {#sec:entrepreneurial}

The artefact addresses a need common to small and medium-sized retailers: they hold sales data but rarely have the data science capacity to produce reliable multi-week forecasts with an honest range. Three features make it a plausible basis for a product or consultancy service. It runs on ordinary laptop hardware without a graphics processor. It reports uncertainty and bias in terms that a store manager can act on. Its tests and documentation make it auditable, which matters to clients who must trust the numbers before changing their ordering [@groene2024]. A service could take a retailer's sales history, run the benchmark, recommend the simplest model that performs well, and deliver the forecasts through a dashboard. Any such service would need the user evaluation described above, a data-protection assessment for each client and a clear statement that forecasts support rather than replace the planner's decision [@cheong2024].
