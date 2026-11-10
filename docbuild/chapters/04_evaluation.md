# Critical Evaluation {#sec:evaluation}

[[PENDING: results sections (accuracy, significance, horizon, intervals, stability, cost, research questions) are written from the final evaluation outputs.]]

## Evaluation against the Requirements {#sec:reqeval}

{tbl:reqstatus} traces each requirement of {tbl:requirements} to the evidence that it has been met. Most functional and data requirements are met and verified by automated tests or generated reports. The main gaps concern the user-facing part of the artefact: the dashboard file has not been assembled, so its functional and accessibility checks have not been run, and the usability requirement cannot be assessed without the user study.

::: table id=tbl:reqstatus widths=1.5,2.4,11.7 size=8.5
caption: Status of the requirements
source: Author's own assessment against the evidence cited.
| ID | Status | Evidence |
|---|---|---|
| FR1 | Met | Integrity report for all nine files with checksums ({app:B}); checksum verification script |
| FR2 | Met | Preprocessing and data-loading tests; exploratory analysis ({sec:data}) |
| FR3 | [[PENDING: status]] | [[PENDING: forecasts for every model, origin and dataset]] |
| FR4 | [[PENDING: status]] | Implemented and unit-tested (conformal rank); [[PENDING: coverage on the test period]] |
| FR5 | [[PENDING: status]] | Metrics, DM test and Holm adjustment checked against hand calculations; [[PENDING: result tables]] |
| FR6 | Met | Tuning uses data before the validation period only; leakage tests pass |
| FR7 | [[PENDING: status]] | Export script and acceptance values implemented; [[PENDING: export after evaluation]] |
| FR8 | Not yet met | Pages specified and wireframed ({app:F}); dashboard file not assembled |
| FR9 | Met | Experiment log with parameters, seed, runtime, energy estimate and metrics |
| NFR1 | Met | Perturbation tests show no use of data after the cut-off, including store selection |
| NFR2 | Partly met | Fixed seeds, deterministic operations, pinned versions and checkpoints; an independent re-run has not been made |
| NFR3 | Met | Modular package with docstrings and 40 automated tests |
| NFR4 | [[PENDING: status]] | [[PENDING: measured runtimes of all stages]] |
| NFR5 | [[PENDING: status]] | [[PENDING: cost table]] |
| NFR6 | Not assessed | User study approved but not yet conducted |
| NFR7 | Partly met | Greyscale-safe figures and checklist specified ({tbl:a11y}); not yet checked in Power BI |
| DR1 | Met | M5: 1,941 days; Rossmann: 942 days ({tbl:datasummary}) |
| DR2 | Met | Covariates restricted to calendar, event and promotion information known in advance ({tbl:covariates}) |
| DR3 | Met | Store-level data only; data dictionary contains no personal data |
| SR1 | Met | Raw data excluded from the repository; download and checksum instructions provided |
| SR2 | Partly met | Consent and data-handling commitments documented ({app:G}); no participant data collected yet |
:::

## Evaluation of the Process {#sec:process}

### Methodology

Combining CRISP-DM with short increments worked well for the analytical core of the project. Each increment ended with an artefact that could be tested before the next one depended on it. This mattered most at the boundary between the statistical and neural stages. The hybrids need ARIMA residuals and forecast paths that are aligned day by day with the calendar and free of look-ahead. Because these artefacts were produced and tested in their own increment, an alignment error could be detected by a failing test rather than by an implausible result weeks later. The decisions log was equally useful. It recorded, for example, why closures are passed to the state-space models as missing values and why the hybrids were compared in three variants, so that each choice could be justified against its alternatives rather than reconstructed afterwards.

The weaknesses of CRISP-DM noted in {sec:bilit} also appeared. The process model says little about how long modelling and evaluation take on limited hardware, and the plan in the proposal assumed that every model could be tuned and retrained within a week. In practice, computation was the binding constraint. The response, a small tuning budget and checkpointed background runs, was sound but should have been planned from the start.

### What went well

- **Data integrity first.** Checking every raw file before modelling, and recording checksums, meant that every later result can be traced to identical inputs.
- **Leakage prevention by design.** The rolling-origin plan, scalers fitted on training data only and the perturbation tests turned the main methodological risk of the reviewed studies ({sec:hybridlit}) into something that is tested automatically.
- **Numbers generated, not typed.** Every number in the result tables is produced by the evaluation scripts from saved forecasts, which removes transcription errors and makes the report reproducible.
- **Verified literature.** Each source was checked against its DOI record and read in full. A second check of the comparison table in {sec:hybridlit} found and corrected one wrong cell, which shows why this step was necessary.

### What went less well

- **Literature access.** Automated searching of Google Scholar was not possible, and several large publishers refused automated access to full texts. The review therefore rests on 47 articles from a narrower set of publishers than intended, below the 60 to 80 sources that had been planned.
- **Toolchain deviations.** The planned R implementation and cross-check were not carried out, and Python 3.13 replaced Python 3.11.
- **Interrupted computation.** A background run was stopped by the operating environment and its progress was lost, which led to the checkpointing described in {sec:issues}.
- **User evaluation.** Ethical approval for the user study was granted, but the study could not be conducted within the time available, and the dashboard file was not assembled in Power BI Desktop. Objective 5 is therefore only partly met.

### What would be done differently

The user study would be scheduled in parallel with model development rather than after it, because it depends on recruitment and on the dashboard rather than on the final model. Compute would be planned explicitly, with an estimate of training time per model before the tuning budget is fixed, and with access to a graphics processor or cloud resources. Finally, the literature search would start with the library's databases, which provide full-text access, rather than relying on open web access.

## Limitations {#sec:limitations}

The findings are bounded by the following limitations:

- **Scope of the data.** Only store-level daily series were modelled: ten Walmart stores and a sample of 20 Rossmann stores. Results may not transfer to item-level forecasting, where intermittent demand dominates, or to other retail formats and markets.
- **Information set.** Prices were not used as covariates, because they are recorded per item and do not aggregate meaningfully to store level. Weather, competitor actions and local events were not available.
- **Fixed parameters between origins.** Model parameters were estimated once before the test period and kept fixed at later origins. Periodic re-estimation might improve all models, and its effect on the ranking was not tested.
- **One test period per dataset.** The test periods cover 392 days for M5 and 196 days for Rossmann. A different period, for example one containing a structural break such as the COVID-19 pandemic, could change the conclusions.
- **Tuning budget.** Fifteen tuning trials per network is a small budget. Larger searches might improve the networks, although @tetko2024 suggests that the gains from extensive tuning are often small.
- **Interval guarantees.** Split conformal intervals assume that errors in the test period resemble those in the calibration period. With five calibration windows, the estimated quantiles are themselves uncertain, and the guarantee does not hold under distribution shift [@schlembach2025]. For the networks, the calibration windows are also the windows used to select the hyperparameters, which may make their intervals slightly too narrow.
- **Energy estimate.** Energy was estimated from runtime and the processor's rated power rather than measured, so it is an approximation suitable for comparing models, not an absolute figure.
- **No user evidence.** Without the user study, there is no evidence yet about whether the dashboard helps planners make better decisions.

## Ethical, Social and Sustainability Considerations {#sec:ethics}

The project used public, anonymised retail data at store level. No personal data were processed, and the Kaggle files were used for research only and are not redistributed with the code. The user study involves human participants. It has ethical approval and will follow the consent and data-handling commitments of the proposal ({app:G}). No participant data have been collected so far.

The social effects of forecasting depend on how forecasts are used. Forecasts inform orders and staff rosters, so systematic errors can lead to waste or to shortages, and automated recommendations can displace the judgement of experienced staff [@winkler2023; @wang2026]. The dashboard was therefore designed to support rather than replace planners. It shows uncertainty and bias alongside the forecast, explains each planning indicator in words and keeps the user in control of the final decision [@cheong2024]. Promotions illustrate the wider effect of retail decisions: they raise sales, but they can also increase household food waste [@gravert2025]. A forecasting system that makes promotions more profitable without considering waste would serve the retailer but not necessarily society.

Sustainability was treated as part of the evaluation rather than as an afterthought. Training and tuning time were measured for every model and converted into estimated energy, so that any accuracy gain of the networks can be weighed against its computational cost [@tabbakh2024; @rafat2023]. The same reasoning motivated the small tuning budget and the decision to keep model parameters fixed between forecast origins [@zanotti2026].

Finally, the project has a global dimension. The data come from retailers in the United States and Germany. Calendar effects, promotion practices and the availability of data differ between countries, so a framework that relies on known-in-advance calendar and promotion information would need local calendars and local validation before it is used elsewhere. The approach is, however, open and inexpensive: it runs on a laptop without a graphics processor, which makes it accessible to smaller retailers and to organisations with limited computing resources.
