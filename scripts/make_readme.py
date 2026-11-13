"""Generate README.md from the result files, so that no number is typed by hand.

Usage (from ``Code``)::

    python scripts/make_readme.py            # write README.md and check links, images and Mermaid
    python scripts/make_readme.py --check    # only check that README.md is up to date

Numbers come from ``outputs/metrics/result_facts.json``, ``outputs/tables/*_dm_tests.csv`` and the
JUnit file ``outputs/tests/pytest_results.xml``. Only files tracked by git are linked or shown.
"""

from __future__ import annotations

import ast
import csv
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

CODE = Path(__file__).resolve().parents[1]
REPO = "Farid89-data/Hybrid-ARIMA-LSTM-retail-sales-forecasting-with-BI-integration"
GH = f"https://github.com/{REPO}"
KAGGLE = "https://www.kaggle.com/datasets/Farid89-data/hybrid-arima-lstm-retail-forecast-results"
NAMES = {"snaive": "Seasonal naive", "arima": "ARIMA", "ets": "ETS", "ffnn": "Feed-forward network (FFNN)", "lstm": "LSTM",
         "hyb_d": "Hybrid, direct (hyb_d)", "hyb_z": "Hybrid, recursive (hyb_z)", "hyb_ms": "Hybrid, multi-step errors (hyb_ms)"}
BENCH = ["snaive", "arima", "ets", "ffnn", "lstm"]
SHORT = {"snaive": "the seasonal naive method", "arima": "ARIMA", "ets": "ETS", "ffnn": "the FFNN", "lstm": "the LSTM", "hyb_d": "the direct hybrid", "hyb_z": "the recursive hybrid", "hyb_ms": "the multi-step hybrid"}
DATASETS = [("m5", "M5 (Walmart, 10 stores; mean absolute error in units sold per day)"),
            ("rossmann", "Rossmann (20 sampled stores; mean absolute error in turnover per day)")]


def tracked() -> set[str]:
    out = subprocess.run(["git", "ls-files"], cwd=CODE, capture_output=True, text=True, encoding="utf-8").stdout
    return set(out.splitlines())


def facts() -> dict:
    return json.loads((CODE / "outputs" / "metrics" / "result_facts.json").read_text(encoding="utf-8"))


def dm_rows(ds: str) -> list[dict]:
    with (CODE / "outputs" / "tables" / f"{ds}_dm_tests.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def n_series(ds: str) -> int:
    with (CODE / "outputs" / "tables" / f"{ds}_test_per_series.csv").open(encoding="utf-8", newline="") as fh:
        return len({r["series_id"] for r in csv.DictReader(fh)})


def pct(a: float, b: float) -> float:
    return (a - b) / b * 100


def table(ds: str, f: dict) -> str:
    m = f[ds]["metrics"]
    best = f[ds]["best_model"]
    bench = min(BENCH, key=lambda k: m[k]["mase"])
    rows = [(best, "Best model")]
    rows.append(("arima", "Best benchmark" if bench == "arima" else "Benchmark"))
    if bench not in ("arima", best):
        rows.append((bench, "Best benchmark"))
    rows.append(("snaive", "Benchmark"))
    lines = ["| Role | Model | MASE | MAE | Interval coverage (95%) |", "|---|---|---:|---:|---:|"]
    for key, role in rows:
        v = m[key]
        lines.append(f"| {role} | {NAMES[key]} | {v['mase']:.3f} | {v['mae']:,.1f} | {v['coverage'] * 100:.1f}% |")
    return "\n".join(lines)


def bullets(f: dict) -> list[str]:
    out = []
    # where the hybrid wins
    ds = "m5"
    d = f[ds]
    ph = d["primary_hybrid"]
    rows = dm_rows(ds)
    all5 = all(int(r["seeds_hybrid_better_holm05"]) == int(r["n_seeds"]) for r in rows)
    out.append(f"**Where the hybrid wins.** On M5, the recursive hybrid has a MASE of {d['metrics'][ph]['mase']:.3f} against "
               f"{d['metrics']['arima']['mase']:.3f} for ARIMA ({pct(d['metrics'][ph]['mase'], d['metrics']['arima']['mase']):+.1f}%), and it is "
               f"significantly better than each of the seven other models in {'all five seeds under both losses' if all5 else 'some seeds only'} "
               f"(Diebold-Mariano tests, Holm-adjusted over the primary family of seven comparisons). M5 has only ten series.")
    # where it is not significantly better
    ds = "rossmann"
    d = f[ds]
    ph = d["primary_hybrid"]
    rows = dm_rows(ds)
    arima = [r for r in rows if r["other"] == "arima"]
    seeds_arima = min(int(r["seeds_hybrid_better_holm05"]) for r in arima)
    weak = sorted({r["other"] for r in rows if int(r["seeds_hybrid_better_holm05"]) < int(r["n_seeds"])} - {"arima"})
    hyb_ms_m5 = pct(f["m5"]["metrics"]["hyb_ms"]["mase"], f["m5"]["metrics"]["arima"]["mase"])
    out.append(f"**Where it is not significantly better.** On Rossmann, the multi-step hybrid has the lowest MASE ({d['metrics'][ph]['mase']:.3f} against "
               f"{d['metrics']['arima']['mase']:.3f} for ARIMA, {pct(d['metrics'][ph]['mase'], d['metrics']['arima']['mase']):+.1f}%), but the gain over ARIMA is significant in only "
               f"{seeds_arima} of 5 seeds, so it is not robust, and it is not robustly better than {' and '.join([', '.join(SHORT[k] for k in weak[:-1]), SHORT[weak[-1]]] if len(weak) > 1 else [SHORT[weak[0]]])}. "
               f"On M5, the multi-step hybrid is {hyb_ms_m5:+.1f}% against ARIMA.")
    cov = [(v["coverage"], k, ds) for ds in ("m5", "rossmann") for k, v in f[ds]["metrics"].items()]
    lo, hi = min(cov), max(cov)
    below = {ds: sum(1 for k, v in f[ds]["metrics"].items() if v["coverage"] < 0.95) for ds in ("m5", "rossmann")}
    out.append(f"**Interval coverage.** The 95% conformal intervals covered {lo[0] * 100:.1f}% to {hi[0] * 100:.1f}% of test days. Coverage was below 95% "
               f"for {below['m5']} of 8 models on M5 and {below['rossmann']} of 8 on Rossmann.")
    return out


def docstring(path: Path) -> str:
    try:
        d = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8"))) or ""
    except SyntaxError:
        d = ""
    return d.split("\n")[0].strip().rstrip(".")


MERMAID = """```mermaid
flowchart LR
    A["Data checks<br/>scripts/check_raw_data.py"] --> B["Preprocessing and splits<br/>src/preprocessing.py"]
    B --> C["Statistical models<br/>scripts/run_statistical.py"]
    C --> D["Neural and hybrid models<br/>scripts/run_neural.py"]
    D --> E["Evaluation<br/>scripts/run_evaluation.py"]
    E --> F["Power BI export<br/>scripts/export_dashboard.py"]
    F --> G["Report build<br/>docbuild/build_docx.py"]
```"""


def build() -> str:
    f = facts()
    root = ET.parse(CODE / "outputs" / "tests" / "pytest_results.xml").getroot()
    ts = root if root.tag == "testsuite" else root.find("testsuite")
    n_tests, n_fail = int(ts.get("tests")), int(ts.get("failures")) + int(ts.get("errors"))
    py = re.search(r'python-version:\s*"?([\d.]+)', (CODE / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")).group(1)
    lic = (CODE / "LICENSE").read_text(encoding="utf-8").splitlines()[0].replace(" License", "")
    test_badge = f"{n_tests}%20passed-brightgreen" if n_fail == 0 else f"{n_tests - n_fail}%20of%20{n_tests}%20passed-red"
    hours = f["total_compute_runtime_hours"]
    s = []
    s.append("# Hybrid ARIMA-LSTM Retail Sales Forecasting with BI Integration\n")
    s.append("28-day store-level sales forecasts with calibrated prediction intervals, delivered to a Power BI planning dashboard.\n")
    s.append(f"[![tests]({GH}/actions/workflows/ci.yml/badge.svg)]({GH}/actions/workflows/ci.yml) "
             f"![unit tests](https://img.shields.io/badge/unit%20tests-{test_badge}) "
             f"![Python](https://img.shields.io/badge/python-{py}-blue) "
             f"![Licence](https://img.shields.io/badge/licence-{lic}-lightgrey) "
             f"[![Kaggle dataset](https://img.shields.io/badge/Kaggle-derived%20results%20(planned)-20BEFF)]({KAGGLE}) "
             f"![Dissertation](https://img.shields.io/badge/dissertation-after%20submission-lightgrey)\n")
    s.append("## Results at a glance\n")
    s.append("Test period, 28-day horizon, rolling origins. MASE is the mean absolute scaled error (below 1 beats the in-sample seasonal naive error); lower is better. "
             "Networks use five seeds.\n")
    for ds, title in DATASETS:
        s.append(f"**{title}**\n")
        s.append(table(ds, f) + "\n")
    for b in bullets(f):
        s.append("- " + b)
    s.append("")
    s.append("## Figures\n")
    s.append('<table><tr>'
             '<td><img src="outputs/figures/res_m5_accuracy_cost.png" alt="M5: mean absolute scaled error of each model against its computational cost" width="100%"></td>'
             '<td><img src="outputs/figures/res_rossmann_accuracy_cost.png" alt="Rossmann: mean absolute scaled error of each model against its computational cost" width="100%"></td></tr>'
             '<tr><td align="center">Accuracy against cost, M5</td><td align="center">Accuracy against cost, Rossmann</td></tr>'
             '<tr><td><img src="outputs/figures/res_m5_mase_by_horizon.png" alt="M5: mean absolute scaled error by forecast horizon, one line per model" width="100%"></td>'
             '<td><img src="outputs/figures/res_rossmann_mase_by_horizon.png" alt="Rossmann: mean absolute scaled error by forecast horizon, one line per model" width="100%"></td></tr>'
             '<tr><td align="center">Error by forecast horizon, M5</td><td align="center">Error by forecast horizon, Rossmann</td></tr></table>\n')
    s.append("## Dashboard\n")
    s.append('<table><tr>'
             '<td><img src="outputs/figures/dash_built_forecast.png" alt="Forecast page: actual and forecast sales with the 95% interval, cards for MASE, coverage, MAE and bias" width="100%"></td>'
             '<td><img src="outputs/figures/dash_built_models.png" alt="Model page: best model, MASE by model, coverage by model, MASE by horizon and a store by model table" width="100%"></td>'
             '<td><img src="outputs/figures/dash_built_planning.png" alt="Planning page: forecast sales, safety stock proxy, stock-out and overstock risk days, weekly forecast and bias by store" width="100%"></td></tr>'
             '<tr><td align="center">Forecast</td><td align="center">Models</td><td align="center">Planning</td></tr></table>\n')
    s.append("The dashboard was designed for accessibility: a palette of blue, green, orange and purple, line styles and markers as well as colour, dark text, alt text on every visual and a logical tab order. "
             "Measures that sum sales return blank unless one dataset is selected, so that units and turnover are never mixed. "
             "The interactive accessibility checks have not yet been run. The Power BI file itself is not in the repository, because it stores the competition data; "
             "the theme, the measure checklist and the page images are in `dashboard/`.\n")
    s.append("## Architecture\n")
    s.append(MERMAID + "\n")
    s.append("| Module | Role |\n|---|---|")
    for p in sorted((CODE / "src").glob("*.py")):
        if p.name != "__init__.py":
            s.append(f"| `src/{p.name}` | {docstring(p)} |")
    for name in ["run_statistical.py", "run_neural.py", "run_evaluation.py", "run_chunks.py", "export_dashboard.py", "make_report_tables.py"]:
        s.append(f"| `scripts/{name}` | {docstring(CODE / 'scripts' / name)} |")
    s.append("")
    s.append("## Engineering highlights\n")
    for b in [
        "Leakage-safe rolling-origin evaluation: scalers, ARIMA and ETS parameters and network weights use only data before each cut-off; `tests/test_leakage.py` perturbs future data and checks that training inputs do not change.",
        f"{n_tests} automated tests (pytest) and a continuous-integration workflow (`.github/workflows/ci.yml`).",
        "Checkpointed, resumable and pausable pipeline runner with a memory guard and parallel lanes (`scripts/run_chunks.py`, `Resume-Pipeline.bat`, `Pause-Pipeline.bat`, `Status-Pipeline.bat`).",
        "Five seeds for every network, fixed seeds and deterministic TensorFlow operations (`DECISIONS_LOG.md`, D-018).",
        "An experiment log with one row per tuning trial and final run (`EXPERIMENT_LOG.csv`) and a decisions log with alternatives and reasons (`DECISIONS_LOG.md`).",
        "Automated report build with checks that fail the build: caption layout (`docbuild/check_captions.py`), test count (`docbuild/check_test_count.py`) and citations (`docbuild/citation_audit.py`).",
        f"Total compute for the final experiments: {hours:.1f} hours on one two-core laptop without a graphics processor.",
    ]:
        s.append("- " + b)
    s.append("")
    s.append("## Quick start\n")
    s.append("Python " + py + " is required.\n")
    s.append("```\npython -m venv .venv\n.venv\\Scripts\\activate        (Windows)   or   source .venv/bin/activate\npip install -r requirements.txt\n```\n")
    s.append("1. Download the competition files into the folder described in `data/README.md` and verify them: "
             "[M5 Forecasting - Accuracy](https://www.kaggle.com/competitions/m5-forecasting-accuracy/data), "
             "[Rossmann Store Sales](https://www.kaggle.com/competitions/rossmann-store-sales/data).\n"
             "   ```\n   python scripts/check_raw_data.py --verify\n   ```\n"
             "2. Run the pipeline (Windows): `Resume-Pipeline.bat` starts it or resumes it from the checkpoints, `Pause-Pipeline.bat` pauses it safely and `Status-Pipeline.bat` shows the progress. "
             "Each stage can also be run on its own (see `scripts/` and `data/README.md`).\n"
             "3. Run the tests:\n   ```\n   python -m pytest -q\n   ```\n"
             "4. Rebuild the dashboard export (writes `dashboard/data/`):\n   ```\n   python scripts/export_dashboard.py\n   ```\n"
             "5. Regenerate this page from the result files: `python scripts/make_readme.py`.\n")
    s.append("## Repository layout\n")
    s.append("| Path | Content |\n|---|---|")
    tops = {"src": "Python package: data loading, preprocessing, models, evaluation, statistical tests, Power BI export",
            "scripts": "Command-line entry points for each stage, the pipeline runner and the checks",
            "tests": "pytest suite, including the leakage tests",
            "notebooks": "Walkthrough notebooks that read the pipeline outputs",
            "dashboard": "Power BI data model documents, DAX measures, theme, measure checklist and page images",
            "docbuild": "Builds the dissertation Word file from Markdown chapters, with the build checks",
            "data": "Instructions for obtaining the Kaggle files and their reference checksums (no raw data)",
            "outputs": "Metrics, tables, figures and logs written by the pipeline (forecasts are not tracked)",
            "reports": "Verification and clean-up reports",
            "DECISIONS_LOG.md": "Design decisions with alternatives and reasons",
            "EXPERIMENT_LOG.csv": "One row per tuning trial and final run"}
    present = tracked()
    for k, v in tops.items():
        if any(p == k or p.startswith(k + "/") for p in present):
            s.append(f"| `{k}{'/' if '.' not in k else ''}` | {v} |")
    s.append("")
    s.append("## Reproducibility and data policy\n")
    s.append("The original M5 and Rossmann data are not redistributed, in line with the competition rules, and neither are the actual daily sales or files derived from them "
             "(the forecast files and the dashboard fact tables are not tracked). The author's own derived results (forecasts without the actual sales, accuracy measures, tests, model settings and costs) "
             f"are planned as a [Kaggle dataset]({KAGGLE}); each file there maps to the tables written by this pipeline (`outputs/tables/`, `outputs/metrics/`), and the dataset page explains how to rejoin the forecasts with the original data.\n")
    s.append("## Limitations\n")
    for b in [
        f"M5 has only {n_series('m5')} series here (ten stores), so conclusions about the hybrid on M5 may not carry over to other retailers; Rossmann uses a sample of {n_series('rossmann')} stores.",
        "Both datasets have one test period each; the five seeds measure variation from network initialisation, not from the choice of test period.",
        "The 95% intervals are split conformal and calibrated on the validation windows before the test period; the exchangeability they assume holds only approximately, and coverage varies with the horizon.",
        "Runtimes were measured on one laptop, partly with parallel jobs sharing the processor, so they are indicative and not strictly comparable across stages.",
    ]:
        s.append("- " + b)
    s.append("")
    s.append("## Citation\n")
    s.append("```bibtex\n@software{negahbani2026,\n  author = {Negahbani, Farid},\n  title = {Hybrid ARIMA-LSTM Retail Sales Forecasting with BI Integration},\n"
             f"  year = {{2026}},\n  url = {{{GH}}}\n}}\n```\n")
    s.append("Citation metadata: [`CITATION.cff`](CITATION.cff). Licence: " + lic + " ([`LICENSE`](LICENSE)).\n")
    s.append(f"Author: Farid Negahbani. GitHub: [Farid89-data](https://github.com/Farid89-data). LinkedIn: _link to be added_.\n")
    return "\n".join(s)


def check(text: str) -> list[str]:
    problems = []
    present = tracked()
    for m in re.finditer(r'(?:src="|\]\()([^")#]+)', text):
        t = m.group(1)
        if t.startswith(("http", "mailto")):
            continue
        if t not in present:
            problems.append(f"link or image not tracked: {t}")
    for m in re.finditer(r"`((?:src|scripts|tests|docbuild|dashboard|data|outputs|reports)/[\w./-]+)`", text):
        t = m.group(1)
        if not any(p == t or p.startswith(t.rstrip("/") + "/") for p in present) and not (CODE / t).exists():
            problems.append(f"path in text does not exist: {t}")
    for blk in re.findall(r"```mermaid\n(.*?)```", text, re.S):
        lines = [l.strip() for l in blk.strip().splitlines()]
        if lines[0] != "flowchart LR":
            problems.append("mermaid: first line must be 'flowchart LR'")
        ids = set()
        for l in lines[1:]:
            if not re.fullmatch(r'[A-Z](?:\["[^"\]]+"\])?(?: --> [A-Z]\["[^"\]]+"\])+', l):
                problems.append(f"mermaid: bad line {l[:60]}")
            ids |= set(re.findall(r"\b([A-Z])\[", l))
        if len(ids) < 2:
            problems.append("mermaid: fewer than two nodes")
    banned = re.findall(r"\b(claude|anthropic|chatgpt|copilot|openai)\b", text, re.I)
    if banned:
        problems.append(f"banned words: {banned}")
    if re.search(r"[\U0001F300-\U0001FAFF☀-➿]", text):
        problems.append("emoji found")
    return problems


def numbers_match(text: str, f: dict) -> list[str]:
    problems = []
    for ds in ("m5", "rossmann"):
        for k, v in f[ds]["metrics"].items():
            pass
        best = f[ds]["best_model"]
        mase = f[ds]["metrics"][best]["mase"]
        if f"{mase:.3f}" not in text:
            problems.append(f"{ds}: best MASE {mase:.3f} not in README")
        csvp = CODE / "outputs" / "tables" / f"{ds}_test_summary.csv"
        with csvp.open(encoding="utf-8", newline="") as fh:
            row = {r["model"]: r for r in csv.DictReader(fh)}[best]
        if abs(float(row["mase"]) - mase) > 5e-4:
            problems.append(f"{ds}: result_facts and test summary disagree for {best}")
    return problems


if __name__ == "__main__":
    text = build()
    probs = check(text) + numbers_match(text, facts())
    target = CODE / "README.md"
    if "--check" in sys.argv:
        if target.read_text(encoding="utf-8").replace("\r\n", "\n") != text:
            probs.append("README.md is not up to date")
    else:
        target.write_text(text, encoding="utf-8")
    for p in probs:
        print("README CHECK:", p)
    print("README OK" if not probs else f"{len(probs)} problem(s)")
    sys.exit(1 if probs else 0)
