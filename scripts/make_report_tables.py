"""Format result files into the report-ready tables used by the Word build.

Usage (from ``Code``)::

    python scripts/make_report_tables.py [--cite-map docbuild/build/cite_sections.json]

Every table is derived from files written by the pipeline (data check,
forecasts, metrics, experiment log, tests). Nothing is typed by hand: a table
whose source file does not exist yet is skipped with a message. Output goes to
``outputs/tables/report_*.csv``; the build references these files.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from src import config  # noqa: E402
from src.visualisation import LABELS  # noqa: E402

TABLE_DIR = config.OUTPUT_DIR / "tables"
ORDER = ["snaive", "arima", "ets", "ffnn", "lstm", "hyb_d", "hyb_ms", "hyb_z"]
DATASET_LABEL = {"m5": "M5", "rossmann": "Rossmann"}
REF_DIR = config.PROJECT_ROOT / "Refrence"


def write(rows: list[list[str]], name: str) -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    path = TABLE_DIR / f"report_{name}.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows(rows)
    print(f"wrote {path.relative_to(config.CODE_DIR)} ({len(rows) - 1} rows)")


def fmt(value, digits: int = 3) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "n/a"
    return f"{value:,.{digits}f}"


def pct(value, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{100 * value:.{digits}f}%"


# --------------------------------------------------------------------------- data


def raw_data_check() -> None:
    src = config.OUTPUT_DIR / "data_check" / "raw_data_check.json"
    data = json.loads(src.read_text(encoding="utf-8"))
    rows = [["File", "Size (MB)", "Rows", "Columns", "Missing cells", "Status", "SHA-256 (first 16)"]]
    for f in data["files"]:
        name = f["file"].replace("Dataset\\", "").replace("\\", "/")
        rows.append([name, f"{f['size_mb']:.2f}", f"{f['rows']:,}", str(f["n_columns"]),
                     f"{f['null_cells']:,}", f["status"], f["sha256"][:16]])
    write(rows, "raw_data_check")


def rossmann_stores() -> None:
    src = TABLE_DIR / "rossmann_sample_stores.csv"
    df = pd.read_csv(src)
    rows = [["Store", "Store type", "Assortment", "Competition distance", "Promo2"]]
    for _, r in df.sort_values("store").iterrows():
        dist = "n/a" if pd.isna(r["CompetitionDistance"]) else f"{r['CompetitionDistance']:,.0f}"
        rows.append([str(r["store"]), r["StoreType"], r["Assortment"], dist, "Yes" if r["Promo2"] == 1 else "No"])
    write(rows, "rossmann_stores")


# --------------------------------------------------------------------------- models


def stat_specs(name: str) -> None:
    src = config.METRIC_DIR / f"{name}_statistical_specs.json"
    if not src.exists():
        print(f"skip stat_specs {name}: {src.name} missing")
        return
    specs = json.loads(src.read_text(encoding="utf-8"))
    rows = [["Series", "ARIMA (p,d,q)", "Seasonal (P,D,Q)7", "Models tried", "Search time (s)", "ETS model"]]
    for s in specs:
        p, d, q = s["arima_order"]
        P, D, Q, _ = s["arima_seasonal_order"]
        rows.append([s["series_id"].replace("store_", "Store "), f"({p},{d},{q})", f"({P},{D},{Q})",
                     str(s["arima_models_tried"]), f"{s['arima_select_seconds']:.0f}", s["ets_model"]])
    write(rows, f"stat_specs_{name}")


def trial_counts(name: str, kind: str) -> str:
    """Complete trials, with interrupted (failed) trials in brackets (D-029)."""
    src = config.METRIC_DIR / f"{name}_{kind}_tuning_trials_summary.json"
    if not src.exists():
        return "n/a"
    s = json.loads(src.read_text(encoding="utf-8"))
    return f"{s['complete_trials']} ({s['failed_trials']})"


def best_params() -> None:
    rows = [["Dataset", "Model", "Input window", "Units", "Layers", "Dropout", "Learning rate", "Batch",
             "Validation MASE", "Trials (interrupted)"]]
    found = False
    for name in ("m5", "rossmann"):
        for kind in ("ffnn", "lstm", "hyb_d", "hyb_ms", "hyb_z"):
            src = config.METRIC_DIR / f"{name}_{kind}_best_params.json"
            if not src.exists():
                continue
            found = True
            d = json.loads(src.read_text(encoding="utf-8"))
            bp = d["best_params"]
            rows.append([DATASET_LABEL[name], LABELS[kind], str(bp["lookback"]), str(bp["units"]),
                         str(bp.get("n_layers", 1)), f"{bp['dropout']:.2f}", f"{bp['learning_rate']:.5f}",
                         str(bp["batch_size"]), f"{d['best_value']:.3f}", trial_counts(name, kind)])
    if found:
        write(rows, "best_params")


def test_summary(name: str) -> None:
    src = TABLE_DIR / f"{name}_test_summary.csv"
    if not src.exists():
        print(f"skip test_summary {name}: {src.name} missing")
        return
    df = pd.read_csv(src).set_index("model")
    rows = [["Model", "RMSE", "MAE", "MAPE (%)", "MASE", "MASE s.d. (seeds)", "Coverage (conformal)",
             "Coverage (Gaussian)"]]
    for m in [m for m in ORDER if m in df.index]:
        r = df.loc[m]
        sd = "n/a" if r["n_seeds"] <= 1 else fmt(r["mase_sd_seeds"], 3)
        native = pct(r["coverage_native"]) if "coverage_native" in r and not pd.isna(r["coverage_native"]) else "n/a"
        rows.append([LABELS[m], fmt(r["rmse"], 0), fmt(r["mae"], 0), fmt(r["mape"], 2), fmt(r["mase"], 3), sd,
                     pct(r["coverage"]), native])
    write(rows, f"test_summary_{name}")


def interval_summary(name: str) -> None:
    src = TABLE_DIR / f"{name}_test_summary.csv"
    if not src.exists():
        return
    df = pd.read_csv(src).set_index("model")
    rows = [["Model", "Coverage (conformal)", "Scaled width (conformal)", "Interval score (conformal)",
             "Coverage (Gaussian)", "Scaled width (Gaussian)", "Interval score (Gaussian)"]]
    for m in [m for m in ORDER if m in df.index]:
        r = df.loc[m]
        has_native = "coverage_native" in r and not pd.isna(r["coverage_native"])
        rows.append([LABELS[m], pct(r["coverage"]), fmt(r["width_scaled"], 2), fmt(r["winkler_scaled"], 2),
                     pct(r["coverage_native"]) if has_native else "n/a",
                     fmt(r["width_native"], 2) if has_native else "n/a",
                     fmt(r["winkler_native"], 2) if has_native else "n/a"])
    write(rows, f"intervals_{name}")


def mase_by_week(name: str) -> None:
    src = TABLE_DIR / f"{name}_mase_by_week.csv"
    if not src.exists():
        return
    df = pd.read_csv(src).set_index("model")
    rows = [["Model", "Days 1 to 7", "Days 8 to 14", "Days 15 to 21", "Days 22 to 28"]]
    for m in [m for m in ORDER if m in df.index]:
        rows.append([LABELS[m]] + [fmt(df.loc[m, f"mase_week{w}"], 3) for w in (1, 2, 3, 4)])
    write(rows, f"mase_by_week_{name}")


def dm_tests(name: str) -> None:
    src = TABLE_DIR / f"{name}_dm_tests.csv"
    if not src.exists() or src.stat().st_size < 5:
        return
    df = pd.read_csv(src)
    rows = [["Compared with", "Loss", "DM statistic (seed 1)", "Holm p (seed 1)", "Seeds: hybrid better",
             "Seeds: hybrid worse", "Series: better / worse"]]
    for _, r in df.iterrows():
        p = r["p_holm_seed1"]
        ptxt = "< 0.001" if p < 0.001 else f"{p:.3f}"
        rows.append([LABELS[r["other"]], r["loss"].capitalize(), f"{r['dm_stat_seed1']:.2f}", ptxt,
                     f"{int(r['seeds_hybrid_better_holm05'])} of {int(r['n_seeds'])}",
                     f"{int(r['seeds_hybrid_worse_holm05'])} of {int(r['n_seeds'])}",
                     f"{int(r['series_hybrid_better_p05_seed1'])} / {int(r['series_hybrid_worse_p05_seed1'])}"])
    write(rows, f"dm_{name}")


def _ptxt(p) -> str:
    return "n/a" if pd.isna(p) else ("< 0.001" if p < 0.001 else f"{p:.3f}")


def dm_matrix_report(name: str) -> None:
    src = TABLE_DIR / f"{name}_dm_matrix.csv"
    if not src.exists() or src.stat().st_size < 5:
        print(f"skip dm_matrix {name}: {src.name} missing")
        return
    df = pd.read_csv(src)
    df = df[df["loss"] == "squared"]
    models = [m for m in ORDER if m in set(df["row"])]
    rows = [["Row model (vs column)"] + [LABELS[m] for m in models]]
    for a in models:
        line = [LABELS[a]]
        for b in models:
            r = df[(df["row"] == a) & (df["col"] == b)]
            if a == b or r.empty:
                line.append("-")
                continue
            r = r.iloc[0]
            star = "*" if r["p_holm"] < 0.05 else ""
            line.append(f"{r['dm_stat']:.2f}{star}")
        rows.append(line)
    write(rows, f"dm_matrix_{name}")


def hybrid_ablation_report(name: str) -> None:
    src = TABLE_DIR / f"{name}_hybrid_ablation.csv"
    if not src.exists() or src.stat().st_size < 5:
        print(f"skip hybrid_ablation {name}: {src.name} missing")
        return
    df = pd.read_csv(src)
    rows = [["Hybrid", "MASE hybrid", "MASE ARIMA", "MASE LSTM", "Change vs ARIMA (%)", "Change vs LSTM (%)",
             "DM vs ARIMA", "Holm p vs ARIMA", "DM vs LSTM", "Holm p vs LSTM"]]
    for _, r in df.iterrows():
        rows.append([LABELS[r["hybrid"]], fmt(r["mase_hybrid"]), fmt(r["mase_arima"]), fmt(r["mase_lstm"]),
                     f"{r['pct_change_vs_arima']:+.1f}", f"{r['pct_change_vs_lstm']:+.1f}",
                     fmt(r["dm_stat_vs_arima"], 2), _ptxt(r["p_holm_vs_arima"]),
                     fmt(r["dm_stat_vs_lstm"], 2), _ptxt(r["p_holm_vs_lstm"])])
    write(rows, f"hybrid_ablation_{name}")


def residual_diagnostics_report(name: str) -> None:
    src = TABLE_DIR / f"{name}_residual_diagnostics.csv"
    if not src.exists() or src.stat().st_size < 5:
        print(f"skip residual_diagnostics {name}: {src.name} missing")
        return
    df = pd.read_csv(src)
    rows = [["Test", "Stores tested", "Share of stores with p < 0.05"]]
    for col, label in (("lb7_p", "Ljung-Box, lag 7"), ("lb14_p", "Ljung-Box, lag 14"), ("bds_p", "BDS, dimension 2")):
        ok = df[col].dropna()
        rows.append([label, str(len(ok)), pct((ok < 0.05).mean()) if len(ok) else "n/a"])
    write(rows, f"residual_diagnostics_{name}")


def cross_dataset() -> None:
    """G04: one row per model, accuracy and coverage for M5 and Rossmann side by side."""
    frames = {}
    for name in ("m5", "rossmann"):
        src = TABLE_DIR / f"{name}_test_summary.csv"
        if src.exists():
            frames[name] = pd.read_csv(src).set_index("model")
        else:
            print(f"skip cross_dataset {name}: {src.name} missing")
    if len(frames) < 2:
        print("skip cross_dataset: needs both datasets")
        return
    header = ["Model"]
    for name in frames:
        d = DATASET_LABEL[name]
        header += [f"{d} MASE", f"{d} RMSE", f"{d} MAPE (%)", f"{d} coverage"]
    rows = [header]
    for m in [m for m in ORDER if any(m in f.index for f in frames.values())]:
        line = [LABELS[m]]
        for f in frames.values():
            if m in f.index:
                r = f.loc[m]
                line += [fmt(r["mase"], 3), fmt(r["rmse"], 0), fmt(r["mape"], 2), pct(r["coverage"])]
            else:
                line += ["n/a"] * 4
        rows.append(line)
    write(rows, "cross_dataset")


def cost() -> None:
    rows = [["Dataset", "Model", "Tuning runs", "Tuning time (min)", "Time per final run (min)",
             "Total time (min)", "Total incl. ARIMA (min)", "Estimated energy (Wh)"]]
    found = False
    for name in ("m5", "rossmann"):
        src = TABLE_DIR / f"{name}_cost.csv"
        if not src.exists():
            continue
        found = True
        df = pd.read_csv(src).set_index("model")
        for m in [m for m in ORDER if m in df.index]:
            r = df.loc[m]
            rows.append([DATASET_LABEL[name], LABELS[m], str(int(r["tuning_runs"])),
                         fmt(r["tuning_seconds"] / 60, 1), fmt(r["final_seconds_per_run"] / 60, 1),
                         fmt(r["total_seconds"] / 60, 1), fmt(r["total_with_arima_seconds"] / 60, 1),
                         fmt(r["energy_kwh_total"] * 1000, 1)])
    if found:
        write(rows, "cost")


# --------------------------------------------------------------------------- tests and literature


def unit_tests() -> None:
    src = config.OUTPUT_DIR / "tests" / "pytest_results.xml"
    if not src.exists():
        print("skip unit_tests: run pytest with --junitxml=outputs/tests/pytest_results.xml")
        return
    root = ET.parse(src).getroot()
    rows = [["Test file", "Test", "Result", "Time (s)"]]
    for case in root.iter("testcase"):
        result = "Passed"
        if case.find("failure") is not None or case.find("error") is not None:
            result = "Failed"
        elif case.find("skipped") is not None:
            result = "Skipped"
        module = case.get("classname", "").split(".")[-1]
        rows.append([module + ".py", case.get("name", "").replace("_", " "), result,
                     f"{float(case.get('time', 0)):.2f}"])
    write(rows, "unit_tests")


def literature_matrix(cite_map: Path | None) -> None:
    refs = json.loads((REF_DIR / "references.json").read_text(encoding="utf-8"))
    notes = json.loads((REF_DIR / "search" / "annotations.json").read_text(encoding="utf-8"))
    sections = {}
    if cite_map and cite_map.exists():
        sections = json.loads(cite_map.read_text(encoding="utf-8"))
    rows = [["Study", "Journal", "Focus", "Cited in"]]
    entries = [r for r in refs if r.get("ledger_status") == "VERIFIED"]
    entries.sort(key=lambda r: (r["author"][0]["family"].lower(), r["issued"]["date-parts"][0][0]))
    for r in entries:
        key = r["id"]
        secs = [s for s in sections.get(key, []) if not s.startswith("App. C")]
        focus = notes.get(key, {}).get("topic", "")
        focus = focus[0].upper() + focus[1:] if focus else ""
        rows.append([f"@{key}", r.get("container-title", ""), focus, ", ".join(secs)])
    write(rows, "literature_matrix")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cite-map", type=Path, default=config.CODE_DIR / "docbuild" / "build" / "cite_sections.json")
    args = parser.parse_args()
    raw_data_check()
    rossmann_stores()
    for name in ("m5", "rossmann"):
        stat_specs(name)
        test_summary(name)
        interval_summary(name)
        mase_by_week(name)
        dm_tests(name)
        dm_matrix_report(name)
        hybrid_ablation_report(name)
        residual_diagnostics_report(name)
    best_params()
    cost()
    cross_dataset()
    unit_tests()
    literature_matrix(args.cite_map)


if __name__ == "__main__":
    main()
