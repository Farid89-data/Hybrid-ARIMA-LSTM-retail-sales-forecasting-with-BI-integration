# Decisions Log

Each entry records:

- the decision and the alternatives considered
- the justification (technical or academic)
- a **plain-language rationale** you can use in a viva
- the status

**Status values:**

- **PROPOSED**: awaiting your approval
- **APPROVED**: approved by you, with the date
- **REJECTED**
- **SUPERSEDED**

---

## D-000: Phase 0 environment findings (FACT, 9 Nov 2026)

| Item | Finding |
|---|---|
| Machine | Intel Core i7-4510U (2 cores / 4 threads, 2014), **5.9 GB RAM**. GPU: NVIDIA GeForce 840M, 2 GB. It is **not usable** by TensorFlow on native Windows, so all training is CPU-only |
| Python | 3.13.14 (Microsoft Store build). Installed: TensorFlow 2.21.0, Keras 3.15.0, pandas 3.0.0, NumPy 2.4.2, SciPy 1.17.0, scikit-learn 1.8.0, Matplotlib 3.10.8, Seaborn 0.13.2, pytest 9.0.2, python-docx 1.2.0, lxml 6.1.2, PyMuPDF 1.28.2, pywin32 312. **Missing:** statsmodels, Optuna, pmdarima, Jupyter |
| R | **Not installed** |
| Microsoft Word | 16.0 (build 16.0.20326.20232). COM automation works: a test PDF export of the proposal succeeded |
| LibreOffice, Pandoc | Not installed (not needed while Word is available) |
| Power BI Desktop | 2.152.1279.0 (March 2026), installed |
| Git | 2.52.0. Global identity: Farid Negahbani |
| Network | PyPI, CRAN, Crossref API, doi.org and the Kaggle web pages are reachable. **Google Scholar is not available to automated access** (see D-001) |
| Datasets | Not present in `Input\` |
| Skills | `academic-research-skills` v3.24.2 installed at user level (5 skills; see D-013). They become invocable as skills after a Claude Code restart; until then their files can still be read and followed |

## D-001: Literature discovery route (PROPOSED)

**Problem.** MP §8.1 requires discovery through Google Scholar only. An automated Scholar query returned a Google redirect rather than results. A follow-up attempt was **refused by the environment's safety policy as "bot-check circumvention"**. Scholar's terms also prohibit automated querying, so it will not be retried in any form.

**Options:**

- **(A) Recommended.** You run the prepared Scholar queries in your own browser (`Refrence\scholar_search_plan.md`) with "Since 2023" / custom range 2023-2026. You export the candidates as BibTeX or RIS (Scholar "Cite" → BibTeX/EndNote/RefMan, or "My library" → export all) into `Input\scholar_exports\`. I then verify every record on its DOI or publisher page (reachable), screen it against MP §8.2 and build the ledger. Discovery stays 100% Google Scholar.
- **(B) Supplement, needs explicit approval.** Allow a scholarly API (Crossref or OpenAlex) as a *secondary* discovery channel for gaps in the coverage map, with each hit cross-checked on Scholar by you. This deviates from MP §8.1.

**Plain-language rationale:** the university-grade route is to search Scholar as a human, as any student would. I do the heavy verification afterwards.

## D-002: Datasets and sampling (PROPOSED)

**Recommendation:** use **both** datasets as separate, identically processed experiments.

- **M5 (primary):** the **10 store-level** daily unit-sales series (sum of all items per store), 1,941 days.
  - Item-level series are excluded. They are highly intermittent with many zero days, where ARIMA assumptions and MAPE break down.
  - Optional robustness set if time allows: 30 store x category series.
- **Rossmann (secondary, generalisability check):** a stratified random sample of **20 stores** across StoreType x Assortment, chosen from stores with a complete daily history (some stores have a known mid-2014 gap).
  - Closed days are structural zeros. The proposal is to model the sequence of **open trading days** and to evaluate on open days only. This matches the original competition, which ignored zero-sales days. To be confirmed in Phase 2 after EDA.
- Results are compared across datasets only through scale-free measures (MASE, ranks, Diebold-Mariano outcomes), never raw RMSE.

**Alternatives:**

- M5 only: simpler, but weaker generalisability.
- Rossmann only: shorter history (942 days) for the LSTM.
- Item-level M5: infeasible on a 2-core CPU and methodologically mismatched with ARIMA.

**Plain-language rationale:** store-level sales are what inventory and revenue planners act on. They are long and regular enough for ARIMA and an LSTM to be compared fairly, and a 2-core laptop can finish the experiments.

## D-003: Software environment (PROPOSED)

**Recommendation:**

- Install **Python 3.11** (via `winget`, user-level) and create `Code\.venv` with pinned versions. This matches the proposal ("Python 3.11") and CI.
- Install **R 4.x** with `forecast` and `fable`, as the proposal specifies.

**Alternative:** stay on Python 3.13 and drop R, documenting the deviation.

**Plain-language rationale:** sticking to the stack you promised in the proposal avoids an examiner question about why it changed.

## D-004: Canonical implementation for reported results (PROPOSED)

**Recommendation:**

- **Python is canonical** for all reported numbers: statsmodels/pmdarima for ARIMA and ETS, TensorFlow/Keras for the networks.
- **R `forecast::auto.arima`/`ets` is an independent cross-check** of selected orders and accuracy on the same splits, reported as an agreement table in an appendix.

**Justification:** the hybrid model needs ARIMA residuals inside the same rolling-origin loop as the LSTM. Splitting the pipeline across languages raises the leakage and alignment risk.

**Plain-language rationale:** one pipeline produces every number. R is used only to confirm that the statistical models agree.

## D-005: Forecast horizon and evaluation design (PROPOSED, detailed at Gate B)

- **Horizon:** h = 28 days, the M5 official horizon (four weekly cycles, a typical replenishment window).
- **Test period:** the final 20% of each series, as in the proposal, evaluated with **non-overlapping 28-day rolling origins**:
  - about 13 origins for M5
  - about 6 origins for Rossmann open days
- **Tuning:** five-fold expanding-window rolling-origin cross-validation inside the training period, as in the proposal.
- **No random splits**; scalers and ARIMA are fitted on training data only.
- Recursive vs direct multi-step forecasting for the residual LSTM is to be tested empirically (MP §6.1).

**Plain-language rationale:** the models are always tested on future weeks they have never seen, exactly as a planner would use them.

## D-006: Ethics and user study (PENDING your status)

| Ethics status | Plan |
|---|---|
| Approved, including participants | Run the SUS plus interview study with real participants only |
| Not approved, or approved for secondary data only | No participants. Deliver functional, heuristic and accessibility evaluation of the dashboard, plus protocol, SUS instrument and consent materials marked "not yet conducted" |

## D-007: Research questions (PROPOSED: the proposal has none, but the handbook's Critical Evaluation expects them)

- **RQ1.** To what extent does a hybrid ARIMA-LSTM residual-learning model improve 28-day-ahead point accuracy (RMSE, MAPE, MASE) over ARIMA, ETS, a feed-forward network, a standalone LSTM and a seasonal naive baseline on store-level daily retail sales?
- **RQ2.** Are the accuracy differences statistically significant under the Diebold-Mariano test with the Harvey-Leybourne-Newbold small-sample correction, and do they hold across forecast horizons and both datasets?
- **RQ3.** How well calibrated are the models' 95% prediction intervals, and what accuracy is gained per unit of computational cost (training time, estimated energy)?
- **RQ4.** How can the forecasts be integrated into a Power BI dashboard that meets the functional, non-functional and accessibility requirements for inventory and revenue planning?

## D-008: BI tool (PROPOSED)

**Recommendation:** Power BI only (Tableau dropped).

**Build path, to be confirmed at Phase 7:**

1. Generate a text-based **Power BI Project (PBIP/TMDL)** plus CSV extracts and DAX.
2. You open the project in Power BI Desktop 2.152 and save it as `.pbix`.
3. Functional tests are run and screenshotted. Until tested, the dashboard is described as "specified, not yet verified".

**Fallback:** CSVs, DAX and M code, a step-by-step build guide and wireframes.

## D-009: Outline and word budget (PROPOSED; the word-count policy is still needed)

| Chapter | Words | Main sections |
|---|---|---|
| Abstract | ~300 | Written last from actual results |
| 1 Project Framing | ~1,200 | Background; problem and rationale; aim; objectives; RQs; scope; contribution; report structure |
| 2 Fact Finding | ~3,000 | Review method; retail forecasting; ARIMA/ETS; FFNN/LSTM; hybrid residual models; metrics, CV, DM test, intervals; BI, decision support and accessibility; ethics and Green AI; synthesis and gaps; **requirements analysis** |
| 3 Project Development | ~3,500 | CRISP-DM in Agile sprints (justified against alternatives); business and data understanding; preparation; models and maths; tuning; evaluation design; architecture, tests, reproducibility; Power BI integration; issues and troubleshooting |
| 4 Critical Evaluation | ~2,800 | Accuracy; significance; calibration; stability; cost and energy; dashboard evaluation; RQ answers; process evaluation; limitations; ethics, sustainability, global context |
| 5 Conclusion | ~900 | Findings; objectives achieved; contribution; recommendations; future work and entrepreneurial potential |
| **Total** | **~11,700** | |

**Appendices:**

- A: AI-use declaration (if required)
- B: Dataset documentation and data dictionary
- C: Extended results
- D: Hyperparameters and search spaces
- E: Test plan and results
- F: Dashboard screenshots, DAX and M code
- G: User-study instruments
- H: Project plan and sprint log
- I: Repository and reproduction guide

## D-010: Formatting conflicts (PROPOSED; see `Doc\compliance_matrix.md` §C)

- **F1, line spacing:** double spacing for body text.
- **F2, font:** Arial 12 for body text, keeping the template's colours and decreasing heading sizes.
- **F4, page numbers:** centre-foot numbers; title page unnumbered; roman numerals for the front matter; arabic numerals for the body.
- **F7, title page:** add "Student Name" and "Submission Date" rows.

**Alternative:** replicate the proposal exactly (Calibri 11, 1.15 spacing), accepting the non-compliance risk.

## D-011: Exception Register candidates (PROPOSED; see `Refrence\exception_register_DRAFT.md`)

There are 8 core candidates and 2 contingent ones. Phase 3 first searches 2023-2026 reviews that could replace each of them.

## D-012: Repository and document build pipeline (PROPOSED)

- The repository structure follows MP §12, with `src/` as an installable package via `pyproject.toml`, so notebooks import it rather than copying code.
- **Document pipeline:**
  1. Markdown chapters in `Code\docbuild\chapters\`, using `[@key]`, `{fig:id}`, `{tbl:id}` and `{sec:id}` markers.
  2. `build_docx.py` copies the template, strips the body, keeps the sections, header, footer and styles, and writes OOXML: headings, `SEQ`/`STYLEREF` captions, `REF` cross-references, citation hyperlinks to `ref_*` bookmarks, a reference list from `references.json`, and TOC/LoF/LoT fields.
  3. `update_fields` (Word COM) updates all fields.
  4. `export_pdf` (Word `ExportAsFixedFormat`, with bookmarks) produces the PDF.
  5. `citation_audit.py` checks the result.

## D-013: Mapping of the installed academic-research-skills (PROPOSED)

The five skills were read in full: `academic-paper`, `academic-paper-reviewer`, `academic-pipeline`, `deep-research` and `sr-screener`.

| Task (MP §7) | Installed skill and mode | How it is used | Overrides needed |
|---|---|---|---|
| Literature leads and synthesis (Phase 3) | `deep-research` `lit-review` / `three-way-scan` (WHY/HOW/WHAT extraction) | Structure the comparison matrix and gap analysis from **already verified** sources | It defaults to APA 7 and WebSearch discovery. Its search output is a lead only and is re-verified; MP §8 wins |
| Eligibility screening of Scholar exports | `sr-screener` `protocol` / `quick` | Apply the MP §8.2 criteria consistently to the exported records | Full dual-reviewer runs need many subagent calls; use only if you approve the cost |
| Argument structure (Fact Finding, Critical Evaluation) | `academic-paper` `outline-only` / `plan` (structure_architect, argument_builder) | Claim-evidence chains per chapter | Handbook structure fixed; no IMRaD |
| Style and clarity editing (all chapters) | `academic-paper` writing quality check and anti-patterns | Remove vague vocabulary and throat-clearing openers; check paragraph logic | British English; Arden Harvard; **no** bilingual abstract; journal "mandatory inclusions" (CRediT, funding statement) not applicable |
| Rubric-based critique after each chapter | `academic-paper-reviewer` `methodology-focus` / `quick` | Peer-review style critique, with the Arden marking scheme supplied as the target criteria | Reports only; the reviewer never edits the manuscript |
| Citation and claim cross-check | `academic-paper` `citation-check`; `academic-pipeline` integrity protocol and 7-mode AI research failure checklist | A second opinion on citation-claim fit and on failure modes (hallucinated results, implementation bugs, shortcut reliance) | Cross-check only; `citation_audit.py` and the ledger stay canonical |
| AI-use declaration | `academic-paper` `disclosure` | Draft the statement | Must follow Arden policy (pending D-014) |
| **Not used** | `academic-pipeline` end-to-end orchestration | | Its Stage 5 requires a LaTeX-compiled PDF and APA defaults, which conflict with the Word-template build |

## D-014: Generative-AI policy (PENDING)

The handbook contains no generative-AI policy. Writing will not start until you confirm Arden's current policy and whether a declaration appendix is required.

**Update, 9 Nov 2026.** You asked for the report to be drafted. The AI-use declaration (Appendix A) will be drafted factually, marked "to be checked against Arden's policy".

---

## Gate A answers (9 Nov 2026)

| Topic | Your answer | Effect |
|---|---|---|
| Literature discovery | **Scholarly APIs approved** | D-001 option B: OpenAlex and Crossref discovery, with verification on DOI/publisher pages |
| Data | You downloaded the Kaggle files yourself into `Dataset\` | Use them in place. No mirrors and no other downloads. Record the Kaggle URLs as the source. Check every file before any experiment |
| Body format | **Handbook format with the template's look** | D-010 APPROVED: Arial 12, double spacing, justified; logo header, title page, heading colours and centred page numbers kept |
| Ethics | **Approved, including participants** | D-006: the user study may run, but only with real participants and data you supply. Until then its results are reported as pending |
| Report | "Delete the existing content (except for the first page) and replace it" | The title page is kept unchanged |

## D-015: Data handling rules (DECIDED 9 Nov 2026, after EDA)

**Integrity check.** All 9 Kaggle files parsed completely; see `outputs/data_check/raw_data_check.md`. SHA-256 checksums are recorded.

**M5:**

- Uses the ten store-level series: daily unit sales summed over all items, 29 Jan 2011 to 22 May 2016, 1,941 days.
- **Christmas Day** is a known closure in every year: sales fall to between 0 and 11 units in every store.

**Rossmann.** A stratified random sample of 20 stores (seed 2026) is used, drawn from eligible stores. A store is eligible when it has:

- a complete 942-day history
- no Sunday opening
- at most 35 weekday closures
- no day recorded as open with zero sales

That leaves 836 eligible stores. Allocation is proportional to StoreType x Assortment, with a minimum of two per stratum.

**Closures and anomalies:**

- **Closures** (Rossmann `Open = 0`; M5 Christmas Day) are known in advance. They are passed to the state-space models as missing values, fed to the networks as zero plus a flag, and excluded from scoring.
- **Anomalies** are flagged by a causal rule: a non-closure day below 10% of the trailing 28-day median. They are treated the same way for modelling, but stay in scoring.
- Only one anomaly was flagged: M5 TX_2 on 24 March 2015 (131 units).

**Scoring.** Forecasts are scored on trading days with positive sales. This is the same exclusion the Rossmann competition used, and it keeps MAPE defined.

**Plain-language rationale:** shops that are shut on known days should not be "forecast"; a rare data glitch should not teach the models something false.

## D-016: Model information set and statistical specifications (DECIDED)

**ARIMA:**

- Implemented as regression with seasonal ARIMA errors (SARIMAX).
- Weekly seasonal differencing (D = 1, m = 7).
- d chosen by a KPSS test.
- p, q, P and Q chosen by a stepwise AICc search (p, q at most 3; P, Q at most 2).
- Regressors known in advance: two annual Fourier harmonics, plus event and SNAP flags (M5) or promotion and school-holiday flags (Rossmann).
- **Why:** this gives ARIMA the same calendar and promotion information as the networks, so the hybrid's gain cannot come merely from extra information.

**ETS:** the linear state-space ETS with additive weekly seasonality, with the trend (N, A or Ad) chosen by AICc. It uses the "concentrated" initialisation, the only statsmodels option that handles missing days.

**Both models:**

- Specifications are selected on the tuning-stage training period.
- Parameters are re-estimated on the full training period before testing.
- At later origins the parameters stay fixed and the Kalman filter is re-run on the available data. This is the same "fixed model, rolling origin" protocol as the networks.

**Deviation from the proposal:** R was not installed (D-003 was not approved), so all statistical models run in Python statsmodels, and the R cross-check is not performed.

## D-017: Neural design and hybrid variants (DECIDED)

**Networks:**

- Global FFNN and LSTM networks are trained across all series of a dataset (one-hot series identity).
- They use direct multi-output forecasts of 28 days and a masked MSE loss on standardised targets.
- Early stopping uses a later, disjoint 10% block of training windows.

**Hybrid variants**, testing MP §6.1:

- `hyb_d`: direct, one-step residuals
- `hyb_z`: recursive, one-step residuals (classic Zhang formulation)
- `hyb_ms`: direct, multi-step ARIMA errors (error correction)

The primary hybrid is the variant with the best validation MASE; the others are reported as ablations.

**Tuning:**

- Optuna TPE (seed 2026), 15 trials per model per dataset.
- Objective: mean per-series MASE over the five validation origins.
- `hyb_z` reuses the `hyb_d` configuration.

**Final training:** 5 seeds (1 to 5).

## D-018: Determinism and uncertainty (DECIDED)

**Determinism:**

- Seeds for Python, NumPy and TensorFlow.
- `enable_op_determinism`.
- `TF_ENABLE_ONEDNN_OPTS=0`.

**Prediction intervals:**

- ARIMA and ETS: native Gaussian 95% intervals.
- All models: horizon-specific split-conformal 95% intervals calibrated on the validation errors (absolute errors scaled by the MASE scale).

**Plain-language rationale:** every model gets an uncertainty band built the same way, so their honesty about uncertainty can be compared.

## D-019: Compute-cost reporting (DECIDED)

- Wall-clock training and fitting time is measured with jobs run one at a time (no competing processes).
- Energy estimate = runtime x 15 W, the TDP of the Intel Core i7-4510U. This is an upper-bound approximation, not a measurement.

## D-020: Publication year rule for references (DECIDED 9 Nov 2026)

- The year cited is the year of the journal issue when the article has been assigned to an issue (Crossref "published-print"); otherwise it is the year of online publication.
- **Why:** Harvard references cite the version of record. Several 2023 articles appeared online in late 2022, so using the online year would wrongly place them outside the 2023-2026 window, and the reverse would misdate articles still in advance publication.
- Applied in `scripts/literature/build_library.py` and re-checked by `docbuild/citation_audit.py`.

## D-021: Deviations from the proposal (FACT, 9 Nov 2026)

| Proposal | Actual | Reason |
|---|---|---|
| R (forecast, fable) for statistical models; R cross-check | Python statsmodels only; no R cross-check | R not installed; installation not approved (D-003) |
| Python 3.11 | Python 3.13.14 | Installed version; all pins in `requirements.txt` |
| Google Scholar discovery | OpenAlex and Crossref discovery, publisher full-text verification | Automated Scholar access refused; option B approved (D-001) |
| Tableau prototype as comparator | Not built | Power BI only (D-008) |
| User study with three to five participants | Approved; not yet conducted | Time; results reported as pending |
| `.pbix` dashboard | Data model, measures, build guide and test plan; `.pbix` to be assembled in Power BI Desktop | The report layer cannot be generated reliably from code |
| Five-fold time-series cross-validation for tuning | Five rolling validation origins of 28 days before the test period | Same principle (expanding window, time order kept); matches the 28-day horizon |

## D-022: Checkpointing of long runs (DECIDED 9 Nov 2026)

- After a background run was stopped by the environment (system clock change) and lost 16 of 20 completed Rossmann stores, every long stage now checkpoints: per series (statistical stage), per Optuna trial (SQLite study plus per-trial validation forecasts) and per seed (final training).
- Timings are stored with the checkpoints, so resuming does not distort the cost figures.

## D-023: Second-pass verification of the hybrid comparison table (FACT, 9 Nov 2026)

- Cells of Table 2.1 not covered by the first-pass reading notes were re-checked on the publisher pages (logged in `Refrence/search/reading_notes.md`).
- **Correction:** Mbodila and Esan (2026) did use a paired t-test (the draft said "None").
- The "evaluation horizon" column was removed because the horizon was not stated in several papers; horizons are reported in the text only where verified (Wan et al., 2023: one day; Si et al., 2024: one step; Gerakoudi et al., 2026: one and five steps).
- Several sentences in Chapters 1 and 2 were reworded so that every claim matches the reading notes exactly.

## D-024: Statistical testing details (DECIDED 9 Nov 2026)

- Diebold-Mariano tests (HLN correction, h = 28) compare the primary hybrid with each of the other seven models, using both absolute and squared scaled losses.
- For each hybrid seed and loss, the seven p-values form one family and are adjusted with the Holm step-down method (`src/statistical_tests.holm_adjust`, unit-tested).
- A difference is called robust only if it is significant after adjustment for all five seeds.

## D-025: Rossmann eligibility uses pre-test data only (DECIDED 10 Nov 2026, audit finding A01)

- **Problem.** Store eligibility (complete history, no Sunday trading, at most 35 weekday closures, no open day with zero sales) was judged on all 942 days, including the test period. Fourteen stores (123, 292, 308, 674, 699, 764, 803, 870, 876, 894, 947, 964, 971, 1021) were excluded only because of events in the test period: a mild selection look-ahead.
- **Fix.** `eligible_rossmann_stores` now uses only records dated before the first test day (17 January 2015). Completeness of the test-period records remains a structural requirement of the panel (checked when the panel is built). Stores with no weekday closure are now handled explicitly (count 0); this changed no eligibility result. Unit tests in `tests/test_data_loader.py` show that changing any record on or after the cut-off does not change eligibility.
- **Effect.** Eligible stores: 836 → 850. Re-drawn sample (same stratified rule, seed 2026):

| | Stores |
|---|---|
| Old sample (v1) | 17, 146, 173, 254, 293, 390, 395, 421, 527, 691, 709, 748, 776, 777, 796, 891, 924, 929, 939, 987 |
| New sample | 17, 146, 176, 254, 293, 390, 400, 421, 527, 691, 718, 776, 777, 792, 796, 891, 929, 936, 939, 987 |
| Removed | 173, 395, 709, 748, 924 |
| Added | 176, 400, 718, 792, 936 |

- The Rossmann statistical stage was re-run on the new sample. The v1 outputs and their experiment-log rows were moved to `outputs/archive/rossmann_sample_v1/`; nothing was deleted.

## D-026 Rossmann statistical stage: concurrent duplicate run and an invalid fit time (10 November 2026)

- The run started at 00:54 was not stopped when the machine went to sleep; it continued after waking. The resumed run started at 19:39 therefore ran alongside it, and both processed the remaining stores and wrote final rows to `EXPERIMENT_LOG.csv` (19:44:48 and 19:45:06 UTC).
- The saved forecasts (`outputs/forecasts/rossmann_statistical.csv.gz`) and specifications come from the later process. Its rows are the valid ones (ARIMA test MASE 0.3588, ETS 0.7251, seasonal naive 0.7673). The earlier rows (ARIMA 0.3576) are kept and marked "superseded" in the notes column; the evaluation ignores them. The small ARIMA difference between the two processes shows that the optimiser is not bit-for-bit reproducible when two fits compete for the processor; this is disclosed as a limitation.
- The ARIMA search time for store 421 (65,657 s) includes the sleep. The search was re-timed on its own with `scripts/retime_arima.py`: 123 s (refit 9.5 s), with the same order as saved, so the forecasts are unchanged. `run_evaluation.cost_table` replaces the invalid time with the re-timed one (`outputs/metrics/rossmann_arima_retime_store_421.json`). Fit times of the stores processed by both runs at once may be inflated by contention; this is disclosed with the cost results.
- The remaining stages run one at a time through `scripts/run_pipeline_rest.sh`, with the system kept awake while the pipeline runs.

## D-027 Remaining stages run in parallel lanes (11 November 2026)

- At the student's request the remaining stages run in parallel lanes (`scripts/run_parallel.py`): A Rossmann networks; B M5 statistical; C M5 FFNN and LSTM; D M5 hybrids after B and C; E evaluation, export and report tables after A to D. Processes are started outside the editor session so that they survive it, and the machine is kept awake.
- Machine: 2 physical cores, 4 logical, about 6 GB RAM. Thread limits per process (OMP, MKL, OpenBLAS, TensorFlow intra-op; inter-op 1): A 2, B 1, C 1, D 2, E 4, so the total never exceeds 4 logical cores.
- The Rossmann FFNN trials 0 to 10 ran alone with default threading; trials 11 to 14 and all later runs use the limits above. Seeds, `PYTHONHASHSEED=0` and TensorFlow op determinism are unchanged. Floating-point results can differ slightly with the thread count; the change is recorded in `EXPERIMENT_LOG.csv` (phase "pipeline").
- Runtimes measured from now on come from processes sharing the processor, and include any time a process was suspended by the memory guard (recorded per step in the "pipeline" rows). They are therefore not directly comparable with the Rossmann statistical times, which ran alone; this is reported with the cost results (RQ3).

## D-028 Pausable pipeline runner (11 November 2026)

- `scripts/run_chunks.py` replaces `scripts/run_parallel.py` (kept for the record). It runs the same lanes (A to E) with the same dependencies, resumes every stage from its own checkpoints and skips stages whose artefacts are complete.
- Pauses happen only between units of work (Optuna trial, final seed, statistical series): the runner sets `outputs/state/PAUSE`, the stage scripts finish the current unit and exit with code 75. Paused time therefore never falls inside a unit, and the unit runtimes logged in `EXPERIMENT_LOG.csv` exclude it. Lane E steps are atomic and finish before the pause completes.
- Processes are no longer suspended. A lane starts only if available RAM after its estimated footprint stays at or above 15% of the total; if memory falls below 15% while several lanes run, the newest lane is asked to pause at its unit boundary (`PAUSE_<lane>`) and restarts when memory allows. At least one lane always runs.
- Thread caps are those of D-027 (A 2, B 1, C 1, D 2, E 4; `PYTHONHASHSEED=0`, TensorFlow inter-op 1). Seeds, determinism settings and model code are unchanged; the hooks only add early exits when a flag file exists.
- Each stage process appends a "pipeline" row (`pipeline-<stage>-<n>`) with start, end, exit code and threads; these rows carry no dataset or model, so the cost tables are unaffected.

## D-029 Interrupted Optuna trials marked as failed (11 November 2026)

When the pipeline processes stopped at 03:15 on 11 November 2026, the trial each tuning study was running stayed in state RUNNING in its Optuna database (Rossmann FFNN: trial 11; Rossmann LSTM: one trial). Optuna never changes such trials, so they would appear as incomplete rows in the tuning results. After the databases were backed up (`outputs/interim/backup_<date>/`), every RUNNING trial was set to FAIL through Optuna's storage API, with the user attribute `failed_reason` = "interrupted run (process stopped 11 Nov 2026 03:15)"; no trial was deleted. The runner now does the same at start-up for any study whose stage has no live process, and logs each change in `outputs/logs/run_chunks.log`. Only COMPLETE trials count towards the 15-trial budget, are written to the tuning-trials CSV and appear in the Appendix D table, which gives the number of interrupted trials per study in brackets. Interrupted trials did not contribute to model selection. `EXPERIMENT_LOG.csv` is unchanged.

**Amendment (12 November 2026, V-3).** The fixed text "process stopped 11 Nov 2026 03:15" was also applied to trials that were interrupted at other times (Rossmann FFNN trial 11 started on 10 Nov 20:56; M5 hybrid MS trial 0 ran from 16:35 on 11 Nov), so it was wrong for them. `mark_stale_trials` now builds the reason from each trial's own start time ("interrupted run (process stopped; trial started 11 Nov 2026 03:14)") and falls back to "interrupted run (process stopped)". The three trials already marked were relabelled once with `scripts/clean_optuna.py --relabel` after the databases were backed up to `outputs/interim/backup_2026-11-12/`. Optuna refuses to edit a finished trial through its storage API, so the single `failed_reason` row of `trial_user_attributes` was rewritten directly; trial states, values and parameters are unchanged. The tuning-trials CSV and summary JSON of the three studies were rewritten (COMPLETE trials only, same contents apart from the reason text).

## D-030 Power BI report built (13 November 2026)

- The `.pbix` row of D-021 is out of date: the three-page Power BI report was built on 13 November 2026 (file saved 06:37 to 06:50). The file holds the Kaggle-derived data and is not committed (`*.pbix` in `.gitignore`); the theme, the measure checklist and the page screenshots are in `dashboard/`. Interactive tests and the user study remain to be done by the author.

## D-031 Kaggle-derived data removed from version control (13 November 2026)

- Tracked files that hold daily store-level sales or forecasts that carry the actual sales were untracked (`git rm --cached`) and kept on disk: `dashboard/data/fact_actuals.csv`, `dashboard/data/fact_forecast.csv`, all of `outputs/forecasts/`, `outputs/archive/rossmann_sample_v1/rossmann_statistical.csv.gz` and `dashboard/Dashboard_screenshots.pdf` (its detail table shows daily actuals). They are listed in `.gitignore`.
- Kept: dimension tables (dates, series, models), `fact_metrics.csv` (per-series error measures), `acceptance_values.json`, the tables and metrics under `outputs/` (aggregates), the notebooks (outputs are summaries and plots; no row-level sales found) and the page images in `outputs/figures/` (they are figures of the report).
- The files remain in the git history. The steps to remove them from all history before the repository is made public are in `reports/history_cleanup.md` and have not been run.
