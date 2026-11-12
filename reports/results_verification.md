# Results verification (read-only), 12 Nov 2026

Overall verdict: **OK, no leakage or scoring bug found; 4 WARNs.** No STOP.

## 1. Completion

| Item | Evidence | Status |
|---|---|---|
| Runner lanes A-E | `outputs/logs/run_chunks.log` ends "17:10:45 pipeline finished"; `outputs/state/status.json` A-E "done", errors {}; RESUME.md 188/188 units | OK |
| Non-zero exits | only exit 75 (pause at unit boundary): nn_m5_ffnn 11:39:21, nn_rossmann_lstm 11:44:01. Both later re-run with exit 0 | OK |
| Silent stops | lane A 11:20:38, lane B stat_m5 11:30:32 and lane D nn_m5_hyb_ms 16:35:20 have no "finished" line; the runner restarted ("stale pause flags ... likely a crash", or a new runner at 16:51:22). All resumed from their checkpoints and ended with exit 0 | WARN (log gap) |
| EXPERIMENT_LOG `pipeline` rows | 20 rows; the last run of each stage has exit 0. The Rossmann statistical stage ran before the runner existed, so it has no pipeline row (D-026) | OK |
| Final rows | snaive/ets/arima: 1 each (m5); 2 each (rossmann, 1 marked superseded, D-026). ffnn, lstm, hyb_d, hyb_z, hyb_ms: seeds 1-5 for both datasets | OK |
| Test forecasts | every network has 5 seeds in `*_all_test_with_intervals.csv.gz`; the statistical models have seed 0 | OK |
| Optuna (read-only sqlite) | 8 studies, each with 15 COMPLETE. FAIL 1 in m5_hyb_ms, rossmann_ffnn and rossmann_lstm (D-029) | OK |
| hyb_z validation | `*_hyb_z_validation.csv.gz`, 1 tuning row per dataset (reuses the hyb_d parameters) | OK |
| Lane E done markers | evaluation, export_dashboard, summarise_results, pytest, make_report_tables, make_notebooks: all exit 0 | OK |
| pytest | `outputs/tests/pytest_results.xml`: tests=57, failures=0, errors=0, skipped=0 | OK |
| Notebooks | 9 notebooks; every code cell executed; 0 error outputs | OK |
| Figures | 20 `res_*.png` (10 per dataset) | OK |

## 2. Sanity checks

- **(a) Leakage: OK.**
  - No model has an implausibly low error. The lowest MAPE is 6.996% (m5 hyb_z). Per-series MASE is never below 0.228.
  - The best hybrid beats ARIMA by 11.0% (m5) and 10.8% (rossmann).
  - The low Rossmann MASE values (about 0.32-0.36) fit the promo-driven seasonal-naive scale.
  - The MASE scale uses only data before `test_start` (`src/experiment.py:94`, `src/preprocessing.py:155-171`).
  - Anomaly flags are causal (`src/preprocessing.py:75-97`).
  - Training windows end before the cutoff (`src/feature_engineering.py:50-55`). Past inputs are `[o-L, o)` (`:96`).
  - The hybrid residual scaler is fitted on data before the cutoff (`src/experiment.py:300`). ARIMA is refitted on `y[:test_start]` (`:203`).
  - Conformal calibration uses only validation-stage rows (max date 2015-04-26 for m5, 2015-01-16 for rossmann).
  - The primary hybrid is chosen by validation MASE (`evaluation_summary.json`).
- **(b) Hybrids against their components: OK.**
  - m5: hyb_z and hyb_d beat both ARIMA and LSTM. hyb_ms beats LSTM but is 1.11% worse than ARIMA.
  - rossmann: all three hybrids are better than ARIMA and LSTM by MASE. Only hyb_z vs ARIMA is significant (see section 3).
- **(c) Interval coverage: OK.** All conformal coverages are between 0.903 (m5 LSTM) and 0.963 (rossmann LSTM). None is below 0.85 or above 0.99. The Gaussian interval for rossmann ETS reaches 0.989 with width 6.36, which is near the upper flag.
- **(d) NaN / empty tables: OK.**
  - The only NaNs are structural:
    - native/Gaussian interval columns for non-ARIMA/ETS models;
    - seed s.d. for the statistical models;
    - validation coverage;
    - "Trials (interrupted)" = n/a for hyb_z.
  - `report_cost.csv` has all 16 rows with sensible values.
  - The Rossmann ARIMA time is corrected by the store-421 re-timing (71073.3 s - 65684.2 s + 132.8 s = 5522.0 s).
  - No paused or suspended time leaked into unit runtimes: the largest m5 ARIMA series takes 934 s (D-028 pauses happen only at unit boundaries).
  - Caveats:
    - Rossmann ARIMA times include contention from the duplicate process (D-026).
    - All later runtimes come from parallel lanes (D-027).
    - Rossmann FFNN trials 0-10 used default threading.
- **(e) Scored days: OK.** Every model and seed has the same number of scored rows: m5 3910 (391 days), rossmann 3244 (163 days).
- **(f) Test stage: OK.** `stage` is "test" for every row of `*_all_test_with_intervals.csv.gz`. The summary CSVs have no stage column; they are built from that file.
- **(g) Seed spread: OK.** Test MASE s.d. across seeds:

  | Model | m5 | rossmann |
  |---|---|---|
  | hyb_d | 0.0050 | 0.0025 |
  | hyb_z | 0.0085 | 0.0059 |
  | ffnn | 0.0176 | 0.0054 |
  | hyb_ms | 0.0226 | 0.0034 |
  | lstm | 0.0353 | 0.0094 |

  m5 LSTM ranges 1.0321-1.1156.
- **(h) DM tests: OK, but WARN on presentation.**
  - `*_dm_tests.csv`: the primary hybrid vs 7 models × 2 losses. Holm family = 7 per seed and loss (for example, m5 vs snaive: 3.5676e-14 × 7 = 2.4973e-13).
  - Sign: positive statistic means the hybrid is better (`scripts/run_evaluation.py:117-123`).
  - The ablation and the matrix use the all-pairs family (28 pairs, squared loss, mean statistic, median Holm p; `src/evaluation.py:120-174`).
  - The two families can disagree. Rossmann hyb_ms vs ARIMA (squared): median Holm p = 0.0443 in `rossmann_dm_tests.csv` but p_holm = 0.0638 in `rossmann_hybrid_ablation.csv`. State which one is reported.
  - "Series better/worse" uses unadjusted p < 0.05.
- **(i) `result_facts.json`: OK, with one WARN.**
  - Checked programmatically against `*_test_summary.csv`, `*_test_per_seed.csv`, `*_test_per_series.csv` and `*_mase_by_week.csv`: 0 mismatches. This covered all metrics, every pct change, the seed ranges, the ranking, the weekly MASE, the series counts (m5: 10/10/10/9; rossmann: 20/20/20/15) and the best-per-series counts.
  - WARN: `total_logged_runtime_hours` = 50.41 and `total_logged_energy_kwh` = 0.677 are inflated. They sum every EXPERIMENT_LOG row (`scripts/summarise_results.py:107-108`), which includes:
    - the superseded duplicate Rossmann statistical rows (19.7 h);
    - the sleep-inflated store-421 search (18.2 h);
    - the pipeline wall-clock rows (5.3 h, double counting).
  - The cost tables sum to 25,648.9 s = **7.12 h, about 0.107 kWh**.
  - These two keys are not used in the docbuild or the notebooks. Do not quote them.

Other WARNs:
- `src/tuning_cleanup.py:17` hard-codes the reason "process stopped 11 Nov 2026 03:15". m5_hyb_ms trial 0 got this reason, but it actually ran 16:35:29-16:51:21.
- `report_cost.csv` gives hyb_z 12.1 min (m5) and 6.5 min (rossmann). These exclude the reused hyb_d search, which is in `tuning_incl_reused_seconds`: 1389.8 s (m5) and 1073.5 s (rossmann).
- The dashboard (`acceptance_values.json`, `fact_*`) uses seed 1 for the networks (documented in `src/export_powerbi.py:10`). Its MASE values therefore differ from the 5-seed means: for example, m5 ffnn is 0.8813 in the dashboard and 0.8637 in the summary.

## 3. Main results (test stage; MASE = per-store mean, then mean over seeds)

**M5** (`m5_test_summary.csv`; coverage and scaled width are conformal):

| Model | MASE | RMSE | MAPE % | Coverage | Width |
|---|---|---|---|---|---|
| hyb_z | 0.7458 | 371.30 | 7.00 | 0.9426 | 4.34 |
| hyb_d | 0.7979 | 397.68 | 7.48 | 0.9358 | 4.42 |
| arima | 0.8379 | 419.04 | 7.87 | 0.9358 | 4.82 |
| hyb_ms | 0.8472 | 412.93 | 7.71 | 0.9288 | 4.85 |
| ffnn | 0.8637 | 417.02 | 7.77 | 0.9285 | 4.72 |
| ets | 1.0368 | 530.99 | 10.30 | 0.9261 | 5.16 |
| lstm | 1.0814 | 496.72 | 9.22 | 0.9030 | 5.70 |
| snaive | 1.1960 | 620.29 | 11.92 | 0.9399 | 7.34 |

**Rossmann** (`rossmann_test_summary.csv`):

| Model | MASE | RMSE | MAPE % | Coverage | Width |
|---|---|---|---|---|---|
| hyb_ms | 0.3202 | 908.24 | 9.64 | 0.9400 | 2.07 |
| ffnn | 0.3279 | 907.85 | 9.93 | 0.9606 | 2.32 |
| hyb_z | 0.3369 | 972.16 | 10.15 | 0.9453 | 2.30 |
| hyb_d | 0.3520 | 1006.41 | 10.64 | 0.9496 | 2.42 |
| arima | 0.3588 | 1027.47 | 10.78 | 0.9571 | 2.64 |
| lstm | 0.3635 | 991.88 | 11.29 | 0.9629 | 2.47 |
| ets | 0.7251 | 1962.98 | 22.18 | 0.9257 | 4.32 |
| snaive | 0.7673 | 2209.21 | 23.98 | 0.9387 | 4.56 |

**Significance** (`*_dm_tests.csv`, Holm, 5 seeds):
- m5: hyb_z is significantly better than all 7 models, for both losses and in 5/5 seeds. Median Holm p ≤ 0.0011; the largest is vs hyb_d (squared).
- rossmann: hyb_ms is significantly better than snaive and ETS (5/5 seeds, both losses).
  - vs ARIMA: 3/5 seeds for both losses; median Holm p 0.0274 (absolute), 0.0443 (squared).
  - vs hyb_d: absolute 3/5 seeds, p 0.0339; squared 2/5 seeds, p 0.102.
  - vs FFNN, LSTM and hyb_z: not significant (0-1 of 5 seeds).
  - No comparison is significant in the opposite direction.

**Hybrid vs components** (`*_hybrid_ablation.csv`; squared loss, all-pairs Holm):

| Hybrid | m5 vs ARIMA | m5 vs LSTM | rossmann vs ARIMA | rossmann vs LSTM |
|---|---|---|---|---|
| hyb_d | -4.78%, p 0.018 | -26.2%, p 0.0086 | -1.89%, p 1.0 | -3.18%, p 1.0 |
| hyb_z | -10.99%, p 0.0022 | -31.0%, p 0.00085 | -6.10%, p 0.0124 | -7.33%, p 1.0 |
| hyb_ms | +1.11%, p 1.0 | -21.7%, p 0.0041 | -10.76%, p 0.064 | -11.93%, p 1.0 |

**Error by horizon** (`*_mase_by_week.csv`):
- m5: errors grow from week 1 to week 3 and dip slightly in week 4. hyb_z: 0.627, 0.735, 0.799, 0.822. ARIMA: 0.695, 0.831, 0.953, 0.874.
- rossmann: the models grow gently; hyb_ms is 0.301, 0.276, 0.354, 0.352. snaive alternates 0.947 / 0.458 / 1.116 / 0.570, which matches the fortnightly promo cycle.
- Median ARIMA error ratio (`evaluation_summary.json`):

  | Dataset | h1 | h28 |
  |---|---|---|
  | m5 | 0.693 | 1.092 |
  | rossmann | 0.655 | 1.130 |

**Cost** (`report_cost.csv`; total min / incl. ARIMA min / Wh):

| Model | M5 | Rossmann |
|---|---|---|
| ARIMA | 84.3 / 84.3 / 21.1 | 92.0 / 92.0 / 23.0 |
| ETS | 1.2 / 1.2 / 0.3 | 2.2 / 2.2 / 0.5 |
| FFNN | 11.7 / 11.7 / 2.9 | 12.9 / 12.9 / 3.2 |
| LSTM | 47.8 / 47.8 / 12.0 | 44.3 / 44.3 / 11.1 |
| hyb_d | 41.1 / 125.4 / 10.3 | 20.3 / 112.3 / 5.1 |
| hyb_ms | 16.4 / 100.6 / 4.1 | 34.8 / 126.8 / 8.7 |
| hyb_z | 12.1 / 96.3 / 3.0 | 6.5 / 98.5 / 1.6 |

Energy in kWh including ARIMA (`*_cost.csv`):

| Model | m5 | rossmann |
|---|---|---|
| hyb_z | 0.0241 | 0.0246 |
| hyb_ms | 0.0252 | 0.0317 |

Energy is estimated at 15 W. The Wh column excludes ARIMA. The times are from parallel lanes (D-027).
