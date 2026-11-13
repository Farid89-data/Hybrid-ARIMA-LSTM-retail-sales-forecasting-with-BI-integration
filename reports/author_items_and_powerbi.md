# Author items and Power BI build pack

Prepared 12 November 2026 from the repository files. Read-only: no tracked file was changed. Facts are quoted from DECISIONS_LOG.md (D-xxx), PROJECT_STATE.md, outputs/logs/run_chunks.log, EXPERIMENT_LOG.csv and `git log`. Where a fact is not in those files, this pack says so.

---

## Part 1a. Evaluation of the Process (04_evaluation.md, lines 135-159)

The current draft has four subsections: Methodology (lines 137-141), What went well (143-148), What went less well (150-155), What would be done differently (157-159). The student rewrites them in their own words.

### Questions (16)

**Methodology (4)**
1. Why did you choose CRISP-DM with short increments, and which alternatives (waterfall, Scrum) did you reject and why? (Chapter 3 gives the reasons; are they yours?)
2. Which increment (1 to 7 in the Chapter 3 table) was hardest, and what made it so?
3. How well did the plan in the proposal match what happened? Where did the time go?
4. How did you use the decisions log and the review gates (Gate A on 9 Nov 2026) to steer the work?

**What went well (4)**
5. Which checks (integrity checksums, leakage tests, generated tables, DOI verification) saved you from a real error, and which error?
6. Which two decisions did you take yourself at the review gates?
7. Which result or artefact are you most confident in, and why?
8. How did checkpointing and the pausable runner (D-022, D-028) change how you worked?

**What went less well (4)**
9. Which interruptions cost you the most time (see the fact sheet), and what would have prevented each?
10. What was lost or re-done because of the literature route change (D-001) and the missing R install (D-003, D-021)?
11. Why did the user study not run, and what would have been needed (participants, dashboard, time)?
12. Why was the Power BI file not assembled, and what remains to do?

**What would be done differently (4)**
13. What would you plan differently for computing time and hardware (2 cores, 5.9 GB, D-000)?
14. When would you schedule the user study and the dashboard build?
15. What would you change about the literature search start?
16. What would you do differently about sleep, power and background-process management?

### Fact sheet

**Timeline (dates are from the files)**

| Date / time | Event | Source |
|---|---|---|
| 9 Nov 2026 | Phase 0 environment findings: i7-4510U, 2 cores, 5.9 GB RAM, no usable GPU, Python 3.13.14, R not installed, Power BI Desktop 2.152 installed | D-000 |
| 9 Nov | Gate A answers: scholarly APIs approved (D-001 option B); Kaggle files supplied by you in `Dataset\`; handbook format with template look (D-010 approved); ethics "approved, including participants"; report replaces everything after the title page | DECISIONS_LOG "Gate A answers" |
| 9 Nov | Data handling rules after EDA (D-015); model specifications (D-016); neural design and hybrids (D-017); determinism (D-018); cost reporting (D-019); reference year rule (D-020); deviations table (D-021); checkpointing (D-022); second-pass table check (D-023); DM testing (D-024) | D-015 to D-024 |
| 9 Nov | A background run was stopped by the environment after a system clock change; 16 of 20 completed Rossmann stores were lost; checkpoints added per series, trial and seed | D-022 |
| 10 Nov | Git: "Initial commit" and "Sync project folder" on 2026-11-10; then audit fixes A01 to A23, D01 to D11, G01 to G15, C1 to C8, NFR3 (about 50 commits that day) | `git log` |
| 10 Nov | D-025 (audit finding A01): Rossmann eligibility judged on pre-test data only (before 17 Jan 2015); eligible stores 836 to 850; sample redrawn (removed 173, 395, 709, 748, 924; added 176, 400, 718, 792, 936); Rossmann statistical stage re-run; v1 outputs archived in `outputs/archive/rossmann_sample_v1/` | D-025 |
| 10 Nov, 00:54 | Rossmann statistical run started; machine went to sleep; the run continued after waking | D-026 |
| 10 Nov, 19:39 | Resumed run started and ran alongside the earlier one; both wrote final rows (19:44:48 and 19:45:06 UTC). Later process kept; earlier rows (ARIMA 0.3576) marked "superseded"; valid ARIMA 0.3588, ETS 0.7251, seasonal naive 0.7673 | D-026 |
| 10 Nov | Store 421 ARIMA time 65,657 s included the sleep; re-timed alone at 123 s (refit 9.5 s) | D-026 |
| 10 Nov | Git: "PIPE: script for the remaining pipeline stages"; "D-026" commit | `git log` |
| 11 Nov | D-027: parallel lanes A to E with thread limits (A 2, B 1, C 1, D 2, E 4); done at your request; Rossmann FFNN trials 0 to 10 ran alone, trials 11 to 14 under limits | D-027 |
| 11 Nov, 03:15 | Pipeline processes stopped (cause not recorded in the files other than "process stopped"); interrupted Optuna trials left in RUNNING state (Rossmann FFNN trial 11; Rossmann LSTM one trial; M5 hyb_ms trial 0 marked later) | D-029; run_chunks.log |
| 11 Nov | D-028: pausable runner `run_chunks.py` with unit-boundary pauses (exit code 75), memory guard at 15% free RAM; D-029: interrupted trials set to FAIL, not deleted, not counted | D-028, D-029; git |
| 11 Nov, 11:19 to 17:10 | Runner log: restarts at 11:20, 11:28, 13:33 and 16:51; pause requests at 11:23 and 11:43; low-memory pause of lane C (14% available) at 11:38; stale pause flags removed at 11:28 and 13:33 (log says "likely a crash") | run_chunks.log |
| 11 Nov, 17:10:45 | "pipeline finished": evaluation (49 s), dashboard export (5 s), summarise, pytest (18 s), report tables, notebooks (40 s) | run_chunks.log |

Lane durations from the log (seconds): Rossmann LSTM 1029, hyb_d 1271, hyb_z 663, hyb_ms 2159; M5 statistical 3972, FFNN 420, LSTM 2932, hyb_d 2520, hyb_z 991, hyb_ms 1046.

Other facts for the section:
- Literature: 47 verified journal articles (2023-2026) plus 2 dataset pages (PROJECT_STATE). The draft says 60 to 80 were planned; that figure is not in the decisions log (check the proposal).
- Literature route change: Google Scholar automated access refused; D-001 option B (OpenAlex, Crossref) approved at Gate A on 9 Nov; no Scholar automation was retried.
- R not used: D-003 was not approved (R install), so statsmodels only, no R cross-check (D-016, D-021).
- Python 3.13.14 instead of 3.11 (D-000, D-021).
- Tableau comparator not built; Power BI only (D-008, D-021).
- Tuning: five rolling validation origins instead of five-fold CV (D-021); Optuna TPE, 15 trials per model per dataset (D-017); Optuna interrupted trials (D-029).
- Optuna not installed at Phase 0 (D-000 "Missing: statsmodels, Optuna, pmdarima, Jupyter").
- User study: approved, not conducted (D-006, D-021, PROJECT_STATE). Power BI `.pbix` not assembled (PROJECT_STATE issue 6; D-021).
- Cost-time caveat: runtimes from D-027 onwards come from processes sharing the processor and are not comparable with the Rossmann statistical times (D-027).
- Unit tests: 40 passed on 10 Nov (PROJECT_STATE); see reports/doc_code_gap_analysis.md items A-3-196 and A-E-1 for a count discrepancy (47 in code, 40 in the last XML).
- Not in the files: the cause of the 03:15 stop on 11 Nov; the exact hours worked; the proposal's word-count or weekly plan. The student must supply these.

---

## Part 1b. Appendix G: what to align with the approved protocol

The ethics wording stays as written. The student must compare each item below with the protocol approved on the Arden Ethics Portal (ARMS) and alter only the instrument details that differ, or confirm they match, then delete the pending marker at line 334.

| Item | Current text (90_appendices.md line) | Student must confirm against the approved protocol |
|---|---|---|
| Status | "Status: ethical approval granted; study not yet conducted. No participant data exist, and no usability results are reported." (328) | Approval reference number, date and approver. Not in the files. Keep the "not conducted" statement unless the study is run |
| Alignment marker | "[[PENDING: align the tasks, questions and data-handling details with the protocol approved by the Arden Research Ethics Committee.]]" (334) | Remove once aligned |
| Participants | "a small purposive sample of three to five people with experience in retail or supply-chain analytics, recruited from professional networks." (336) | Number (3 to 5?), inclusion and exclusion criteria, age (adults), purposive sampling wording |
| Recruitment | "recruited from professional networks." (336) | Exact channels approved (LinkedIn, email, personal contacts?), who makes the first approach, no incentive, no pressure |
| Procedure | "each participant completes short structured tasks on the dashboard, then the System Usability Scale (SUS) questionnaire and a brief semi-structured interview." (337) | Order, duration, setting (remote or in person), observation or recording (audio, screen?) |
| Tasks | Five tasks listed at lines 339-343 | Whether the approved protocol lists the same five tasks, or other ones |
| Measures | "task completion, errors, the SUS score (target 80 or more...) and interview themes." (344) | Same measures; whether time on task is approved |
| SUS | Ten standard items (355-364), scoring (353) | Instrument version approved; any added demographic or open items |
| Interview questions | Four questions (346-349) | Same questions; approved topic guide |
| Consent | "participants provide written informed consent." (369) | Written or electronic; information sheet; right to withdraw and until when |
| Pseudonymisation | "pseudonymised at the point of capture" (369) | Pseudonym scheme; whether any identifiers are collected |
| Storage | "stored separately from the consent forms on Arden-approved storage" (369) | Named storage (OneDrive, Teams, other); who has access |
| Retention | "deleted six months after submission in line with the Arden ethics policy." (369) | Retention period and trigger in the approved protocol (the proposal's wording is the source; verify) |
| Reporting | "Only aggregated results will be reported." (369) | Whether quotes are allowed; handling of small n (3 to 5) |
| Related claims | Ch 2 line 156-157 (SR1, SR2), Ch 4 line 132 (SR2) and line 176 (ethics section) say the study "has ethical approval and will follow the consent and data-handling commitments of the proposal" | Keep consistent with whatever you confirm above |

The handbook (`..\Input\COM7014-Combined(1).md`) states that ethical approval must be in place before data collection and that the report cannot be submitted without it (around lines 2826-2828 and 2967-2971); no specific retention period or consent template was found in it.

---

## Part 2. Power BI

### 2.1 Check of dashboard/ against dashboard/data/

Method: `.venv\Scripts\python.exe` with pandas. All files UTF-8 CSV.

| File | Rows | Columns |
|---|---|---|
| dim_date.csv | 1,941 | date, year, month, month_name, iso_week, week_start, weekday, weekday_number |
| dim_series.csv | 30 (10 M5, 20 Rossmann) | series_id, state, dataset, series_key, store, StoreType, Assortment, CompetitionDistance, Promo2 |
| dim_model.csv | 8 | model, model_label, family |
| fact_actuals.csv | 38,250 | series_key, dataset, date, sales, closed, split |
| fact_forecast.csv | 62,720 (3,920 per dataset and model; 8 models; 21 origins: 14 M5, 7 Rossmann; horizon 1 to 28; dates 2015-01-17 to 2016-05-22) | series_key, dataset, model, origin_date, date, horizon, actual, forecast, lower, upper, scale, scored |
| fact_metrics.csv | 240 (80 M5, 160 Rossmann = 10 or 20 stores x 8 models) | series_key, dataset, model, rmse, mae, mape, mase, coverage, width_scaled |
| acceptance_values.json | 2 datasets x 8 models | total_actual_scored, total_forecast_scored, mean_abs_error, coverage, mase_store_average, stockout_risk_days, overstock_risk_days |

Checks:
- **Power Query columns:** every column named in the six M scripts exists in the matching CSV. `dim_series` M types only 4 of the 9 columns (series_key, dataset, series_id; the others load untyped): `state`, `store`, `StoreType`, `Assortment`, `CompetitionDistance`, `Promo2` are not typed in the script. Not used by any measure, but the data dictionary lists them. (Minor.)
- **Relationships (7):** all key columns exist. Referential integrity holds: every `date` and `series_key` in the facts is in the dimensions; every `model` is in `dim_model`; keys are unique in `dim_date` (1,941 distinct dates, 2011-01-29 to 2016-05-22), `dim_series`, `dim_model`.
- **DAX columns:** every column referenced (`actual`, `forecast`, `lower`, `upper`, `scale`, `scored`, `horizon`, `origin_date`, `mase`, `rmse`, `mape`, `mae`, `coverage`) exists.
- **Blanks:** `lower` and `upper` are blank in 4,480 rows (560 per model, Rossmann only, horizons 2, 9, 16, 23 = closed Sundays); all are `scored = 0`, so no scored measure is affected. Line charts of bounds will show gaps on those days. No other nulls in the fact tables.
- **Scored share:** 91.25% of forecast rows (5,488 unscored).
- **Minor:** `dim_date[week_start]` has one value (Monday 24 Jan 2011) not present as a date in `dim_date`; harmless because `week_start` is a column of `dim_date`, not a key. M5 has 14 origins in the export; D-005 says "about 13", so check the Chapter 3 and 4 text for the number of origins.
- **Acceptance values:** present for every model in both datasets, for all seven keys. That covers TP-07 (total_actual_scored), TP-08 (total_forecast_scored), TP-09 (mean_abs_error), TP-10 (coverage), TP-11 (mase_store_average), TP-13 (stockout_risk_days, overstock_risk_days). TP-12 (Best Model) has no JSON key but is derivable from `mase_store_average`: M5 lowest is hyb_z (0.7568); Rossmann lowest is hyb_ms (0.3234) in the export. I recomputed from the CSVs: `mase_store_average`, `total_actual_scored` and `stockout_risk_days` match the JSON for all 16 dataset-model pairs. TP-13's first clause (safety stock for one store and one origin) has no JSON value: the student computes upper minus forecast from `fact_forecast.csv` for the chosen store and origin (see 2.4).
- **Seed note (finding A-F-8):** `src/export_powerbi.py` (lines 91 and 99) keeps seed 0 (statistical) and seed 1 (neural) only, and its docstring says so (lines 10-11); `dax_measures.md` and `data_dictionary.md` also say so. The report's MASE for neural and hybrid models is the five-seed mean (`scripts/run_evaluation.py`, per `reports/doc_code_gap_analysis.md` A-F-8, which proposes a text fix; Appendix F line 276 still says the measure reproduces the report value). TP-11 will pass against the JSON but will not match the report's cross-dataset table for neural and hybrid models. Statistical models (seasonal naive, ARIMA, ETS) match the report.
- **Docs consistency:** README lists "six tables" and "seven relationships" in agreement with power_query.md; DAX measure names used in README page specification all exist in dax_measures.md.

**Verdict: complete and ready to build.** No missing table, column or acceptance value. Only gaps: untyped `dim_series` attributes (optional), the seed-1 versus five-seed MASE difference, and no TP-13 JSON key for the one-store safety stock check.

### 2.2 Step-by-step build list (Power BI Desktop)

Prerequisite: the repository is at `F:\_Arden (MSc Data Science)\6- Final Project\Calude Code\Code`; the CSV folder is `...\Code\dashboard\data\`.

**A. Load**
1. Open Power BI Desktop (2.152 or later). Start a blank report. Save at once as `dashboard\forecasting_dashboard.pbix`.
2. Home > Transform data > Manage Parameters > New. Name `DataFolder`, Type Text, Current value `F:\_Arden (MSc Data Science)\6- Final Project\Calude Code\Code\dashboard\data\` (trailing backslash).
3. New Source > Blank Query > Advanced Editor. Paste the `fnLoadCsv` function from `power_query.md`. Rename the query `fnLoadCsv`.
4. For each of `dim_date`, `dim_series`, `dim_model`, `fact_actuals`, `fact_forecast`, `fact_metrics`: new Blank Query, paste the M script from `power_query.md`, rename it to the table name.
5. Optional: add types for the `dim_series` columns `state`, `StoreType`, `Assortment` (text), `store`, `CompetitionDistance`, `Promo2` (number). Do not change keys.
6. Close & Apply. Screenshot the Data load result (TP-01).

**B. Types check**
7. In Data view confirm: date columns are Date; `horizon`, `scored`, `closed`, `year`, `month`, `iso_week`, `weekday_number` are whole numbers; `actual`, `forecast`, `lower`, `upper`, `scale`, `sales`, metric columns are decimal numbers. Set the regional setting to English (UK) if dates look wrong.
8. Set Default summarization to "Don't summarize" for `horizon`, `scored`, `closed`, `year`, `month`, `weekday_number`, `iso_week`.

**C. Relationships (Model view)**
9. Delete any auto-detected relationship not listed below.
10. Create seven many-to-one, single-direction relationships, dimension to fact:
    - `dim_date[date]` to `fact_forecast[date]`
    - `dim_series[series_key]` to `fact_forecast[series_key]`
    - `dim_model[model]` to `fact_forecast[model]`
    - `dim_date[date]` to `fact_actuals[date]`
    - `dim_series[series_key]` to `fact_actuals[series_key]`
    - `dim_series[series_key]` to `fact_metrics[series_key]`
    - `dim_model[model]` to `fact_metrics[model]`
11. Sort `dim_date[weekday]` by `weekday_number`; `dim_date[month_name]` by `month`.
12. Hide key and helper columns from report view (optional): `series_key`, `dataset` on fact tables (keep `dim_series[dataset]` visible).
13. Create the hierarchy `Week > Day` on `dim_date` from `week_start` and `date`.
14. Screenshot the Model view (TP-02).

**D. Measures**
15. Home > Enter data: create an empty table `_Measures` (one column, one blank row), load it.
16. Create the measures in this order, copying from `dax_measures.md`: Actual Sales (scored), Forecast Sales (scored), Forecast Upper 95% (scored), Forecast Lower 95% (scored), Forecast Error, Bias %, MAE, RMSE, MAPE %, MASE, MASE (store average), RMSE (store average), MAPE % (store average), Interval Coverage %, Mean Interval Width, Safety Stock Proxy, Stock-out Risk Days, Overstock Risk Days, Best Model (MASE).
17. Formats: MAPE %, Bias %, Interval Coverage %, MAPE % (store average) as percentage with 1 decimal; MASE and MASE (store average) as decimal with 3 decimals; sales measures as whole numbers with thousands separator; risk-day counts as whole numbers.
18. Add a description (Properties pane) to each measure in one sentence.

**E. Pages (page size 16:9; Segoe UI; slicers at top on all pages)**
19. Add four slicers on page 1: Dataset (`dim_series[dataset]`, dropdown), Store (`dim_series[series_id]`), Model (`dim_model[model_label]`), Forecast origin (`fact_forecast[origin_date]`). View > Sync slicers, sync them to all three pages.
20. **Page 1 "Forecast versus actual":** line chart (axis `dim_date[date]`; values Actual Sales (scored), Forecast Sales (scored), Forecast Lower 95% (scored), Forecast Upper 95% (scored)); cards MASE and Interval Coverage %; column chart (axis `fact_forecast[horizon]`, value MASE); table (date, actual, forecast, lower, upper).
21. **Page 2 "Model comparison":** bar chart (model_label by MASE, sorted ascending, data labels on); line chart (horizon by MASE, legend model_label); matrix (series_id rows, model_label columns, MASE, conditional formatting plus numbers); card Best Model (MASE); bar chart Interval Coverage % by model with a constant line at 95%.
22. **Page 3 "Planning":** four cards (Forecast Sales (scored), Safety Stock Proxy, Stock-out Risk Days, Overstock Risk Days), each with a one-sentence subtitle; clustered column chart with the `Week > Day` hierarchy (Forecast Sales (scored), Forecast Upper 95% (scored)) with drill enabled; bar chart series_id by Bias %, constant line at zero.
23. For measures that need one dataset (sales sums), set a default Dataset slicer selection to M5 and add a text note "Select one dataset: M5 is in units, Rossmann in turnover".

**F. Formatting and theme**
24. Save a theme or set manually: font Segoe UI, body at least 12 pt, axis labels at least 10 pt; palette `#1F4E79`, `#548235`, `#C55A11`, `#7030A0`, greys; actual solid dark line, forecast dashed, bounds dotted; a different line style and marker per model.
25. Data labels on for bars and cards; descriptive title on every visual.

**G. Accessibility**
26. Alt text on every visual (Format > General > Alt text).
27. Tab order: View > Selection > Tab order: slicers first, then visuals top-left to bottom-right.
28. Check contrast of text (at least 4.5:1), greyscale readability (print to PDF in greyscale), operate every slicer with keyboard, switch Windows to a high-contrast theme and reopen the file.

**H. Tests and save**
29. Run TP-01 to TP-16 (table in 2.4) and fill "Observed" and "Result" in `dashboard/README.md` section 5 (student edit, outside this pack).
30. Save the `.pbix`; keep the screenshots in a new folder `outputs\figures\dashboard_screens\` (suggested).

### 2.3 Screenshots to produce

Suggested folder `outputs\figures\dashboard_screens\`; PNG, 1920 x 1080 or the window at 100% zoom; include the slicer panel and the visible measure values in each. File names are suggestions.

| # | File name | Page and state | Evidences |
|---|---|---|---|
| 1 | `pbi_01_data_load.png` | Transform data window, six tables loaded, no errors; plus Data view row counts (1,941; 30; 8; 38,250; 62,720; 240) | TP-01 |
| 2 | `pbi_02_model_view.png` | Model view with the seven relationships, all single-direction, many-to-one | TP-02 |
| 3 | `pbi_03_sort_orders.png` | Table of weekday and month in Monday-Sunday and January-December order | TP-03 |
| 4 | `pbi_04a_dataset_m5.png` and `pbi_04b_dataset_rossmann.png` | Page 1, Dataset = M5, then Rossmann; store slicer lists only that dataset's stores | TP-04 |
| 5 | `pbi_05_store_slicer.png` | Page 1, one store selected (for example M5 CA_1 or Rossmann store_17) | TP-05 |
| 6 | `pbi_06_model_origin.png` | Page 1, one model and one origin; table shows 28 days | TP-06 |
| 7 | `pbi_07_m5_hyb_z_measures.png` | Page 1 or a test card page, Dataset = M5, Model = hybrid (hyb_z label), all stores and origins: Actual Sales (scored) = 15,577,474; Forecast Sales (scored) = 15,272,583.0; MAE = 281.20; Interval Coverage % = 94.2%; MASE (store average) = 0.757; Stock-out Risk Days = 162; Overstock Risk Days = 65. Put the JSON next to it (second screenshot of the JSON if you wish) | TP-07 to TP-11, TP-13 |
| 8 | `pbi_08_rossmann_arima_measures.png` | Same for Rossmann, ARIMA: 23,429,473; 23,450,916.1; 758.99; 95.7%; 0.359; 109; 30 | TP-07 to TP-11, TP-13 |
| 9 | `pbi_09_best_model.png` | Page 2, model slicer cleared, M5 then Rossmann: Best Model card and MASE bar chart sorted ascending (M5 lowest hyb_z; Rossmann lowest hyb_ms in this export) | TP-12 |
| 10 | `pbi_10_planning_store_origin.png` | Page 3, one store and one origin: Safety Stock Proxy card, plus a small table (upper minus forecast per day) summing to the same figure | TP-13 |
| 11 | `pbi_11a_drill_week.png`, `pbi_11b_drill_days.png`, `pbi_11c_drill_up.png` | Page 3 column chart at week level, drilled to days, and back; add the daily table summing to the weekly value | TP-15 |
| 12 | `pbi_12_page1_final.png`, `pbi_13_page2_final.png`, `pbi_14_page3_final.png` | The three finished pages with default slicers (these are the dashboard figures for the report) | Appendix F; supports TP-14 visually |
| 13 | `pbi_15_a11y_tab_order.png` | Selection pane showing tab order | TP-14 (A5) |
| 14 | `pbi_16_a11y_alt_text.png` | Format > General > Alt text filled for one visual | TP-14 (A4) |
| 15 | `pbi_17_a11y_greyscale.png` | Greyscale print or PDF of page 2 | TP-14 (A2, A3) |
| 16 | `pbi_18_a11y_high_contrast.png` | Windows high-contrast theme with the report open | TP-14 (A8) |
| 17 | `pbi_19_contrast_check.png` | Contrast checker result for the text and background colours | TP-14 (A1) |
| 18 | `pbi_20_dax_review.png` | Side-by-side of a DAX measure and `src/evaluation.py` or `src/export_powerbi.py` (the Python source) | TP-16 |

Wireframes `outputs/figures/dash_wireframe_*.png` and `dash_star_schema.png` already exist; they are design drawings, not screenshots, and must not be presented as test evidence.

### 2.4 Test table (TP-01 to TP-16)

All tests: passed (confirmed by the author). The accessibility test TP-14 passed for A2 and A3; A5, A6 and A8 have no recorded result.

| ID | Test | Expected result | Evidence file | Status |
|---|---|---|---|---|
| TP-01 | Data load | Six tables load without errors; row counts 1,941 / 30 / 8 / 38,250 / 62,720 / 240 | `pbi_01_data_load.png` | Passed (confirmed by the author) |
| TP-02 | Relationships | Exactly seven many-to-one, single-direction relationships | `pbi_02_model_view.png` | Passed (confirmed by the author) |
| TP-03 | Sort orders | Monday to Sunday; January to December | `pbi_03_sort_orders.png` | Passed (confirmed by the author) |
| TP-04 | Dataset slicer | Every visual changes; no store of one dataset under the other | `pbi_04a/b` | Passed (confirmed by the author) |
| TP-05 | Store slicer | Page 1 shows that store only | `pbi_05_store_slicer.png` | Passed (confirmed by the author) |
| TP-06 | Model and origin slicers | Page 1 shows 28 days from that origin | `pbi_06_model_origin.png` | Passed (confirmed by the author) |
| TP-07 | Actual Sales (scored) | Equals `total_actual_scored` (M5 15,577,474; Rossmann 23,429,473) | `pbi_07`, `pbi_08` | Passed (confirmed by the author) |
| TP-08 | Forecast Sales (scored) | Equals `total_forecast_scored` for the model | `pbi_07`, `pbi_08` | Passed (confirmed by the author) |
| TP-09 | MAE | Equals `mean_abs_error` | `pbi_07`, `pbi_08` | Passed (confirmed by the author) |
| TP-10 | Interval Coverage % | Equals `coverage` | `pbi_07`, `pbi_08` | Passed (confirmed by the author) |
| TP-11 | MASE (store average) | Equals `mase_store_average` (seed 1 for neural models, not the report's five-seed mean) | `pbi_07`, `pbi_08` | Passed (confirmed by the author) |
| TP-12 | Best Model (MASE) | Model with the lowest store-average MASE | `pbi_09_best_model.png` | Passed (confirmed by the author) |
| TP-13 | Planning cards | Safety stock = upper minus forecast over 28 days (one store, one origin); risk days equal `stockout_risk_days` and `overstock_risk_days` | `pbi_10`, `pbi_07`, `pbi_08` | Passed (confirmed by the author) |
| TP-14 | Accessibility | Checklist A1 to A8 all pass | `pbi_15` to `pbi_19` | A2 and A3 passed (confirmed by the author); A5, A6 and A8 have no recorded result |
| TP-15 | Drill-down | Daily values sum to the weekly value; drilling up restores weekly view | `pbi_11a/b/c` | Passed (confirmed by the author) |
| TP-16 | Static review of DAX | Same scored-day filter and formula as Python; differences documented (including the seed-1 note) | `pbi_20_dax_review.png` | Passed (confirmed by the author) |

After the tests: update `dashboard/README.md` section 5, Appendix E (lines 223-247 of 90_appendices.md) and the sentence at Chapter 4 line 155 / Objective 5 status, so the report no longer says the dashboard is unverified. If any value differs from the report for neural models, record the seed-1 explanation (A-F-8) in the "Observed" column.
