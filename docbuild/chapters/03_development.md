# Project Development {#sec:development}

## Methodology {#sec:methodology}

The project combined the cross-industry standard process for data mining (CRISP-DM) with short, iterative development increments. CRISP-DM provided the analytical life cycle: business understanding, data understanding, data preparation, modelling, evaluation and deployment. It was chosen because it is the established reference model for data projects and makes the data preparation effort explicit, which was the most labour-intensive phase in one application [@doede2025]. Reported weaknesses are a linear, model-centric view and little built-in governance [@sousa2026]. These were mitigated in three ways. First, each phase was delivered as an increment that ended with a working, tested artefact. Second, decisions were recorded in a decisions log with their alternatives and justification. Third, the evaluation phase fed back into data preparation and modelling where a problem was found.

A waterfall plan was rejected because the behaviour of the hybrid model could not be known in advance, and the design had to respond to what the data revealed. A full Scrum process was also rejected, because it assumes a team, a product owner and regular stakeholder reviews, none of which exist in an individual MSc project. The resulting increments are listed in {tbl:increments}, and the project plan is compared with the actual increments in {app:H}.

::: table id=tbl:increments widths=1.6,4.0,5.2,4.6 size=8.5
caption: Development increments and their outputs
source: Author's own work.
| Increment | CRISP-DM phase | Main activities | Output |
|---|---|---|---|
| 1 | Business understanding | Read the handbook and proposal, define requirements, set up the environment | Compliance matrix; decisions log |
| 2 | Data understanding | Integrity check of the raw files, exploratory analysis | Data check report; exploratory figures |
| 3 | Data preparation | Store-level series, closures, anomalies, covariates, chronological splits | Prepared panels; split plans; unit tests |
| 4 | Modelling (benchmarks) | Seasonal naive, ARIMA, ETS with rolling-origin forecasts | Statistical forecasts; residual artefacts |
| 5 | Modelling (networks and hybrids) | FFNN, LSTM and three hybrid variants; tuning and five-seed training | Neural forecasts; tuning logs |
| 6 | Evaluation | Metrics, Diebold-Mariano tests, interval calibration, cost | Result tables and figures |
| 7 | Deployment | Power BI data model, measures, build guide, test plan | Dashboard package |
:::

## Business and Data Understanding {#sec:data}

### Business questions

Store managers and central planners use daily sales forecasts for three decisions:

- how much to order before the next delivery;
- how many staff to roster;
- what revenue to expect in the coming weeks.

A forecast horizon of 28 days covers four weekly ordering cycles and matches the official horizon of the M5 competition. The business questions were therefore framed as follows:

- How accurate are 28-day store-level forecasts?
- How much safety margin do they require?
- Which model offers the best balance between accuracy, reliability and cost?

### Datasets and provenance

Two public datasets were used. Both were downloaded by the author from the Kaggle competition pages [@kaggle2020m5; @kaggle2015rossmann] and placed in the project's data folder. No other copies or mirrors were used.

- **M5 (Walmart).** Daily unit sales of 3,049 products in ten stores in California, Texas and Wisconsin, from 29 January 2011 to 22 May 2016. The data include a calendar with events and with days on which Supplemental Nutrition Assistance Program (SNAP) benefits are paid.
- **Rossmann.** Daily sales (turnover) of 1,115 German drugstores, from 1 January 2013 to 31 July 2015. The data include opening status, promotions and school and state holidays.

Before any modelling, every file was opened and checked: number of rows and columns, column names, missing cells and a SHA-256 checksum. All nine files were complete and readable. The integrity report is reproduced in {app:B}. The raw files are not redistributed with the code; the reproduction guide explains how to obtain them from the Kaggle pages.

### Exploratory analysis

The analysis focused on the properties that determine model design. {fig:m5series} shows the ten M5 store series as seven-day moving averages, which remove the weekly cycle. The series share a slow upward trend and a regular monthly rhythm. The rhythm is linked to SNAP payment days, on which mean sales were 12% higher than on other days (between 2% and 32% across stores). Mean daily sales differ between stores by a factor of 2.7. Every store recorded almost no sales on Christmas Day, when the stores are closed. The Rossmann stores ({fig:rossseries}) show a different pattern: no trading on Sundays or public holidays, a strong promotional cycle and peaks before Christmas. In the sample, mean sales were 40% higher on promotion days than on other trading days, and 29% higher from 1 to 24 December than over the year as a whole.

::: figure id=fig:m5series file=outputs/figures/eda_m5_store_series.png width=15.5
caption: Seven-day moving average of daily unit sales in the ten M5 stores
source: Author's own work, based on the M5 dataset [@kaggle2020m5].
alt: Ten overlaid lines of seven-day average unit sales from 2011 to 2016, one per Walmart store, showing a gradual upward trend, monthly fluctuations and the shaded validation and test periods.
:::

::: figure id=fig:rossseries file=outputs/figures/eda_rossmann_sample_series.png width=15.5
caption: Daily sales of a selection of the sampled Rossmann stores
source: Author's own work, based on the Rossmann dataset [@kaggle2015rossmann].
alt: Line charts of daily sales for four sampled Rossmann stores from 2013 to 2015, with gaps on closed days, a saw-tooth weekly pattern, a mostly fortnightly promotional pattern and pre-Christmas peaks.
:::

The weekly profiles in {fig:weekly} confirm that the day of the week is the dominant source of variation in both datasets. Sales in M5 peak on Saturdays and Sundays, at about 20% above the weekly mean, while Rossmann sales peak on Mondays, at about 19% above the mean, and are zero on Sundays. The autocorrelation functions ({fig:acf}) decay slowly at multiples of seven days. This pattern indicates a weekly seasonal unit root and motivates seasonal differencing in ARIMA. {tbl:datasummary} summarises the two panels.

::: figure id=fig:weekly file=outputs/figures/eda_weekly_profiles.png width=15
caption: Average sales by day of the week, relative to the series mean
source: Author's own work, based on the M5 and Rossmann datasets.
alt: Two bar charts of relative sales by weekday. M5 sales peak on Saturday and Sunday; Rossmann sales peak on Monday and are zero on Sunday.
:::

::: figure id=fig:acf file=outputs/figures/eda_acf.png width=15
caption: Autocorrelation of daily sales up to lag 56 for one series of each dataset
source: Author's own work.
alt: Two autocorrelation plots with spikes at lags 7, 14, 21 and so on that decay slowly, indicating strong weekly seasonality.
:::

::: table id=tbl:datasummary csv=outputs/tables/dataset_summary.csv size=8
caption: Summary of the two modelling panels
source: Author's own calculation from the Kaggle files. Coefficient of variation is the mean over series of the standard deviation divided by the mean on trading days.
:::

## Data Preparation {#sec:prep}

### Series construction and sampling

For M5, the item-level sales were summed to the ten store-level daily series. Item-level series were not modelled, because most items sell zero units on most days. Such intermittent series violate the assumptions of ARIMA and make percentage errors undefined.

For Rossmann, a sample of 20 stores was drawn so that the experiments could be completed on the available hardware. A store was eligible when it met four conditions, judged on records before the test period only:

- it had a record for every day before the test period;
- it never opened on Sundays, so all stores share the same trading week;
- it had at most 35 closures on weekdays, which excludes long refurbishment closures;
- it had no day recorded as open with zero sales, which would indicate a recording error.

Of the 1,115 stores, 850 met these conditions. The sample was stratified by store type and assortment, with allocation proportional to stratum size and at least two stores per stratum, and drawn with a fixed random seed (2026). Store type "b" does not appear in the sample, because all its stores trade on Sundays. The selected stores are listed in {app:B}.

### Closures, anomalies and missing values

Known closures are not demand. Forecasting them as low sales would distort both the models and the error measures. Closures were therefore treated as known in advance: Rossmann days with an "Open" flag of zero, and Christmas Day in M5. They were handled differently by model family:

- the state-space models received them as missing observations;
- the networks received a zero value together with an availability flag;
- they were excluded from scoring.

Data errors were handled with a causal rule. A trading day was flagged as an anomaly when its sales fell below 10% of the median of the previous 28 trading days. Because the rule uses only past values, it can be applied in operation without look-ahead. It flagged one day across both panels: store TX_2 on 24 March 2015, with 131 units against a median of 3,519 units over the previous four weeks. Anomalies were excluded from model fitting in the same way as closures but kept in scoring, because a planner would have faced them. No values were imputed. The state-space models treat closures and anomalies as unobserved, because missing values alter the autocorrelation structure on which the models depend [@niako2024].

### Covariates

All covariates are known in advance. {tbl:covariates} lists them. The networks used all of them. ARIMA used a subset as regressors, since the day-of-week pattern is captured by its seasonal differencing. A hybrid gain could therefore partly reflect the extra covariates. ETS and the seasonal naive method are univariate benchmarks and use no covariates.

::: table id=tbl:covariates widths=4.2,6.8,2.4,2.4 size=8.5
caption: Covariates known at the forecast origin
source: Author's own work.
| Covariate | Definition | Networks | ARIMA |
|---|---|---|---|
| Day of week | One-hot encoding (seven indicators) | Yes | No (seasonal differencing) |
| Month | Sine and cosine of the month angle | Yes | No |
| Annual Fourier terms | Sine and cosine of the first two annual harmonics | Yes | Yes |
| Event indicators (M5) | Any event, and one indicator per event type | Yes | Any event only |
| SNAP day (M5) | Benefit payment day in the store's state | Yes | Yes |
| Promotion (Rossmann) | Store runs a promotion | Yes | Yes |
| School holiday (Rossmann) | School holiday in the store's region | Yes | Yes |
| State holiday (Rossmann) | Any public holiday | Yes | No (stores closed) |
| Opening flag | Store open on the target day | Yes | Closed days missing |
:::

### Chronological splits

Each panel was divided into a training period, a validation period and a test period ({fig:splits}). The test period is the last part of each series, divided into non-overlapping 28-day windows:

- **M5:** 14 windows, or 392 days (about 20% of the series), from 27 April 2015 to 22 May 2016.
- **Rossmann:** seven windows, or 196 days, from 17 January to 31 July 2015.

The validation period comprises the five 28-day windows immediately before the test period. These windows replace the five-fold time-series cross-validation planned in the proposal: each model is trained once before the validation period and evaluated from five successive origins, which keeps the time order and the 28-day horizon and avoids five separate trainings per tuning trial. Model specifications and hyperparameters were chosen on the validation period, using models trained only on data before it. The selected models were then re-estimated on all data before the test period and used, with fixed parameters, to forecast each test window from its origin. At each origin a model used only observations up to the day before. This rolling-origin design reproduces how a planner would use the models and follows the recommendations of @hewamalage2023.

::: figure id=fig:splits file=outputs/figures/eda_split_timeline.png width=15
caption: Training, validation and test periods with the rolling forecast origins
source: Author's own work.
alt: Timeline for each dataset showing a long training period, five validation windows and the test windows of 28 days, each beginning at a forecast origin.
:::

### Scaling

The networks were trained on standardised series. Each series was standardised with its own mean and standard deviation, both computed on training days only. The MASE denominator was likewise computed per series on the training period only. Neither statistic uses validation or test data.

## Models {#sec:models}

### Seasonal naive benchmark

The seasonal naive forecast repeats the most recent observed value for the same day of the week, as in {eq:snaive}. If that day was closed or anomalous, the latest valid value from an earlier week is used.

$$\hat{y}_{o+h-1 \mid o} = y_{o+h-1-7k}, \quad k = \lceil h/7 \rceil$$ {#eq:snaive}

where \(o\) is the first forecast day and \(h = 1, \ldots, 28\) is the horizon. In effect, the last observed week is repeated over the four weeks of the horizon.

### ARIMA with known regressors

The statistical model is a regression with seasonal ARIMA errors, shown in {eq:arima}:

$$y_t = \boldsymbol{\beta}^{\top}\mathbf{x}_t + u_t, \quad \phi(B)\,\Phi(B^7)\,(1-B)^d\,(1-B^7)\,u_t = \theta(B)\,\Theta(B^7)\,\varepsilon_t$$ {#eq:arima}

where \(\mathbf{x}_t\) contains the regressors of {tbl:covariates}, \(B\) is the backshift operator, and \(\phi\), \(\Phi\), \(\theta\) and \(\Theta\) are polynomials of order \(p\), \(P\), \(q\) and \(Q\). Seasonal differencing at lag seven was imposed because every series showed a strong weekly cycle. The order of non-seasonal differencing \(d\) was chosen by a Kwiatkowski-Phillips-Schmidt-Shin (KPSS) stationarity test on the seasonally differenced series. The orders \(p\) and \(q\) (up to three) and \(P\) and \(Q\) (up to two) were chosen by a stepwise search that minimised the corrected Akaike information criterion (AICc). The search started from four initial models and moved to neighbouring orders while the AICc improved.

The model was implemented in the statsmodels state-space framework. The Kalman filter treats closures and anomalies as missing observations, so no imputation was needed. One-step-ahead residuals and multi-step forecasts are both produced by the same causal filter. A consistency check confirmed that the multi-step forecast paths used by the hybrids agreed with direct forecasts at every test origin.

### Exponential smoothing

The ETS benchmark is the linear state-space exponential smoothing model with additive errors and additive weekly seasonality. Three trend forms were compared by AICc: no trend, additive trend and damped additive trend. The concentrated initialisation was used because it was the only option in the library that handled missing observations correctly. This was established by testing the alternatives on series with closures.

### Feed-forward network and LSTM

Both networks are global models: one network is trained on all series of a dataset, and a one-hot series identity tells it which store it is forecasting. Global training increases the number of training windows, which matters for short daily series. Both networks produce all 28 forecasts at once (direct multi-output). This avoids the error accumulation of recursive forecasting. Each training example has four parts:

- a past block of \(L\) days (the standardised sales, an availability flag and the covariates);
- a future block of 28 days (the covariates and the opening flag of the target days, but never the target);
- the series identity;
- the 28 target values.

The feed-forward network (FFNN) flattens these inputs and passes them through one or two layers of rectified linear units. The LSTM network encodes the past block with an LSTM layer, whose cell is defined by {eq:lstm} to {eq:lstmout}:

$$\mathbf{f}_t = \sigma(\mathbf{W}_f[\mathbf{h}_{t-1}, \mathbf{x}_t] + \mathbf{b}_f), \quad \mathbf{i}_t = \sigma(\mathbf{W}_i[\mathbf{h}_{t-1}, \mathbf{x}_t] + \mathbf{b}_i)$$ {#eq:lstm}

$$\mathbf{c}_t = \mathbf{f}_t \odot \mathbf{c}_{t-1} + \mathbf{i}_t \odot \tanh(\mathbf{W}_c[\mathbf{h}_{t-1}, \mathbf{x}_t] + \mathbf{b}_c)$$ {#eq:lstmcell}

$$\mathbf{o}_t = \sigma(\mathbf{W}_o[\mathbf{h}_{t-1}, \mathbf{x}_t] + \mathbf{b}_o), \quad \mathbf{h}_t = \mathbf{o}_t \odot \tanh(\mathbf{c}_t)$$ {#eq:lstmout}

where \(\mathbf{f}_t\), \(\mathbf{i}_t\) and \(\mathbf{o}_t\) are the forget, input and output gates, \(\mathbf{c}_t\) is the cell state and \(\mathbf{h}_t\) the hidden state, as presented in @kim2025. The final hidden state is concatenated with the future block and the series identity and passed through a dense layer to the 28 outputs.

Both networks were trained with the Adam optimiser on a masked mean squared error. Days that were closed, anomalous or undefined received zero weight in the loss. Training stopped when the loss on a later, separate block of training windows had not improved for six epochs, and the best weights were restored. This block comprised the last 10% of training origins, and the windows before it were cut back so that no training target overlapped it.

### Hybrid ARIMA-LSTM {#sec:hybrid}

The hybrid follows the decomposition of a series into a linear component \(L_t\) and a non-linear component \(N_t\) ({eq:decomp}). ARIMA estimates the linear component, and an LSTM network learns the structure that remains in the ARIMA errors:

$$y_t = L_t + N_t, \qquad \hat{y}^{\text{hyb}}_{o+h-1} = \hat{L}_{o+h-1 \mid o-1} + \hat{N}_{o+h-1}$$ {#eq:decomp}

The review in {sec:hybridlit} showed that the reviewed studies (2023-2026) leave one design choice implicit: which residuals the network should learn. Three variants were therefore implemented and compared. All use the same LSTM architecture and the same ARIMA models.

- **Direct one-step hybrid (hyb_d).** The network receives the past one-step residuals \(e_t = y_t - \hat{y}_{t \mid t-1}\) with the covariates. In one pass it predicts the next 28 one-step residuals, which are added to the ARIMA forecast path.
- **Recursive one-step hybrid (hyb_z).** This is the classical formulation. The network predicts one residual ahead and is applied 28 times, with each prediction fed back as an input.
- **Multi-step error-correction hybrid (hyb_ms).** The targets are the actual errors of the ARIMA forecast made at the origin, \(y_{o+h-1} - \hat{y}_{o+h-1 \mid o-1}\), for \(h = 1, \ldots, 28\). The network also receives recent sales and the ARIMA forecast path itself. This variant learns how the ARIMA error develops over the horizon, rather than assuming that one-step residuals describe it.

The residuals and forecast paths were produced by the causal Kalman filter with parameters estimated on the training period only. They were scaled by the residual standard deviation of the training period. In the tuning stage, the hybrids were built on the ARIMA model estimated before the validation period. In the final stage, they were built on the re-estimated model. The variant with the best validation MASE was designated the primary hybrid, and the other two are reported as ablations.

### Hyperparameter tuning {#sec:tuning}

The hyperparameters of the networks were tuned with a tree-structured Parzen estimator in Optuna, using a fixed sampler seed of 2026. Each model received 15 trials per dataset. Each trial trained the network on data before the validation period with seed 1, and was scored by the mean per-series MASE over the five validation windows. The search space ({tbl:searchspace}) was deliberately small. Extensive tuning on a short validation period risks overfitting, offers small gains over sensible defaults [@tetko2024] and was the main source of excess emissions in one study [@rafat2023]. The recursive hybrid reused the configuration selected for the direct hybrid, because the two share the same inputs.

::: table id=tbl:searchspace widths=4.0,5.4,6.2 size=8.5
caption: Hyperparameter search space
source: Author's own work.
| Hyperparameter | Values | Applies to |
|---|---|---|
| Input window \(L\) | 28 or 56 days | All networks |
| Hidden units | 32, 64 or 128 (FFNN); 16, 32 or 64 (LSTM-based) | All networks |
| Hidden layers | One or two | FFNN |
| Dropout rate | 0 to 0.3 (continuous) | All networks |
| Learning rate | 0.0003 to 0.003 (logarithmic) | All networks |
| Batch size | 64 or 128 | All networks |
| Maximum epochs; patience | 60; 6 | All networks (fixed) |
:::

After tuning, each network was retrained on all data before the test period with five seeds (1 to 5). It then forecast every test window. Reporting the mean and spread over seeds separates the effect of the model from the effect of random initialisation.

## Evaluation Design {#sec:evaldesign}

### Accuracy measures

Accuracy was measured on scored days, which are trading days with positive recorded sales. The rules for unscored days are as follows:

- closed days are known in advance and were not forecast;
- zero-sales trading days, of which there were none in either panel's test period, would make MAPE undefined.

For a series with \(n\) scored forecasts \(\hat{y}_t\), and training period \(\{1, \ldots, T\}\), the measures are defined in {eq:metrics}:

$$\text{RMSE} = \sqrt{\frac{1}{n}\sum_t (y_t - \hat{y}_t)^2}, \quad \text{MAPE} = \frac{100}{n}\sum_t \left|\frac{y_t - \hat{y}_t}{y_t}\right|, \quad \text{MASE} = \frac{\frac{1}{n}\sum_t |y_t - \hat{y}_t|}{\frac{1}{T-7}\sum_{j=8}^{T} |y_j - y_{j-7}|}$$ {#eq:metrics}

The MASE denominator is the in-sample error of the seasonal naive method on training days, so a MASE below one means the forecast beats the naive method's in-sample accuracy. Metrics were computed per series and averaged with equal weight, so that large stores do not dominate. MASE is the primary measure because it is scale-free, which suits heterogeneous series [@hewamalage2023]. Results are also reported by horizon and by series.

### Significance testing

Accuracy differences were tested with the Diebold-Mariano (DM) test. For two forecasts with errors \(e_{1,t}\) and \(e_{2,t}\), the loss differential is \(d_t = g(e_{1,t}) - g(e_{2,t})\). The statistic, with the small-sample correction of Harvey, Leybourne and Newbold (HLN), is given in {eq:dm}:

$$\text{DM} = \frac{\bar{d}}{\sqrt{\hat{\sigma}^2_{d}/n}}, \qquad \text{DM}^{*} = \text{DM}\sqrt{\frac{n + 1 - 2h + h(h-1)/n}{n}}$$ {#eq:dm}

\(\hat{\sigma}^2_{d}\) is the long-run variance of \(d_t\), estimated with autocovariances up to lag \(h - 1\) and rectangular weights (Bartlett weights replace them if the estimate is not positive), and \(\text{DM}^{*}\) is compared with Student's t distribution with \(n - 1\) degrees of freedom. The test was applied to the daily cross-series mean of losses scaled by each series' MASE denominator, so that every store contributes equally. Days on which no store traded, such as Rossmann Sundays, have no loss and are omitted, so the autocorrelation lags count trading days rather than calendar days. Both squared and absolute losses were used, with \(h = 28\). Pooling horizons 1 to 28 from non-overlapping windows makes the test an approximation, because the error variance changes over the window and the correction assumes a fixed horizon. For networks, the test was repeated for each seed, and a difference was considered robust only if it held for all five seeds. As a descriptive complement, the test was also run separately for each series, on unscaled errors for seed 1, and the counts of significant series use unadjusted p-values. The Holm correction was applied within each family of seven comparisons of the primary hybrid with the other models, separately for each dataset, loss and seed. The pairwise matrix and the ablation tables ({app:D}, {sec:evaluation}) are supplementary evidence: they apply Holm over all 28 pairs per seed with squared loss, and report the mean statistic and the median p-value across seeds.

### Prediction intervals

Every model received a 95% prediction interval built in the same way. This allows the honesty of the models about uncertainty to be compared. Split conformal intervals were calibrated on the validation windows [@zhang2025]. For each horizon \(h\), the scaled absolute errors of the validation forecasts were sorted, and the quantile \(q_h\) at rank \(\lceil (n+1)\,0.95 \rceil\) was taken. The interval is \(\hat{y} \pm q_h s\), where \(s\) is the MASE scale of the series, and its lower bound is clipped at zero. Horizon-specific quantiles allow the interval to widen with the horizon [@schlembach2025]. ARIMA and ETS also provide their own Gaussian intervals, which are reported for comparison. Intervals were assessed by empirical coverage on the test period, by their mean scaled width and by the interval score, which penalises both width and misses.

### Computational cost

Training and fitting times were measured as wall-clock time, with experiments run one at a time on the same laptop: a dual-core Intel Core i7-4510U processor with 5.9 GB of memory and no usable graphics processor. Energy was estimated as time multiplied by the processor's 15 W thermal design power. This is an approximation for comparing models, not a measurement [@scala2025].

## Software Implementation {#sec:software}

### Architecture

The framework was implemented in Python as a package with one module per responsibility ({tbl:modules}). Command-line scripts run each stage and write every result to a file. The result tables and figures in this report are generated from these files rather than typed by hand, and the descriptive statistics quoted in the text are recorded in a file of their own. Statistical models used statsmodels, networks used TensorFlow and Keras, and tuning used Optuna.

::: table id=tbl:modules widths=4.4,11.2 size=8.5
caption: Modules of the forecasting package
source: Author's own work.
| Module | Responsibility |
|---|---|
| config | Paths, horizon, seeds, dataset settings |
| data_loader | Read the raw Kaggle files; build the store panels; Rossmann eligibility and stratified sampling |
| preprocessing | Split plans, causal anomaly rule, masks, scalers, MASE scale |
| statistical_models | Seasonal naive, ARIMA selection and forecasting, residuals and forecast paths, ETS |
| feature_engineering | Training windows, past and future blocks, early-stopping split |
| neural_networks | FFNN and LSTM builders, masked loss, training with early stopping |
| hybrid_model | Residual scaling, multi-step error targets, recursive residual forecasting, combination |
| experiment | End-to-end stages with checkpoints; tuning objective |
| evaluation | Point and interval metrics, conformal calibration |
| statistical_tests | Diebold-Mariano test with HLN correction |
| export_powerbi | Star-schema export for the dashboard |
:::

### Testing and leakage prevention

The package is covered by 40 automated tests written with pytest, grouped in {tbl:tests}. The most important are the leakage tests. They perturb all data after a cut-off and check that the training windows and forecast inputs are unchanged. They also check that the early-stopping block lies after the fitting windows and does not overlap them, and that residuals at day \(t\) do not change when later data change. Other tests compare the metrics and the DM statistic with manual calculations on known inputs. All tests pass. The full list of tests and their results is in {app:E}.

::: table id=tbl:tests widths=3.8,1.4,10.4 size=8.5
caption: Automated tests by area
source: Author's own work. Test files are in the tests folder of the repository.
| Area | Tests | What is verified |
|---|---|---|
| Preprocessing | 6 | Chronological, non-overlapping splits; causal anomaly rule; scoring mask; scaler fitted on training data only; MASE scale by hand calculation |
| Leakage | 4 | Training targets end before the cut-off; early-stopping block later and disjoint; windows and forecast inputs unchanged when future data are perturbed |
| Models | 6 | Seasonal naive repeats the last valid week; interval ordering; one-pass paths equal per-origin forecasts; ETS with missing days; output shape; masked loss |
| Hybrid | 5 | Residual alignment; burn-in and missing days masked; causal residuals; correct combination; multi-step targets equal actual minus path |
| Evaluation | 8 | Metrics on known values; unscored days ignored; interval metrics; conformal rank; DM test on identical, clearly different and hand-computed cases; Holm adjustment |
| Data loading | 3 | Rossmann store eligibility unchanged when records on or after the test start are altered; rules still applied before it; test start matches the split plan |
| Power BI export | 4 | Acceptance values equal a hand calculation; risk-day counts; store-average MASE differs from the pooled value; week start is a Monday and unique across years |
| Title page | 4 | Identity configuration keys; title page matches the identity file; names appear only where expected; applying the identity twice changes nothing |
:::

### Reproducibility

Every source of randomness was seeded: the sample of stores, the tuning sampler and the network weights. TensorFlow was configured to use deterministic operations. Each stage writes checkpoints, so an interrupted run resumes without repeating finished work. Each experiment was logged with its parameters, seed, runtime, energy estimate and metrics. The repository contains the code, the tests, a continuous-integration workflow that runs the tests on every change, pinned package versions and a reproduction guide ({app:I}). The raw data are excluded, and a script checks a user's downloaded files against the recorded checksums.

## Dashboard Design {#sec:dashboard}

The dashboard is the deployment step of CRISP-DM and answers RQ4. It was designed for two user groups:

- **store managers**, who need the next four weeks of forecasts for their own store with a realistic range;
- **planners**, who compare stores and models and set safety stock.

The export script writes a star schema of three dimension tables and three fact tables ({fig:schema}): dates, series and models as dimensions, and actuals, forecasts with intervals and per-series metrics as facts. It also writes a file of acceptance values that the dashboard's measures must reproduce. The Data Analysis Expressions (DAX) measures compute the accuracy measures, interval coverage and four planning indicators:

- **forecast sales**, the sum of point forecasts over the selected days, which gives the expected volume (M5) or turnover (Rossmann);
- **safety stock proxy**, the gap between the upper bound of the 95% interval and the point forecast, a simple indication of the stock needed above the forecast;
- **stock-out risk days** and **overstock risk days**, the number of days on which actual sales fell above the upper bound or below the lower bound.

::: figure id=fig:schema file=outputs/figures/dash_star_schema.png width=15
caption: Star schema of the dashboard data model
source: Author's own work.
alt: Diagram of three dimension tables (date, series and model) linked by one-to-many relationships to three fact tables (actuals, forecasts and metrics).
:::

The dashboard has three pages:

- forecast versus actual with the 95% band for a selected store, model and origin;
- model comparison by accuracy, horizon and cost;
- a planning page with the indicators above.

Slicers for dataset, store, model and origin are shared across pages. Accessibility followed the principles reviewed in {sec:bilit} [@choiseo2024; @nelli2024]:

- a colour palette that remains distinguishable under common colour-vision deficiencies;
- line styles and data labels so that no information depends on colour alone;
- alternative text on every visual;
- a logical keyboard tab order;
- minimum font sizes of 12 points for text and 10 points for axis labels.

The page specification, measures and accessibility checklist are in {app:F}, and the functional test plan is in {app:E}. The functional tests check every measure against acceptance values computed in Python from the same data.

## Issues and Troubleshooting {#sec:issues}

Several problems arose during development. Each was resolved and recorded in the decisions log.

- **Missing values in exponential smoothing.** The default initialisation of the state-space ETS model returned undefined values when closures were present. Each available initialisation was tested on a series with closures, and only the concentrated initialisation produced valid estimates. It was adopted for all series.
- **Multi-step paths for the hybrids.** Computing a 28-day ARIMA forecast at every training day by re-filtering the series would have taken days. The paths were instead derived in one pass from the filtered state and the transition matrix. An initial version failed on models whose design matrix varies over time. After the fix, an automatic check confirmed that the one-pass paths matched direct forecasts.
- **Weekdays without history.** The seasonal naive method failed for Rossmann Sundays, which have no valid history. Such days are closures, so they were forecast as zero and excluded from scoring.
- **Interrupted runs.** A long background run was stopped by the operating environment after a system clock change and lost 16 completed stores. Checkpoints were then added for each series, each tuning trial and each seed, so that every stage can resume.
- **Literature access.** Automated searching of Google Scholar was not possible, and several publishers refused automated access to full texts. Discovery was moved to OpenAlex and Crossref with the project owner's agreement, and only articles whose full text could be read were included ({sec:reviewmethod}).
- **Toolchain deviation.** R was not installed on the development machine, so the planned R cross-check of the statistical models was not performed. Python 3.13 was used instead of Python 3.11.
