"""Evaluate every model on the test origins and produce the report tables and figures.

Usage (from ``Code``)::

    python scripts/run_evaluation.py

Steps:
1. Load the statistical forecasts and the neural forecasts (five seeds).
2. Add horizon-specific split-conformal 95% intervals to every model, calibrated
   on that model's validation-origin errors (for neural models: the selected
   configuration's validation run).
3. Point and interval metrics per model (mean of per-series values); for
   neural models also per seed (mean and standard deviation across seeds).
4. Diebold-Mariano tests (HLN-corrected, h = 28) of the primary hybrid against
   every other model, on the cross-series mean of scaled losses, per seed.
5. Runtime and estimated energy from EXPERIMENT_LOG.csv.
6. Figures: accuracy by horizon, seed stability, interval coverage by horizon,
   example forecasts, one-step versus multi-step ARIMA error growth.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src import config, evaluation as ev, experiment, statistical_tests as st, utils  # noqa: E402
from src.visualisation import LABELS, STYLES, apply_style, save  # noqa: E402

TABLE_DIR = config.OUTPUT_DIR / "tables"
NEURAL = ["ffnn", "lstm", "hyb_d", "hyb_ms", "hyb_z"]
ORDER = ["snaive", "arima", "ets", "ffnn", "lstm", "hyb_d", "hyb_ms", "hyb_z"]


def load_forecasts(name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    stat = pd.read_csv(config.FORECAST_DIR / f"{name}_statistical.csv.gz")
    val = [stat[stat["stage"] == "validation"]]
    test = [stat[stat["stage"] == "test"]]
    for kind in NEURAL:
        vpath = config.FORECAST_DIR / f"{name}_{kind}_validation.csv.gz"
        tpath = config.FORECAST_DIR / f"{name}_{kind}_test.csv.gz"
        if vpath.exists() and tpath.exists():
            val.append(pd.read_csv(vpath))
            test.append(pd.read_csv(tpath))
    return pd.concat(val, ignore_index=True), pd.concat(test, ignore_index=True)


def add_intervals(val: pd.DataFrame, test: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Keep native intervals as *_native and add conformal intervals for all models."""
    out = []
    for model, g in test.groupby("model"):
        q = ev.conformal_quantiles(val[val["model"] == model], horizon)
        g = g.rename(columns={"lower": "lower_native", "upper": "upper_native"})
        g = ev.apply_conformal(g, q)
        out.append(g)
    return pd.concat(out, ignore_index=True)


def metric_tables(test: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    per_seed = ev.dataset_summary(test, ["model", "seed"])
    native = test.dropna(subset=["lower_native"]).copy()
    if not native.empty:
        native = native.drop(columns=["lower", "upper"]).rename(
            columns={"lower_native": "lower", "upper_native": "upper"})
        nat = ev.dataset_summary(native, ["model", "seed"])[["model", "seed", "coverage", "width_scaled",
                                                            "winkler_scaled"]]
        nat = nat.rename(columns={"coverage": "coverage_native", "width_scaled": "width_native",
                                  "winkler_scaled": "winkler_native"})
        per_seed = per_seed.merge(nat, on=["model", "seed"], how="left")
    cols = ["rmse", "mae", "mape", "mase", "coverage", "width_scaled", "winkler_scaled",
            "coverage_native", "width_native", "winkler_native"]
    cols = [c for c in cols if c in per_seed]
    summary = per_seed.groupby("model")[cols].mean()
    summary["mase_sd_seeds"] = per_seed.groupby("model")["mase"].std().fillna(0.0)
    summary["n_seeds"] = per_seed.groupby("model")["seed"].nunique()
    summary = summary.reindex([m for m in ORDER if m in summary.index])
    return summary.reset_index(), per_seed


def scaled_loss_series(test: pd.DataFrame, model: str, seed, kind: str) -> pd.Series:
    """Cross-series mean of scaled loss per test day (index: day_index)."""
    g = test[(test["model"] == model) & (test["seed"] == seed) & test["eval"]]
    err = (g["actual"] - g["forecast"]) / g["scale"]
    loss = err.abs() if kind == "absolute" else err ** 2
    return loss.groupby(g["day_index"]).mean()


def per_series_dm(test, a, sa, b, sb, kind, horizon):
    wins = losses = 0
    for sid in test["series_id"].unique():
        ga = test[(test.model == a) & (test.seed == sa) & (test.series_id == sid) & test["eval"]].set_index("day_index")
        gb = test[(test.model == b) & (test.seed == sb) & (test.series_id == sid) & test["eval"]].set_index("day_index")
        common = ga.index.intersection(gb.index)
        ea = (ga.loc[common, "actual"] - ga.loc[common, "forecast"]).to_numpy()
        eb = (gb.loc[common, "actual"] - gb.loc[common, "forecast"]).to_numpy()
        res = st.dm_test(ea, eb, horizon, kind)
        if res.p_value < 0.05:
            if res.statistic > 0:
                wins += 1  # model a has the larger loss -> b significantly better
            else:
                losses += 1
    return wins, losses


def dm_table(test: pd.DataFrame, primary: str, horizon: int) -> pd.DataFrame:
    """DM-HLN tests of the primary hybrid against every other model.

    For each seed of the primary hybrid and each loss, the comparisons with the
    other models form one family whose p-values are Holm-adjusted. A positive
    statistic means the other model has the larger loss (the hybrid is better).
    Statistical models have a single run (seed 0), which is paired with every
    hybrid seed; neural models are paired seed by seed.
    """
    seeds = sorted(test.loc[test["model"] == primary, "seed"].unique())
    others = [m for m in ORDER if m in test["model"].unique() and m != primary]
    raw = {}
    for kind in ("absolute", "squared"):
        for s in seeds:
            for other in others:
                other_seeds = sorted(test.loc[test["model"] == other, "seed"].unique())
                so = s if s in other_seeds else other_seeds[0]
                la = scaled_loss_series(test, other, so, kind)
                lb = scaled_loss_series(test, primary, s, kind)
                common = la.index.intersection(lb.index)
                raw[(kind, s, other)] = st.diebold_mariano((la.loc[common] - lb.loc[common]).to_numpy(), horizon)
            adj = st.holm_adjust([raw[(kind, s, o)].p_value for o in others])
            for o, a in zip(others, adj):
                raw[(kind, s, o)] = (raw[(kind, s, o)], a)
    rows = []
    for other in others:
        other_seeds = sorted(test.loc[test["model"] == other, "seed"].unique())
        for kind in ("absolute", "squared"):
            res = [raw[(kind, s, other)] for s in seeds]
            stats = [r.statistic for r, _ in res]
            pvals = [r.p_value for r, _ in res]
            padj = [a for _, a in res]
            means = [r.mean_differential for r, _ in res]
            s1 = seeds[0]
            so1 = s1 if s1 in other_seeds else other_seeds[0]
            better, worse = per_series_dm(test, other, so1, primary, s1, kind, horizon)
            rows.append({
                "comparison": f"{primary} vs {other}",
                "other": other,
                "loss": kind,
                "n_days": res[0][0].n,
                "mean_loss_diff_seed1": means[0],
                "dm_stat_seed1": stats[0],
                "p_value_seed1": pvals[0],
                "p_holm_seed1": padj[0],
                "median_p_over_seeds": float(np.median(pvals)),
                "median_p_holm_over_seeds": float(np.median(padj)),
                "seeds_hybrid_better_holm05": int(sum((a < 0.05) and (z > 0) for a, z in zip(padj, stats))),
                "seeds_hybrid_worse_holm05": int(sum((a < 0.05) and (z < 0) for a, z in zip(padj, stats))),
                "seeds_hybrid_better_p05": int(sum((p < 0.05) and (z > 0) for p, z in zip(pvals, stats))),
                "seeds_hybrid_worse_p05": int(sum((p < 0.05) and (z < 0) for p, z in zip(pvals, stats))),
                "n_seeds": len(seeds),
                "series_hybrid_better_p05_seed1": better,
                "series_hybrid_worse_p05_seed1": worse,
                "variance_method_seed1": res[0][0].variance_method,
            })
    return pd.DataFrame(rows)


def horizon_table(test: pd.DataFrame) -> pd.DataFrame:
    """Mean MASE by model and week of the horizon (days 1-7, 8-14, 15-21, 22-28), averaged over seeds."""
    g = test[test["eval"]].copy()
    g["week"] = (g["horizon"] - 1) // 7 + 1
    g["se"] = (g["actual"] - g["forecast"]).abs() / g["scale"]
    per = g.groupby(["model", "seed", "series_id", "week"])["se"].mean().groupby(["model", "seed", "week"]).mean()
    out = per.groupby(["model", "week"]).mean().unstack("week")
    out.columns = [f"mase_week{c}" for c in out.columns]
    return out.reindex([m for m in ORDER if m in out.index]).reset_index()


def cost_table(name: str) -> pd.DataFrame:
    log = pd.read_csv(config.EXPERIMENT_LOG)
    log = log[log["dataset"] == name]
    rows = []
    for model in ORDER:
        g = log[log["model"] == model]
        if g.empty:
            continue
        tune = g[g["phase"] == "tuning"]["runtime_s"].sum()
        final = g[g["phase"] == "final"]["runtime_s"]
        rows.append({
            "model": model,
            "tuning_runs": int((g["phase"] == "tuning").sum()),
            "tuning_seconds": tune,
            "final_seconds_per_run": final.mean(),
            "total_seconds": tune + final.sum(),
            "energy_kwh_total": utils.energy_kwh(tune + final.sum()),
        })
    out = pd.DataFrame(rows)
    # A11: the hybrids need the ARIMA stage (residuals and forecast paths), so their full cost includes it.
    arima_total = float(out.loc[out["model"] == "arima", "total_seconds"].sum()) if not out.empty else 0.0
    out["total_with_arima_seconds"] = np.where(out["model"].str.startswith("hyb"),
                                               out["total_seconds"] + arima_total, out["total_seconds"])
    out["energy_with_arima_kwh"] = [utils.energy_kwh(s) for s in out["total_with_arima_seconds"]]
    return out


def fig_by_horizon(test, name):
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    for model in [m for m in ORDER if m in test["model"].unique()]:
        g = test[(test.model == model) & test["eval"]]
        g = g.assign(se=(g["actual"] - g["forecast"]).abs() / g["scale"])
        curve = g.groupby(["seed", "horizon"])["se"].mean().groupby("horizon").mean()
        ax.plot(curve.index, curve.values, label=LABELS[model], linewidth=1.1, markersize=3, markevery=3,
                **STYLES[model])
    ax.set_xlabel("Forecast horizon (days ahead)")
    ax.set_ylabel("Scaled absolute error (MASE units)")
    ax.legend(ncol=4, fontsize=7, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.22))
    return save(fig, f"res_{name}_mase_by_horizon")


def fig_seed_stability(per_seed, name):
    nn = [m for m in ORDER if m in per_seed["model"].unique() and per_seed[per_seed.model == m]["seed"].nunique() > 1]
    stat = [m for m in ORDER if m in per_seed["model"].unique() and m not in nn]
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    data = [per_seed[per_seed.model == m]["mase"].to_numpy() for m in nn]
    ax.boxplot(data, tick_labels=[LABELS[m] for m in nn], widths=0.5)
    for m in stat:
        v = per_seed[per_seed.model == m]["mase"].iloc[0]
        ax.axhline(v, linestyle=STYLES[m]["linestyle"], color=STYLES[m]["color"], linewidth=1, label=LABELS[m])
    ax.set_ylabel("Test MASE (five seeds)")
    ax.tick_params(axis="x", labelrotation=15)
    ax.legend(fontsize=7, frameon=False, loc="upper right")
    return save(fig, f"res_{name}_seed_stability")


def fig_coverage(test, name):
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    for model in [m for m in ORDER if m in test["model"].unique()]:
        g = test[(test.model == model) & test["eval"]]
        cov = ((g["actual"] >= g["lower"]) & (g["actual"] <= g["upper"])).groupby([g["seed"], g["horizon"]]).mean()
        curve = cov.groupby("horizon").mean()
        ax.plot(curve.index, curve.values, label=LABELS[model], linewidth=1, markersize=3, markevery=4,
                **STYLES[model])
    ax.axhline(0.95, color="black", linewidth=0.8)
    ax.set_ylim(0.5, 1.0)
    ax.set_xlabel("Forecast horizon (days ahead)")
    ax.set_ylabel("Empirical coverage of 95% interval")
    ax.legend(ncol=4, fontsize=7, frameon=False, loc="lower center")
    return save(fig, f"res_{name}_coverage_by_horizon")


def fig_example(test, name, primary, series_id=None):
    sid = series_id or sorted(test["series_id"].unique())[0]
    origins = sorted(test["origin_index"].unique())
    o = origins[len(origins) // 2]
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    base = test[(test.series_id == sid) & (test.origin_index == o)]
    act = base[base.model == "arima"].sort_values("horizon")
    ax.plot(pd.to_datetime(act["date"]), act["actual"].where(act["eval"]), color="black", linewidth=1.4,
            label="Actual")
    for model in ("arima", "lstm", primary):
        g = base[(base.model == model) & (base.seed == base[base.model == model]["seed"].min())].sort_values("horizon")
        ax.plot(pd.to_datetime(g["date"]), g["forecast"].where(g["eval"]), label=LABELS[model], linewidth=1,
                markersize=3, **STYLES[model])
        if model == primary:
            ax.fill_between(pd.to_datetime(g["date"]), g["lower"].where(g["eval"]), g["upper"].where(g["eval"]),
                            color="0.85", label="95% interval (hybrid)")
    ax.set_ylabel("Daily sales")
    ax.set_xlabel("Date")
    ax.legend(fontsize=7, frameon=False, ncol=3)
    fig.autofmt_xdate()
    return save(fig, f"res_{name}_example_{sid}"), sid, o


def fig_error_growth(prep, arts, name):
    """One-step in-sample ARIMA residual spread versus multi-step validation error spread."""
    y, mask = prep.panel.y, prep.model_mask
    paths = arts.paths_tune
    H = prep.plan.horizon
    ratios = []
    for s in range(prep.panel.n_series):
        r = arts.resid_tune[s, : prep.plan.val_start]
        sd1 = np.nanstd(r)
        errs = np.full((len(prep.plan.val_origins), H), np.nan)
        for i, o in enumerate(prep.plan.val_origins):
            ok = mask[s, o: o + H]
            errs[i] = np.where(ok, y[s, o: o + H] - paths[s, o], np.nan)
        ratios.append(np.sqrt(np.nanmean(errs ** 2, axis=0)) / sd1)
    ratios = np.array(ratios)
    fig, ax = plt.subplots(figsize=(7.2, 2.8))
    ax.plot(range(1, H + 1), np.nanmedian(ratios, axis=0), color="black", marker="o", markersize=3, label="Median")
    ax.fill_between(range(1, H + 1), np.nanpercentile(ratios, 25, axis=0), np.nanpercentile(ratios, 75, axis=0),
                    color="0.85", label="Interquartile range across series")
    ax.axhline(1.0, color="0.4", linestyle="--", linewidth=0.8, label="In-sample one-step residual s.d.")
    ax.set_xlabel("Forecast horizon (days ahead)")
    ax.set_ylabel("Out-of-sample RMSE / in-sample residual s.d.")
    ax.legend(fontsize=7, frameon=False)
    return save(fig, f"res_{name}_error_growth"), ratios


def main() -> None:
    utils.setup_logging()
    apply_style()
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    for name in ("m5", "rossmann"):
        prep = experiment.prepare(name)
        arts = experiment.load_stat_artifacts(prep)
        val, test = load_forecasts(name)
        test = add_intervals(val, test, prep.plan.horizon)
        test.to_csv(config.FORECAST_DIR / f"{name}_all_test_with_intervals.csv.gz", index=False)
        summary, per_seed = metric_tables(test)
        summary.to_csv(TABLE_DIR / f"{name}_test_summary.csv", index=False)
        per_seed.to_csv(TABLE_DIR / f"{name}_test_per_seed.csv", index=False)
        per_series = ev.summarise(test, ["model", "seed", "series_id"])
        per_series.to_csv(TABLE_DIR / f"{name}_test_per_series.csv", index=False)
        hybrids = [h for h in ("hyb_d", "hyb_ms", "hyb_z") if h in test["model"].unique()]
        val_scores = {h: experiment.validation_mase(val[val.model == h]) for h in hybrids}
        primary = min(val_scores, key=val_scores.get) if val_scores else None
        dm = dm_table(test, primary, prep.plan.horizon) if primary else pd.DataFrame()
        dm.to_csv(TABLE_DIR / f"{name}_dm_tests.csv", index=False)
        horizon_table(test).to_csv(TABLE_DIR / f"{name}_mase_by_week.csv", index=False)
        cost = cost_table(name)
        cost.to_csv(TABLE_DIR / f"{name}_cost.csv", index=False)
        val_summary = ev.dataset_summary(val, ["model"])
        val_summary.to_csv(TABLE_DIR / f"{name}_validation_summary.csv", index=False)
        figs = {
            "by_horizon": fig_by_horizon(test, name),
            "seed_stability": fig_seed_stability(per_seed, name),
            "coverage": fig_coverage(test, name),
        }
        ex_path, ex_sid, ex_origin = fig_example(test, name, primary or "lstm")
        figs["example"] = ex_path
        figs["error_growth"], ratios = fig_error_growth(prep, arts, name)
        results[name] = {
            "primary_hybrid": primary,
            "hybrid_validation_mase": val_scores,
            "example_series": ex_sid,
            "example_origin_date": str(prep.panel.dates[ex_origin].date()),
            "error_growth_median_h1": float(np.nanmedian(ratios[:, 0])),
            "error_growth_median_h28": float(np.nanmedian(ratios[:, -1])),
            "figures": figs,
        }
        print(f"\n===== {name}: primary hybrid = {primary} (validation MASE {val_scores})")
        print(summary.round(4).to_string(index=False))
        print(dm.round(4).to_string(index=False))
        print(cost.round(2).to_string(index=False))
    utils.save_json(results, config.METRIC_DIR / "evaluation_summary.json")


if __name__ == "__main__":
    main()
