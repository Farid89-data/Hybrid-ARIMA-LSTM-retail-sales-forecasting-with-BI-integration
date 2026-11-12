# Conclusion {#sec:conclusion}

## Summary of Findings {#sec:findings}

The project compared a hybrid ARIMA-LSTM with four single models and a seasonal naive benchmark on daily store sales from two public datasets. Four findings stand out.

- **A hybrid was the most accurate model on both datasets, but not the same one.** The recursive hybrid reduced MASE by 11.0% relative to ARIMA on M5 (0.746 against 0.838). The multi-step hybrid reduced it by 10.8% on Rossmann (0.320 against 0.359).
- **The gain was robust on M5 only.** There the hybrid beat all seven alternatives in every seed and under both losses. On Rossmann it beat ARIMA in three of five seeds and could not be distinguished from the FFNN (MASE 0.328) or the LSTM.
- **The residual design matters.** The multi-step hybrid was the best variant on Rossmann but slightly worse than ARIMA on M5. Validation picked the right variant on both datasets.
- **Intervals and cost qualify the gain.** Conformal coverage ranged from 90.3% to 96.3% but fell well below 95% at some horizons. ARIMA's model search dominated the cost, so the hybrids were the most expensive models.

## Achievement of the Objectives {#sec:objachieved}

{tbl:objectives} assesses each objective of {sec:objectives} against the evidence in this report.

::: table id=tbl:objectives widths=1.4,6.2,1.9,6.1 size=8.5
caption: Achievement of the project objectives
source: Author's own assessment.
| # | Objective (abridged) | Status | Evidence |
|---|---|---|---|
| 1 | Structured literature review of statistical, machine learning and hybrid methods for retail | Met, with a smaller source base than planned | {sec:factfinding}: 47 verified articles from 2023 to 2026, comparison of 12 hybrid studies, requirements |
| 2 | Prepare and explore a public retail dataset: missing values, seasonality, features | Met and extended to two datasets | {sec:data} and {sec:prep}: integrity check, closures, anomaly rule, covariates, splits |
| 3 | Implement and benchmark ARIMA, ETS, a feed-forward network and an LSTM with RMSE, MAPE and MASE | Met | {sec:resaccuracy}, {tbl:crossdataset}: all models on both test periods, five seeds per network; best single model ARIMA on M5 (MASE 0.838) and the FFNN on Rossmann (0.328) |
| 4 | Develop and tune a hybrid ARIMA-LSTM and compare it with the Diebold-Mariano test | Met | {sec:ressignificance}: three variants tuned and tested with Holm-adjusted DM tests; the M5 hybrid significantly better than all seven alternatives in all five seeds; on Rossmann robust only against seasonal naive and ETS |
| 5 | Deploy the best model in a Power BI dashboard and evaluate its usability with at least three users | Partly met | {sec:dashboard}: data model, measures, specification and test plan; the dashboard file and the user study are outstanding |
:::

## Contribution {#sec:contributionfinal}

The contribution is a transparent, tested comparison rather than a new model. On two public datasets, with leakage tests and significance tests repeated across seeds, it shows that the gain of an ARIMA-LSTM hybrid is real but conditional. It depends on the dataset and on a design choice that earlier studies leave implicit: which residuals the network learns ({sec:hybridlit}). The best design differed between the datasets, and one design was no better than ARIMA. Only one of the twelve reviewed hybrid studies used a test designed for comparing forecasts; this project applies such a test to every comparison and reports interval calibration and cost alongside accuracy. The code, tests and star-schema export form an artefact that can be re-run on the public data.

## Recommendations for Practice {#sec:recommendations}

- **Start with strong simple models.** ARIMA with known regressors and a small feed-forward network were the best single models, and on Rossmann the network was not significantly worse than the best hybrid.
- **Validate the hybrid on the retailer's own data.** The best residual design differed between the datasets, and validation selected it correctly on both.
- **Use the information that drives demand.** On Rossmann, the two methods without promotion information had about twice the error of the others.
- **Treat the 95% band as approximate.** Coverage dropped in the third week, so it should be monitored by horizon after deployment.
- **Weigh accuracy against cost.** ARIMA's order search dominated computation. Where the hybrid's gain is small, the cheaper network is the better choice.

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
