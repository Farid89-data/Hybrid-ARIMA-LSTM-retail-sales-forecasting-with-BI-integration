# Project Framing {#sec:framing}

## Background and Context {#sec:background}

Demand forecasts sit at the start of most operational decisions in retail. Replenishment orders, staff rosters, promotional plans and short-term revenue projections are all derived from an estimate of what customers will buy in the coming days and weeks. When that estimate is wrong, the cost appears in two opposite forms: surplus stock that ties up capital and, for perishable goods, becomes waste, and stock-outs that lose sales and customer goodwill. Interviews with twelve German grocery retailers identified demand forecasting and automated ordering among the options for preventing food surplus before it arises [@winkler2023]. A study of food and beverage outlets reached a similar conclusion from the operator's perspective: accurate sales forecasts supported purchasing of perishables, shift planning and liquidity management, and an automated model reduced the root mean squared error (RMSE) of managers' own forecasts by 22% to 33% [@groene2024]. Forecast errors therefore translate directly into holding and shortage costs, and systematic bias in the forecasts raises these costs [@alsaif2026].

Two families of methods dominate the forecasting of retail sales. Statistical models such as the autoregressive integrated moving average (ARIMA) model and exponential smoothing (ETS) describe a series through a small number of interpretable linear components, are inexpensive to estimate and remain strong benchmarks [@canedo2024; @alkhatib2026]. Deep learning models, in particular the long short-term memory (LSTM) network, can learn non-linear dependencies and interactions with calendar and promotional variables, but they need large amounts of data, are computationally expensive and are harder to explain [@siamba2023; @kim2025; @cheong2024]. Neither family dominates the other: rigorous comparisons report that sophisticated models frequently fail to beat simple benchmarks when the data are volatile or the evaluation is strict [@beck2025].

A third option combines the two. In a hybrid ARIMA-LSTM model, the statistical component captures the linear and seasonal structure of a series, and a neural network is trained on the part that the statistical model leaves unexplained, its residuals. The final forecast is the sum of the two components. This decomposition has been applied in recent studies of disease incidence, financial prices and product sales [@siamba2023; @si2024; @huang2025]. The evidence is, however, uneven. Some studies report large gains [@huang2025], others only marginal improvements without any test of significance [@si2024], and at least one found that a plain ARIMA-LSTM hybrid was less accurate than ARIMA alone [@wan2023].

Accurate forecasts only create value when they reach the people who make decisions. Business intelligence (BI) dashboards are the usual channel, and a systematic review of 127 studies found that interactive visualisation with filtering, drill-down and explicit display of uncertainty helps domain experts act on model outputs without data-science expertise [@neri2025]. Adoption also depends on trust: managers accept algorithmic recommendations when the model uses information they recognise and when its performance has been demonstrated against their own judgement [@groene2024].

## Problem Statement and Rationale {#sec:problem}

The literature reviewed in {sec:factfinding} shows four weaknesses that limit what can be concluded about hybrid ARIMA-LSTM models for retail forecasting:

1. Gains are often claimed without a test of statistical significance, without a naive benchmark, or with validation schemes that do not respect time order, which can inflate accuracy [@hewamalage2023; @beck2025].
2. Hybrids are typically trained on the in-sample residuals of the statistical model and evaluated over short horizons, often one step ahead [@si2024; @wan2023], whereas replenishment and revenue planning require forecasts several weeks ahead. How residual correction behaves over a multi-week horizon is rarely examined.
3. Uncertainty and computational cost are seldom reported, although decision-makers need intervals to set safety stock and the energy cost of training neural networks is a growing concern [@zhang2025; @rafat2023].
4. Forecasting studies rarely carry the forecasts through to a decision-support artefact, although dashboard studies show how such artefacts can be validated with users and against accessibility principles [@hammad2026; @choiseo2024].

This project addresses these weaknesses with a reproducible benchmark on two public retail datasets, a strict chronological evaluation with significance testing and interval calibration, and a Power BI data model that turns the forecasts into planning indicators. Each of these elements is designed in {sec:development} and assessed in {sec:evaluation}.

## Aim {#sec:aim}

The aim, as approved in the project proposal, is:

"The aim of this project is to design, implement, and critically evaluate a hybrid ARIMA-LSTM forecasting framework for retail sales data, and to integrate the resulting model into an interactive Business Intelligence dashboard that supports inventory and revenue planning decisions."

## Objectives {#sec:objectives}

The five objectives approved in the proposal are reproduced below. Only punctuation has been restored in Objective 3, where list delimiters were missing in the proposal file; the wording is unchanged.

1. To conduct a structured literature review of statistical, machine learning, and hybrid time-series forecasting methods, with particular attention to the retail domain, completed by the end of Week 3.
2. To prepare and exploratory-analyse a publicly available retail dataset (the M5 Forecasting dataset and/or the Rossmann Store Sales dataset), addressing missing values, seasonality, and feature engineering, by the end of Week 5.
3. To implement and benchmark four forecasting models (ARIMA, Exponential Smoothing, a feed-forward neural network, and an LSTM) using consistent evaluation metrics (RMSE, MAPE, and MASE), by the end of Week 8.
4. To develop and tune a hybrid ARIMA-LSTM model and statistically compare its performance against the benchmark models using the Diebold-Mariano test, by the end of Week 10.
5. To deploy the best-performing model behind an interactive dashboard built in Power BI (or Tableau), and to evaluate the dashboard's usability with at least three potential business users using a structured feedback protocol, by the end of Week 12.

## Research Questions {#sec:rqs}

The proposal did not state explicit research questions. The following four questions were derived from the aim and objectives so that the evaluation in {sec:evaluation} can answer them directly.

- **RQ1.** To what extent does a hybrid ARIMA-LSTM residual model improve 28-day-ahead point accuracy (RMSE, mean absolute percentage error (MAPE) and mean absolute scaled error (MASE)) over ARIMA, ETS, a feed-forward neural network (FFNN), a standalone LSTM and a seasonal naive benchmark on daily store-level retail sales?
- **RQ2.** Are any differences statistically significant under the Diebold-Mariano test with a small-sample correction, and are they consistent across random seeds, series and the two datasets?
- **RQ3.** How well calibrated are the models' 95% prediction intervals, and what accuracy is gained per unit of computational cost?
- **RQ4.** How can the forecasts be integrated into a Power BI dashboard that meets the functional, non-functional and accessibility requirements of inventory and revenue planning?

## Scope and Delimitations {#sec:scope}

The project forecasts daily sales at store level. It uses the ten store-level series of the M5 dataset (Walmart) and a stratified sample of 20 stores from the Rossmann dataset, both obtained from Kaggle [@kaggle2020m5; @kaggle2015rossmann]. Item-level series, which are dominated by zero sales, are outside scope because they violate the assumptions of ARIMA and make percentage errors undefined. Forecasts are made 28 days ahead from rolling origins, and all models use only information that would have been available at the forecast origin, together with calendar and promotion information that is known in advance. All models were implemented in Python. The planned R implementation was not undertaken, because R was not installed on the development machine; Python was used for every reported result. The Power BI component is delivered as a tested data model, measures and build specification. Ethical approval for the user-acceptance study has been granted, but the study had not been conducted when this report was written, so no usability results are reported.

## Expected Contribution {#sec:contribution}

The project makes three contributions. Methodologically, it provides a transparent benchmark of statistical, neural and hybrid models with significance testing, interval calibration and cost reporting, and it compares three ways of training the residual network, a design choice that previous hybrid studies leave implicit. Practically, it shows how forecasts and their uncertainty can be expressed as planning indicators in a BI data model that non-technical managers can interrogate. Professionally, the code base, tests and documentation form a reproducible portfolio artefact.

## Structure of the Report {#sec:structure}

{sec:factfinding} reviews the literature and derives the requirements. {sec:development} describes the methodology, data preparation, models, software and dashboard design. {sec:evaluation} evaluates the results, the artefact and the project process. {sec:conclusion} summarises the findings against the objectives and proposes further work. The appendices contain the dataset documentation, model specifications, test plans and user-study materials.
