# Fact Finding {#sec:factfinding}

## Review Approach {#sec:reviewmethod}

The review is a narrative and integrative review with a documented search. It is not a systematic review. The proposal intended Google Scholar as the discovery tool, but automated querying of Google Scholar was not available in the development environment. With the agreement of the project owner, discovery therefore used the scholarly metadata services OpenAlex and Crossref. Queries were organised into twelve themes, from retail demand forecasting to the ethics and energy cost of deep learning, and restricted to publications dated 2023 to 2026.

A source was included only if it met all of the following conditions:

- it is a peer-reviewed journal article;
- its journal states, on the publisher's website, that it is indexed in Scopus, and in most cases also in Web of Science;
- its metadata matched the Crossref record of its digital object identifier (DOI), with no retraction or correction notice;
- its full text could be read on the publisher's website.

The last condition introduced a bias that must be acknowledged. Several publishers refuse automated page requests, so relevant articles in their journals could not be read and were excluded, and the final set leans towards open-access publishers. Forty-seven articles met all conditions. Each was read in full, and the passages that support claims in this report were logged with the section in which they appear. The year of publication was taken as the year of the journal issue, or the year of online publication when no issue had been assigned.

## Retail Demand Forecasting as a Decision Problem {#sec:retail}

Retail forecasting is valuable because of the decisions it enables, not because of accuracy in the abstract. Interviews with twelve German grocery retailers identified 21 options for preventing and reducing food surplus. Demand forecasting and automated ordering were among the preventive options, but implementation for perishables remained limited by data quality and by staff resistance to algorithmic recommendations [@winkler2023]. In food and beverage outlets, forecasts supported purchasing, shift planning and liquidity management, and adoption depended on managers trusting that the model used information they recognised [@groene2024]. @alsaif2026 linked forecast errors to an explicit periodic-review inventory policy. On two Kaggle retail datasets, including Rossmann, a gradient-boosting model gave both the lowest error and the lowest inventory cost. Forecast bias propagated to holding and shortage costs, and the study concluded that "architectural complexity without careful bias control can harm supply chain performance".

Retail sales also have features that complicate modelling. Weekly cycles are strong, but floating holidays and shopping events such as Black Friday create irregular seasonal patterns. In weekly US sales of Sony televisions, Black Friday weeks alone accounted for 5% to 10% of annual sales [@yamashita2026]. Promotions change both demand and its consequences: a field experiment in eight Swedish supermarkets found that multi-unit offers raised quantities purchased by 19.5% and increased household food waste [@gravert2025]. Sales data may also contain structural breaks and administrative artefacts. In Brazilian fashion e-commerce, COVID-19 restrictions changed the relationship between full-price and discounted sales, and a weekly invoicing practice created an artificial Monday peak [@padilha2025]. A forecasting framework for retail therefore has to handle calendar effects, promotions, closures and occasional anomalies explicitly, rather than treating them as noise.

The M5 dataset has become a common test bed for this domain. @zanotti2026 compared ten global models on its 30,490 daily product series. Ensembles raised the computational cost substantially, and the study recommended that they "should be kept small and strategically designed". Reducing the retraining frequency cut computing time by about a third with "minimal impact on accuracy". This finding is relevant to the design of this project, which keeps model parameters fixed between forecast origins.

## Statistical Forecasting: ARIMA and Exponential Smoothing {#sec:statlit}

ARIMA models represent a series through autoregressive and moving-average terms after differencing, and seasonal ARIMA adds the same structure at the seasonal lag. Exponential smoothing represents the level, trend and seasonal components as weighted averages updated over time. Both are linear in their parameters, estimated by maximum likelihood and interpretable to analysts. Recent comparisons show that they remain competitive. In quarterly maternal mortality data, Holt-Winters exponential smoothing and ARIMA agreed better with out-of-sample data than a neural autoregression [@canedo2024]. In annual agricultural production, a gradient-boosting model had the lowest validation error, but statistical models were preferred for extrapolation, because tree-based models cannot predict values above the training maximum [@alkhatib2026]. Rigorous evaluation on financial and macroeconomic data found that statistical models deteriorated less than machine learning models on highly volatile series [@beck2025].

The limitations of the linear models are equally clear. In daily fashion sales, seasonal ARIMA with a weekly period was outperformed by a neural autoregression [@padilha2025]. For intermittent online sales, ARIMA prediction intervals were "too large and thus, not much meaningful" [@ahmadov2023]. Missing values are a practical problem as well. They alter the autocorrelation structure on which both ARIMA and LSTM models depend, and a comparison of ten imputation methods recommended Kalman smoothing among other approaches [@niako2024]. State-space formulations of ARIMA and exponential smoothing avoid imputation altogether, because the Kalman filter treats a missing observation as unobserved. This property was used in this project to handle store closures.

## Neural Forecasting: Feed-Forward Networks and LSTM {#sec:nnlit}

Feed-forward networks map a window of past values directly to future values. Recurrent networks process the window sequentially and carry a hidden state. The LSTM adds input, forget and output gates and a cell state that preserve information across long sequences and mitigate the vanishing-gradient problem [@kim2025]. A survey of deep learning for time-series forecasting notes that the sequential computation of the LSTM causes "high computational costs and slow learning speeds", and that simple linear models can surpass Transformer architectures [@kim2025]. Applications confirm both strengths and weaknesses. A multivariate LSTM for hourly temperature lost accuracy at a three-day horizon, and its "confidence interval widens as the prediction term increases" [@nketiah2023].

In retail, the evidence is mixed and often weakened by evaluation design. An LSTM variant for point-of-sale data was evaluated with a "time-aware splitting strategy" and preprocessing fitted on training data only, but only one step ahead [@suresh2026]. A hybrid of gradient boosting, a neural network and attention was evaluated on Walmart data with five-fold cross-validation, without stating whether the time order was preserved. This leaves the reported accuracy open to look-ahead bias, even though the differences were tested for significance [@mbodila2026]. For intermittent demand, statistically informed feature engineering produced larger gains than architectural complexity [@nathan2026]. Deep learning forecasts for intermittent online sales were up to 35% more accurate than classical methods, but the sellers were small and no promotional information was used [@ahmadov2023]. Taken together, these studies suggest that network architecture matters less than the information set, the evaluation protocol and the handling of special days.

## Hybrid Statistical-Neural Models {#sec:hybridlit}

The hybrid models reviewed here share one principle. A statistical model captures the linear, autocorrelated and seasonal structure, and a neural network models what remains. The studies differ in how the two parts are coupled, how the residuals are defined and how the result is evaluated. {tbl:hybridstudies} compares twelve recent studies on these dimensions.

::: table id=tbl:hybridstudies widths=2.7,3.2,3.9,2.6,3.5 size=8
caption: Comparison of recent hybrid statistical-neural forecasting studies
source: Author's own synthesis of the cited studies (2023 to 2026).
| Study | Data | Coupling of the two components | Significance test | Main finding |
|---|---|---|---|---|
| @siamba2023 | Monthly TB cases (120) | ANN fitted to ARIMA residuals, added | Diebold-Mariano | MAPE 38.9% (seasonal ARIMA) to 36.0% |
| @wan2023 | Daily disease cases (3,134) | EEMD-LSTM on ARIMA residuals, added | None | Plain ARIMA-LSTM less accurate than ARIMA |
| @duan2023 | Daily air quality index, four cities | ARIMA for the linear part, CNN-LSTM for the non-linear part | None | Error reductions against nine benchmarks |
| @linardatos2023 | Hourly CO2 sensor data | Average of ARIMA and transformer forecasts | Friedman with Holm | Significantly better in 13 of 20 RMSE cases |
| @si2024 | Daily index spread (7,927) | GRU or LSTM on ARIMA residuals, added | None | MAE 0.384 to 0.346 |
| @huang2025 | Daily tobacco sales (337) | CNN-LSTM on ARIMA residuals, added | None | MAPE 38.9% to 11.3% |
| @du2025 | Monthly disease cases (120) | LSTM on ARIMA residuals, added | None | Hybrid MAPE 0.08%; seasonal naive beat ARIMA and LSTM |
| @milli2025 | Hourly PM2.5, Beijing | LSTM on Prophet in-sample residuals, added | None (bootstrap intervals for metrics) | Lower MAE and RMSE than the compared models |
| @vallejo2025 | Hourly air quality, Chile | ARIMA orders define ANN inputs | None | R2 above 0.90 |
| @gerakoudi2026 | Daily shipping stock prices | ARIMA-LSTM combination | None | Hybrid best at short horizons; LSTM beat ARIMA |
| @mbodila2026 | Retail sales incl. Walmart | Gradient boosting, ANN and attention fused | Paired t-test | Lowest RMSE on Walmart data; time order of folds unclear |
| @nathan2026 | Intermittent parts demand | Decomposed architecture versus single model | Wilcoxon | Feature engineering beat architectural complexity |
:::

Four critical observations follow from {tbl:hybridstudies}. First, the reported gains vary from marginal to dramatic, and the most dramatic ones deserve scepticism. In @du2025, the hybrid's MAPE of 0.08% on a 12-month hold-out is implausibly close to perfection for monthly disease counts. In the same study the seasonal naive forecast was more accurate than either single model, a pattern consistent with an evaluation flaw rather than a genuine breakthrough. The recommendations of @hewamalage2023 apply directly here: leakage through preprocessing fitted on the whole series can make a model appear "the best model even outperforming the naïve forecast".

Second, a hybrid is not guaranteed to beat its own components. @wan2023 found that the plain ARIMA-LSTM was less accurate than ARIMA alone (RMSE 9.85 against 6.95). Only an additional decomposition of the residuals reversed the result.

Third, significance testing is the exception rather than the rule. Only four of the twelve studies used a formal test: the Diebold-Mariano test [@siamba2023], a Friedman test with Holm correction [@linardatos2023], a paired t-test [@mbodila2026] and the Wilcoxon test [@nathan2026]. Only the first is designed for comparing forecasts, and the Friedman test showed that the hybrid's advantage was significant in only some of the comparisons [@linardatos2023].

Fourth, the residual hybrids train the network on the in-sample residuals of the fitted statistical model [@siamba2023; @si2024; @milli2025]. Where the horizon was stated, they were evaluated over short horizons: one day ahead [@wan2023], one step ahead [@si2024] or up to five steps ahead [@gerakoudi2026]. Retail planning needs forecasts several weeks ahead. Over a multi-week horizon, the error of the statistical forecast is no longer the one-step residual on which the network was trained, and it grows with the horizon. A network trained to predict one-step residuals may therefore correct only the first few days of a long forecast. No study in the review examined this mismatch, and it motivates the comparison of residual definitions in {sec:hybrid}.

The coupling schemes also differ more than the label "hybrid" suggests. Additive residual correction [@siamba2023; @huang2025], averaging of independent forecasts [@linardatos2023] and the use of statistical model orders as network inputs [@vallejo2025] rest on different assumptions about how linear and non-linear structure interact. This project uses the additive residual form, which matches the proposal. It tests three ways of training the residual network, so that the effect of this design choice can be measured rather than assumed.

## Evaluating Forecasts Rigorously {#sec:evallit}

### Temporal validation and leakage

Forecast evaluation must respect time order. Rolling-origin evaluation "seems the most adequate as it preserves the temporal order" under non-stationarity [@hewamalage2023]. In time series, random cross-validation "disrupts the temporal sequence", and parameters of any preprocessing step must be learnt on training data only [@sasse2025]. Leakage is easy to introduce and hard to detect from the outside, which is why @sasse2025 recommend internal code review and conclude that "ensuring the correctness of a ML pipeline should take precedence over its output". This project implements these recommendations as automated tests that fail if future values reach the training data (see {sec:software}).

### Accuracy measures

No single error measure is sufficient, because each has a different weakness:

- **RMSE** penalises large errors and is in the units of the series, but it is dominated by large series when averaged across a panel [@hewamalage2023].
- **MAE** is "more interpretable than MSE or RMSE", because squared measures "inflate unsystematic error by squaring deviations" [@robeson2023].
- **MAPE** is intuitive for managers but produces "excessively large values" when actual values are close to zero [@hewamalage2023].
- **MASE** scales the absolute error by the in-sample error of a naive benchmark. It is therefore scale-free and meaningful across series [@hewamalage2023].

Even scaled measures hide which series benefit from a model when they are averaged, because "important information is lost when current error metrics are averaged" [@strom2024]. This project therefore reports RMSE, MAPE and MASE, evaluates MAPE only on days with positive sales, and reports results by horizon and by series.

### Benchmarks and significance

A naive benchmark is essential. In a rigorous comparison of eight methods including ARIMA, ETS and LSTM, no model significantly beat the naive forecast on exchange rates, and only "four out of 960" cases were significantly better on the NASDAQ100 stock index [@beck2025]. For seasonal series, the appropriate benchmark is the seasonal naive forecast [@hewamalage2023]. Differences in accuracy should also be tested formally rather than judged by inspection [@hewamalage2023]. The Diebold-Mariano test, used by @siamba2023 and @beck2025, compares the losses of two forecasts while allowing for the autocorrelation of multi-step errors. When several models were compared, @alsaif2026 and @linardatos2023 applied a Holm correction for multiple testing.

### Hyperparameter optimisation

Neural networks depend on hyperparameters such as the input window, the number of units and the learning rate. @beck2025, for example, tuned them on a validation period with tree-structured Parzen estimators, a Bayesian optimisation method. Tuning carries two risks. The first is overfitting the validation data: models with default hyperparameters performed comparably to extensively tuned ones at a computational cost about four orders of magnitude lower [@tetko2024]. The second is cost: in one study, hyperparameter tuning was "primarily responsible" for the excess carbon emissions of training [@rafat2023]. A modest, documented tuning budget is therefore both methodologically and ethically defensible.

### Prediction intervals

Inventory decisions depend on uncertainty as much as on the point forecast, because safety stock is set from the expected spread of demand. Model-based intervals from ARIMA and exponential smoothing assume correctly specified Gaussian errors. Neural networks do not provide intervals at all. Split conformal prediction offers a model-agnostic alternative: errors on a calibration period define the interval width. Applied to an LSTM, it achieved about 95.2% coverage for a 95% target [@zhang2025]. Its guarantee assumes exchangeable errors, which time series violate, and multi-step forecasts need horizon-specific calibration [@schlembach2025]. Empirical coverage on the test period is therefore an essential check, not a formality.

## Business Intelligence, Decision Support and Accessibility {#sec:bilit}

Analytics creates value when it is embedded in decision processes. A systematic review of business-analytics affordances found that forecasting "present and future business risks/threats and opportunities" and fast, user-friendly access to data were linked to decision quality and planning effectiveness. A data-driven culture acted as a mediator [@kurpiela2024]. Interactive dashboards are the usual interface. They support exploration through filtering and drill-down, and uncertainty should be shown explicitly, for example through confidence-interval displays [@neri2025]. Dashboards built on predictive models have been developed for planning problems, but how such dashboards can be applied to different planning tools "remains a critical implementation challenge" [@choi2024].

Usability must be evaluated with intended users. A key performance indicator dashboard for community and retail pharmacies was validated with 20 end users through the System Usability Scale (SUS), with scores of 80 or more interpreted as excellent usability. The overall score was 82.5 [@hammad2026]. Accessibility is a precondition for usability, since "low accessibility for certain individuals is bound to affect the usability" [@choiseo2024]. The Web Accessibility Initiative principles require interfaces to be perceivable, operable, understandable and robust, which in practice means sufficient colour contrast, keyboard navigation, zoom, captions and support for screen readers [@choiseo2024]. Colour-vision deficiencies affect a substantial part of the population, so charts should remain readable for common deficiencies and in greyscale [@nelli2024].

Methodologically, the cross-industry standard process for data mining (CRISP-DM) remains the reference life cycle for data projects. In one recent application, all six phases were applied, data preparation was "the most labor-intensive phase", and deployment took the form of a dashboard [@doede2025]. It has also been criticised as linear, model-centric, weak on governance and offering little support for project management. A data-centric adaptation therefore replaces model delivery with "Dashboard Development and Insight Delivery" and embeds iterative validation [@sousa2026]. This project combines CRISP-DM with iterative development increments for these reasons ({sec:methodology}).

## Ethics, Sustainability and Computational Cost {#sec:ethicslit}

Algorithmic forecasts influence decisions about stock, staff and supply, so their transparency and accountability matter. Transparency alone is "insufficient for accountability", and complex models are "less interpretable", which strengthens the case for human oversight and documentation [@cheong2024]. A review of 90 studies of algorithmic decision-making in organisations found tensions between transparency and opacity and between human and algorithmic agency. Humans act as "algorithmic brokers" between model outputs and decisions [@wang2026]. A planning dashboard should therefore support, not replace, the planner's judgement.

The environmental cost of deep learning is a second concern. Green AI aims at "energy efficiency (e.g., watt-hours per model training)" and a reduced carbon footprint [@tabbakh2024]. Energy can be measured during training and should be reported alongside accuracy [@scala2025; @rafat2023]. In retail specifically, accurate forecasts can reduce food waste [@winkler2023]. The same promotions that raise sales can also increase waste in households [@gravert2025]. A sustainable forecasting system therefore balances accuracy against the cost of computation and considers the wider effects of the decisions it informs.

## Synthesis and Research Gaps {#sec:gaps}

The review supports four conclusions:

1. Statistical models remain strong and interpretable benchmarks, and naive benchmarks are frequently not beaten [@beck2025; @canedo2024].
2. Hybrid ARIMA-LSTM models are popular, but their evaluation is often weak. Significance tests are rare, implausible results appear, and residual networks are trained and evaluated one step ahead [@du2025; @wan2023; @si2024].
3. Uncertainty and computational cost are rarely reported together with accuracy [@zhang2025; @rafat2023].
4. Few studies take forecasts through to an accessible decision-support artefact [@hammad2026; @neri2025].

This project addresses these gaps in four ways:

- It benchmarks a hybrid against a seasonal naive, two statistical and two neural models on two retail datasets, under a strict rolling-origin protocol with leakage tests.
- It tests the significance of accuracy differences across five random seeds.
- It compares three definitions of the residual target over a 28-day horizon.
- It reports calibrated intervals, runtime and estimated energy, and exposes the results through a Power BI data model designed for accessibility.

## Requirements Analysis {#sec:requirements}

The requirements were derived from the aim and objectives, the module guidance and the gaps above. Each requirement is testable, and the verification method is stated so that {sec:evaluation} can report against it. {tbl:requirements} lists the functional (FR), non-functional (NFR), data (DR) and security and ethics (SR) requirements.

::: table id=tbl:requirements widths=1.3,8.2,6.0 size=8.5
caption: Requirements of the forecasting framework and dashboard
source: Author's own work, derived from the proposal, the module handbook and the reviewed literature.
| ID | Requirement | Verification |
|---|---|---|
| FR1 | Load the raw Kaggle files and report their integrity: rows, columns, missing cells and checksums | Integrity report ({app:B}) |
| FR2 | Build daily store-level series with known closures and causally flagged anomalies | Unit tests; EDA |
| FR3 | Produce 28-day forecasts from rolling origins for seasonal naive, ARIMA, ETS, FFNN, LSTM and hybrid models | Forecast files for every origin |
| FR4 | Provide a 95% prediction interval for every model | Coverage on the test period |
| FR5 | Compute RMSE, MAPE and MASE by model, series and horizon, and Diebold-Mariano tests | Metric tables; unit tests on known inputs |
| FR6 | Tune neural hyperparameters using data before the validation period only | Leakage tests; tuning logs |
| FR7 | Export a star schema with planning indicators for Power BI | Export script; acceptance values |
| FR8 | Dashboard pages for forecast versus actual with intervals, model comparison and planning, filterable by dataset, store, model and origin | Dashboard test plan ({app:E}) |
| FR9 | Log every experiment with parameters, seed, runtime and metrics | Experiment log |
| NFR1 | Temporal integrity: no information after the forecast origin enters fitting or inputs | Perturbation tests must pass |
| NFR2 | Reproducibility: fixed seeds, deterministic operations, pinned versions, one command per stage | Re-run comparison; repository guide |
| NFR3 | Maintainability: modular package, type hints, docstrings, automated tests | Code review; test suite |
| NFR4 | Feasibility: complete on a two-core laptop CPU without a GPU | Measured runtimes |
| NFR5 | Sustainability: runtime and estimated energy reported for every model | Cost table |
| NFR6 | Usability: dashboard SUS score of 80 or more, interpreted as excellent [@hammad2026] | User study (approved, pending) |
| NFR7 | Accessibility: readable without colour cues and in greyscale, keyboard operable, usable with a screen reader through alternative text [@choiseo2024; @nelli2024] | Accessibility checklist |
| DR1 | Daily data with at least two years of history per series | Data summary |
| DR2 | Covariates limited to information known in advance (calendar, events, promotions) | Code review; leakage tests |
| DR3 | No personal data in modelling data or dashboard | Data dictionary |
| SR1 | Raw data and any participant data kept out of the public repository | Repository content check |
| SR2 | Participant data handled under the approved ethics protocol: consent, pseudonymisation, approved storage | Ethics documentation ({app:G}) |
:::
