"""Collect the result figures quoted in the text of Chapters 4 and 5 and the abstract.

Usage (from ``Code``; after ``scripts/run_evaluation.py``)::

    python scripts/summarise_results.py

Writes ``outputs/metrics/result_facts.json``. Every number quoted in the
discussion of results is taken from this file, which is derived only from the
evaluation outputs, so the text can be checked against the pipeline.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src import config, utils  # noqa: E402

TABLES = config.OUTPUT_DIR / "tables"
STAT = ["snaive", "arima", "ets"]


def pct_change(new: float, base: float) -> float:
    """Relative change in percent (negative = lower error than the base)."""
    return float(100 * (new - base) / base)


def dataset_facts(name: str, evaluation: dict) -> dict:
    summary = pd.read_csv(TABLES / f"{name}_test_summary.csv").set_index("model")
    per_seed = pd.read_csv(TABLES / f"{name}_test_per_seed.csv")
    per_series = pd.read_csv(TABLES / f"{name}_test_per_series.csv")
    by_week = pd.read_csv(TABLES / f"{name}_mase_by_week.csv").set_index("model")
    dm = pd.read_csv(TABLES / f"{name}_dm_tests.csv")
    cost = pd.read_csv(TABLES / f"{name}_cost.csv").set_index("model")
    primary = evaluation["primary_hybrid"]

    ranking = summary["mase"].sort_values()
    facts: dict = {
        "primary_hybrid": primary,
        "hybrid_validation_mase": evaluation["hybrid_validation_mase"],
        "ranking_by_mase": [[m, round(float(v), 4)] for m, v in ranking.items()],
        "best_model": ranking.index[0],
        "metrics": {m: {k: float(summary.loc[m, k]) for k in ("rmse", "mae", "mape", "mase", "coverage",
                                                             "width_scaled", "mase_sd_seeds")
                        if k in summary.columns}
                    for m in summary.index},
    }
    for base in ("snaive", "arima", "ets", "ffnn", "lstm"):
        if base in summary.index and primary in summary.index:
            facts[f"hybrid_vs_{base}_pct"] = {k: round(pct_change(summary.loc[primary, k], summary.loc[base, k]), 2)
                                              for k in ("rmse", "mape", "mase")}
    if "lstm" in summary.index and "arima" in summary.index:
        facts["lstm_vs_arima_pct"] = {k: round(pct_change(summary.loc["lstm", k], summary.loc["arima", k]), 2)
                                      for k in ("rmse", "mape", "mase")}
    # Seed spread of the neural models
    facts["seed_range_mase"] = {
        m: [round(float(g["mase"].min()), 4), round(float(g["mase"].max()), 4)]
        for m, g in per_seed.groupby("model") if g["seed"].nunique() > 1}
    # Per-series comparison of the primary hybrid (mean over seeds) with ARIMA
    if primary:
        hyb = per_series[per_series.model == primary].groupby("series_id")["mase"].mean()
        for base in ("arima", "ets", "snaive", "lstm"):
            b = per_series[per_series.model == base].groupby("series_id")["mase"].mean()
            common = hyb.index.intersection(b.index)
            facts[f"series_hybrid_better_than_{base}"] = int((hyb[common] < b[common]).sum())
            facts["n_series"] = int(len(common))
    # Best model per series
    mean_series = per_series.groupby(["series_id", "model"])["mase"].mean().unstack()
    facts["best_model_count_by_series"] = mean_series.idxmin(axis=1).value_counts().to_dict()
    # Accuracy by week of the horizon
    facts["mase_by_week"] = {m: [round(float(by_week.loc[m, f"mase_week{w}"]), 4) for w in (1, 2, 3, 4)]
                             for m in by_week.index}
    # Diebold-Mariano summary (Holm-adjusted, all seeds)
    facts["dm"] = [
        {"other": r["other"], "loss": r["loss"], "stat_seed1": round(float(r["dm_stat_seed1"]), 3),
         "p_holm_seed1": float(r["p_holm_seed1"]), "seeds_better": int(r["seeds_hybrid_better_holm05"]),
         "seeds_worse": int(r["seeds_hybrid_worse_holm05"]), "n_seeds": int(r["n_seeds"]),
         "series_better": int(r["series_hybrid_better_p05_seed1"]),
         "series_worse": int(r["series_hybrid_worse_p05_seed1"])}
        for _, r in dm.iterrows()]
    # Intervals
    facts["coverage_conformal"] = {m: round(float(summary.loc[m, "coverage"]), 4) for m in summary.index}
    if "coverage_native" in summary.columns:
        facts["coverage_gaussian"] = {m: round(float(summary.loc[m, "coverage_native"]), 4)
                                      for m in summary.index if not pd.isna(summary.loc[m, "coverage_native"])}
    # Cost
    facts["cost_minutes"] = {m: round(float(cost.loc[m, "total_seconds"]) / 60, 2) for m in cost.index}
    facts["energy_wh"] = {m: round(float(cost.loc[m, "energy_kwh_total"]) * 1000, 2) for m in cost.index}
    if primary in cost.index and "arima" in cost.index:
        facts["hybrid_total_with_arima_minutes"] = round(
            float(cost.loc[primary, "total_seconds"] + cost.loc["arima", "total_seconds"]) / 60, 2)
    facts["error_growth_median_h1"] = evaluation["error_growth_median_h1"]
    facts["error_growth_median_h28"] = evaluation["error_growth_median_h28"]
    return facts


def load_cost_table():
    """Import ``cost_table`` from scripts/run_evaluation.py (same superseded/re-timing rules)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("run_evaluation", Path(__file__).resolve().parent / "run_evaluation.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.cost_table


def compute_totals(datasets, cost_table) -> dict:
    """V-1: total tuning + final compute over the datasets, from the cost tables.

    Only phase tuning/final rows count, superseded rows are skipped and the ARIMA re-timing
    (D-026) is applied, because that is what ``cost_table`` does; 'pipeline' wall-clock rows are
    excluded. Hybrid ARIMA-stage costs are not added again.
    """
    seconds = energy = 0.0
    for name in datasets:
        table = cost_table(name)
        if not table.empty:
            seconds += float(table["total_seconds"].sum())
            energy += float(table["energy_kwh_total"].sum())
    return {"total_compute_runtime_hours": round(seconds / 3600, 2),
            "total_compute_energy_kwh": round(energy, 3)}


def main() -> None:
    evaluation = utils.load_json(config.METRIC_DIR / "evaluation_summary.json")
    facts = {name: dataset_facts(name, evaluation[name]) for name in ("m5", "rossmann") if name in evaluation}
    facts.update(compute_totals([d for d in ("m5", "rossmann") if d in evaluation], load_cost_table()))
    utils.save_json(facts, config.METRIC_DIR / "result_facts.json")
    print(json.dumps(facts, indent=1, default=lambda o: o.item() if isinstance(o, np.generic) else str(o)))


if __name__ == "__main__":
    main()
