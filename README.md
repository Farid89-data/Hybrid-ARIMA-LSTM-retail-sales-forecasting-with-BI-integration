# Hybrid ARIMA-LSTM retail sales forecasting with BI integration

Code, tests and documentation for the MSc Data Science project *A Hybrid ARIMA-LSTM Framework for Retail Sales Forecasting with Business Intelligence Integration* (Arden University, COM7014).

The project benchmarks eight forecasting models on daily store-level sales:

- a seasonal naive benchmark;
- ARIMA and ETS;
- a feed-forward network and an LSTM;
- three hybrid ARIMA-LSTM residual models.

The data are two Kaggle datasets: the ten M5 (Walmart) stores and 20 sampled Rossmann stores. Evaluation uses 28-day rolling origins, Diebold-Mariano tests, conformal prediction intervals and runtime and energy estimates. The forecasts are exported as a star schema for a Power BI dashboard.

## Results

<!-- RESULTS:START -->
Results are added here from `outputs/tables/` after the final evaluation run.
<!-- RESULTS:END -->

## Repository layout

| Path | Content |
|---|---|
| `src/` | Python package: data loading, preprocessing, statistical models, networks, hybrids, evaluation, statistical tests, Power BI export |
| `scripts/` | Command-line entry points for each stage (see below) |
| `tests/` | pytest suite, including leakage tests |
| `notebooks/` | Nine executed walkthrough notebooks that read the pipeline outputs |
| `dashboard/` | Power BI data model: data dictionary, Power Query, DAX measures, build guide and test plan |
| `docbuild/` | Builds the dissertation Word file from Markdown chapters in the university template |
| `data/` | Instructions for obtaining the Kaggle files and their reference checksums (no raw data) |
| `outputs/` | Generated forecasts, metrics, tables, figures and logs |
| `DECISIONS_LOG.md` | Design decisions with alternatives and justifications |
| `EXPERIMENT_LOG.csv` | One row per tuning trial and final run: parameters, seed, runtime, energy estimate, metrics |

## Reproducing the results

1. Install Python 3.13 and the pinned dependencies:

   ```
   python -m venv .venv
   .venv\Scripts\activate        (Windows)   or   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Download the Kaggle files as described in `data/README.md` and check them:

   ```
   python scripts/check_raw_data.py --verify
   ```

3. Run the stages in order. Each stage writes checkpoints, so an interrupted run can simply be restarted.

   ```
   python scripts/make_eda.py
   bash scripts/run_queue.sh stat:rossmann stat:m5
   bash scripts/run_queue.sh nn:rossmann:ffnn nn:rossmann:lstm nn:rossmann:hyb_d nn:rossmann:hyb_z nn:rossmann:hyb_ms
   bash scripts/run_queue.sh nn:m5:ffnn nn:m5:lstm nn:m5:hyb_d nn:m5:hyb_z nn:m5:hyb_ms
   python scripts/run_evaluation.py
   python scripts/export_dashboard.py
   python scripts/make_report_tables.py
   python scripts/make_notebooks.py
   ```

   `hyb_z` must run after `hyb_d`, because it reuses the configuration selected for `hyb_d`. Run the stages one at a time if the runtimes are to be compared.

4. Run the tests:

   ```
   python -m pytest -q
   ```

5. Optionally rebuild the dissertation (Windows with Microsoft Word):

   ```
   pip install -r requirements-docs.txt
   python docbuild/build_docx.py
   python docbuild/word_automation.py
   python docbuild/citation_audit.py
   ```

## Design in brief

- **No look-ahead.** Every fitted quantity (scalers, ARIMA and ETS parameters, network weights) uses only data before the relevant cut-off. Tests in `tests/test_leakage.py` perturb future data and check that training inputs do not change.
- **Closures.** Known closures (Rossmann `Open = 0`, M5 Christmas Day) are missing values for the state-space models, zero plus a flag for the networks, and are not scored.
- **Hybrid variants.** `hyb_d` predicts one-step ARIMA residuals directly for 28 days; `hyb_z` iterates a one-step residual network; `hyb_ms` learns the actual multi-step ARIMA errors.
- **Determinism.** Seeds for Python, NumPy and TensorFlow, deterministic TensorFlow operations and `TF_ENABLE_ONEDNN_OPTS=0`.

## Licence and data

The code is released under the MIT licence (`LICENSE`). The Kaggle data are not included and remain subject to the competition rules. Citation metadata are in `CITATION.cff`.
