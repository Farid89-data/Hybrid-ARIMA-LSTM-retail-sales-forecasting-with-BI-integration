"""Create and execute the nine walkthrough notebooks in ``notebooks/``.

Usage (from ``Code``)::

    python scripts/make_notebooks.py            # create and execute
    python scripts/make_notebooks.py --no-run   # create only

The notebooks do not re-run the expensive experiments. They call the package
in ``src`` and read the files written by the pipeline scripts, so that every
table and figure of the dissertation can be inspected step by step.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import nbformat
from nbclient import NotebookClient

CODE_DIR = Path(__file__).resolve().parents[1]
NB_DIR = CODE_DIR / "notebooks"

SETUP = """import sys
from pathlib import Path
CODE_DIR = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(CODE_DIR))
import json
import numpy as np
import pandas as pd
from IPython.display import Image, Markdown, display
from src import config, experiment
pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 30)
TABLES = config.OUTPUT_DIR / "tables"
FIGS = config.FIGURE_DIR"""

NOTEBOOKS = {
    "01_data_check.ipynb": [
        ("md", "# 1. Data check\n\nIntegrity of the raw Kaggle files (rows, columns, missing cells, checksums). "
               "The full check is produced by `scripts/check_raw_data.py`; this notebook displays its report."),
        ("code", SETUP),
        ("code", "report = json.loads((config.OUTPUT_DIR / 'data_check' / 'raw_data_check.json').read_text())\n"
                 "pd.DataFrame(report['files'])[['file', 'size_mb', 'rows', 'n_columns', 'null_cells', 'status']]"),
        ("code", "print(report['checked_at_utc'])\nreport['sources']"),
    ],
    "02_exploratory_analysis.ipynb": [
        ("md", "# 2. Exploratory analysis\n\nThe two modelling panels: ten M5 stores and 20 sampled Rossmann stores."),
        ("code", SETUP),
        ("code", "pd.read_csv(TABLES / 'dataset_summary.csv')"),
        ("code", "for name in ['eda_m5_store_series', 'eda_rossmann_sample_series', 'eda_weekly_profiles', 'eda_acf']:\n"
                 "    display(Markdown(f'**{name}**'))\n    display(Image(filename=str(FIGS / f'{name}.png'), width=800))"),
    ],
    "03_preprocessing_and_splits.ipynb": [
        ("md", "# 3. Preprocessing and chronological splits\n\nClosures, the causal anomaly rule, masks and the rolling-origin plan."),
        ("code", SETUP),
        ("code", "for name in ['m5', 'rossmann']:\n    prep = experiment.prepare(name)\n"
                 "    print(name, prep.plan.describe())\n"
                 "    print('  closures:', int(prep.panel.closed.sum()), ' anomalies:', int(prep.anomalies.sum()))"),
        ("code", "prep = experiment.prepare('m5')\nidx = np.argwhere(prep.anomalies)\n"
                 "[(prep.panel.series_ids[s], str(prep.panel.dates[t].date()), prep.panel.y[s, t]) for s, t in idx]"),
        ("code", "display(Image(filename=str(FIGS / 'eda_split_timeline.png'), width=800))"),
    ],
    "04_statistical_models.ipynb": [
        ("md", "# 4. Statistical benchmarks\n\nSelected ARIMA and ETS specifications and their validation accuracy."),
        ("code", SETUP),
        ("code", "for name in ['m5', 'rossmann']:\n"
                 "    specs = json.loads((config.METRIC_DIR / f'{name}_statistical_specs.json').read_text())\n"
                 "    df = pd.DataFrame(specs)[['series_id', 'arima_order', 'arima_seasonal_order', 'ets_model',\n"
                 "                              'arima_select_seconds', 'path_check_max_abs_gap']]\n"
                 "    display(Markdown(f'**{name}**')); display(df)"),
        ("code", "for name in ['m5', 'rossmann']:\n"
                 "    v = pd.read_csv(TABLES / f'{name}_validation_summary.csv')\n"
                 "    display(Markdown(f'**{name} validation**')); display(v.round(4))"),
    ],
    "05_neural_tuning.ipynb": [
        ("md", "# 5. Neural networks: tuning\n\nOptuna trials (tree-structured Parzen estimator, 15 trials) and the selected configurations."),
        ("code", SETUP),
        ("code", "rows = []\nfor name in ['m5', 'rossmann']:\n    for kind in experiment.NEURAL_KINDS:\n"
                 "        p = config.METRIC_DIR / f'{name}_{kind}_best_params.json'\n"
                 "        if p.exists():\n            d = json.loads(p.read_text())\n"
                 "            rows.append({'dataset': name, 'model': kind, **d['best_params'], 'validation_mase': d['best_value']})\n"
                 "pd.DataFrame(rows)"),
        ("code", "for name in ['m5', 'rossmann']:\n    for kind in ['ffnn', 'lstm', 'hyb_d', 'hyb_ms']:\n"
                 "        p = config.METRIC_DIR / f'{name}_{kind}_tuning_trials.csv'\n"
                 "        if p.exists():\n            t = pd.read_csv(p)\n"
                 "            print(name, kind, 'trials:', len(t), 'best:', round(t['value'].min(), 4), 'median:', round(t['value'].median(), 4))"),
    ],
    "06_hybrid_models.ipynb": [
        ("md", "# 6. Hybrid ARIMA-LSTM variants\n\nOne-step residuals versus multi-step ARIMA errors, and the validation scores of the three variants."),
        ("code", SETUP),
        ("code", "summary = json.loads((config.METRIC_DIR / 'evaluation_summary.json').read_text())\n"
                 "{k: {'primary': v['primary_hybrid'], 'validation_mase': v['hybrid_validation_mase'],\n"
                 "     'error_growth_h1': v['error_growth_median_h1'], 'error_growth_h28': v['error_growth_median_h28']}\n"
                 " for k, v in summary.items()}"),
        ("code", "for name in ['m5', 'rossmann']:\n"
                 "    display(Image(filename=str(FIGS / f'res_{name}_error_growth.png'), width=800))"),
    ],
    "07_evaluation.ipynb": [
        ("md", "# 7. Test-period evaluation\n\nPoint accuracy, Diebold-Mariano tests, accuracy by horizon and interval coverage."),
        ("code", SETUP),
        ("code", "for name in ['m5', 'rossmann']:\n"
                 "    display(Markdown(f'**{name}: test summary**'))\n"
                 "    display(pd.read_csv(TABLES / f'{name}_test_summary.csv').round(4))"),
        ("code", "for name in ['m5', 'rossmann']:\n"
                 "    display(Markdown(f'**{name}: Diebold-Mariano tests**'))\n"
                 "    display(pd.read_csv(TABLES / f'{name}_dm_tests.csv').round(4))"),
        ("code", "for name in ['m5', 'rossmann']:\n"
                 "    for fig in ['mase_by_horizon', 'coverage_by_horizon', 'seed_stability']:\n"
                 "        display(Image(filename=str(FIGS / f'res_{name}_{fig}.png'), width=800))"),
    ],
    "08_cost_and_energy.ipynb": [
        ("md", "# 8. Computational cost and estimated energy\n\nRuntime from the experiment log; energy = runtime x 15 W (processor TDP)."),
        ("code", SETUP),
        ("code", "for name in ['m5', 'rossmann']:\n"
                 "    display(Markdown(f'**{name}**')); display(pd.read_csv(TABLES / f'{name}_cost.csv').round(2))"),
        ("code", "log = pd.read_csv(config.EXPERIMENT_LOG)\nlog.groupby(['dataset', 'model', 'phase'])['runtime_s'].agg(['count', 'sum']).round(1)"),
    ],
    "09_dashboard_export.ipynb": [
        ("md", "# 9. Dashboard export\n\nThe star schema written for Power BI and the acceptance values used by the dashboard test plan."),
        ("code", SETUP),
        ("code", "dash = config.CODE_DIR / 'dashboard' / 'data'\n"
                 "{p.name: len(pd.read_csv(p)) for p in sorted(dash.glob('*.csv'))}"),
        ("code", "json.loads((dash / 'acceptance_values.json').read_text())"),
        ("code", "display(Image(filename=str(FIGS / 'dash_star_schema.png'), width=700))"),
    ],
}


def local_kernel() -> str:
    """Register a project-local kernel that runs this interpreter (no change to the user's Jupyter setup)."""
    import json
    import os
    import sys

    kdir = CODE_DIR / "outputs" / "interim" / "jupyter" / "kernels" / "hybrid-forecast"
    kdir.mkdir(parents=True, exist_ok=True)
    spec = {"argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
            "display_name": "Python (hybrid-forecast)", "language": "python"}
    (kdir / "kernel.json").write_text(json.dumps(spec), encoding="utf-8")
    os.environ["JUPYTER_PATH"] = str(kdir.parents[1]) + os.pathsep + os.environ.get("JUPYTER_PATH", "")
    return "hybrid-forecast"


def build(run: bool) -> None:
    NB_DIR.mkdir(exist_ok=True)
    kernel = local_kernel() if run else "python3"
    for name, cells in NOTEBOOKS.items():
        nb = nbformat.v4.new_notebook()
        nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
        nb.cells = [nbformat.v4.new_markdown_cell(src) if kind == "md" else nbformat.v4.new_code_cell(src)
                    for kind, src in cells]
        if run:
            NotebookClient(nb, timeout=600, kernel_name=kernel,
                           resources={"metadata": {"path": str(NB_DIR)}}).execute()
            nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
        nbformat.write(nb, NB_DIR / name)
        print(("executed " if run else "created ") + name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-run", action="store_true")
    build(run=not parser.parse_args().no_run)
