"""Export a star schema of actuals, forecasts and metrics for the Power BI dashboard.

Tables written to ``dashboard/data`` (CSV, UTF-8, ISO dates):

* ``dim_date``      one row per calendar day of both datasets
* ``dim_series``    stores (M5) and sampled stores (Rossmann) with attributes
* ``dim_model``     the eight forecasting models
* ``fact_actuals``  daily sales with closure flag and data split label
* ``fact_forecast`` test-period forecasts with 95% conformal intervals; column ``seed``
                    (0 for the three statistical models, 1 to 5 for the five network models)
* ``fact_metrics``  per-series test metrics for every model and seed; averaging ``mase`` over
                    all rows gives the report's five-seed mean (A-F-8)
* ``acceptance_values.json``  reference totals computed in Python; the dashboard's
                    DAX measures must reproduce them (test plan, Appendix E)
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import config, experiment

DASH_DIR = config.CODE_DIR / "dashboard" / "data"
MODEL_FAMILY = {
    "snaive": "Benchmark", "arima": "Statistical", "ets": "Statistical", "ffnn": "Neural",
    "lstm": "Neural", "hyb_d": "Hybrid", "hyb_ms": "Hybrid", "hyb_z": "Hybrid",
}


def build_dim_date(dates: pd.Series) -> pd.DataFrame:
    """Calendar dimension. ``week_start`` (the Monday of each week) is the week level for
    drill-down; unlike ``iso_week`` it does not repeat from year to year (D08)."""
    dim = pd.DataFrame({"date": pd.to_datetime(pd.Series(dates))}).drop_duplicates().sort_values("date")
    dim["year"] = dim["date"].dt.year
    dim["month"] = dim["date"].dt.month
    dim["month_name"] = dim["date"].dt.strftime("%b")
    dim["iso_week"] = dim["date"].dt.isocalendar().week.astype(int)
    dim["week_start"] = dim["date"] - pd.to_timedelta(dim["date"].dt.dayofweek, unit="D")
    dim["weekday"] = dim["date"].dt.strftime("%a")
    dim["weekday_number"] = dim["date"].dt.dayofweek + 1
    return dim.reset_index(drop=True)


def acceptance_values(scored: pd.DataFrame) -> dict:
    """Reference values that the dashboard measures must reproduce (test plan TP-07 to TP-13).

    ``scored`` holds the exported forecast rows of one dataset with ``scored == 1``
    (columns ``model``, ``series_key``, ``actual``, ``forecast``, ``lower``,
    ``upper``, ``scale`` and, optionally, ``seed``). Each network model has five seeds
    (A-F-8), so the values are defined per seed and then averaged over the seeds present:

    * ``mase_store_average``: per seed, the mean over stores of the per-store MASE; then the
      mean over seeds. This is the report's test MASE (``<ds>_test_summary.csv``) and equals
      the DAX ``AVERAGE ( fact_metrics[mase] )`` when every seed has the same stores.
    * totals and risk-day counts: the mean over seeds of the per-seed total / count (the DAX
      measures divide the sum by the number of seeds in the selection).
    * ``mean_abs_error`` and ``coverage``: means over all rows (equal rows per seed).
    """
    if "seed" not in scored.columns:
        scored = scored.assign(seed=0)
    out = {}
    for model, g in scored.groupby("model"):
        n_seeds = g["seed"].nunique()
        abs_err = (g["actual"] - g["forecast"]).abs()
        per_store_mase = (abs_err / g["scale"]).groupby([g["seed"], g["series_key"]]).mean()
        mase_per_seed = per_store_mase.groupby(level="seed").mean()
        out[model] = {
            "n_seeds": int(n_seeds),
            "total_actual_scored": float(g["actual"].sum() / n_seeds),
            "total_forecast_scored": float(g["forecast"].sum() / n_seeds),
            "mean_abs_error": float(abs_err.mean()),
            "coverage": float(((g["actual"] >= g["lower"]) & (g["actual"] <= g["upper"])).mean()),
            "mase_store_average": float(mase_per_seed.mean()),
            "stockout_risk_days": float((g["actual"] > g["upper"]).sum() / n_seeds),
            "overstock_risk_days": float((g["actual"] < g["lower"]).sum() / n_seeds),
        }
    return out


def check_against_report(values: dict, name: str, tol: float = 1e-6) -> None:
    """The dashboard MASE must equal the report's test MASE for every model (A-F-8)."""
    summary = pd.read_csv(config.OUTPUT_DIR / "tables" / f"{name}_test_summary.csv").set_index("model")
    for model, v in values.items():
        report = float(summary.loc[model, "mase"])
        v["report_test_mase"] = report
        if abs(v["mase_store_average"] - report) > tol:
            raise ValueError(f"{name}/{model}: dashboard MASE {v['mase_store_average']:.6f} "
                             f"differs from the report's {report:.6f}")


def export() -> dict:
    DASH_DIR.mkdir(parents=True, exist_ok=True)
    dates, series, actuals, forecasts, metrics = [], [], [], [], []
    acceptance = {}
    for name in ("m5", "rossmann"):
        prep = experiment.prepare(name)
        panel, plan = prep.panel, prep.plan
        label = "M5" if name == "m5" else "Rossmann"
        dates.append(pd.DataFrame({"date": panel.dates}))
        meta = panel.meta.copy()
        meta["dataset"] = label
        meta["series_key"] = label + "|" + meta["series_id"]
        series.append(meta)
        split = np.where(np.arange(panel.n_days) < plan.val_start, "Training",
                         np.where(np.arange(panel.n_days) < plan.test_start, "Validation", "Test"))
        for s, sid in enumerate(panel.series_ids):
            actuals.append(pd.DataFrame({
                "series_key": f"{label}|{sid}", "dataset": label, "date": panel.dates,
                "sales": panel.y[s], "closed": panel.closed[s].astype(int), "split": split,
            }))
        test = pd.read_csv(config.FORECAST_DIR / f"{name}_all_test_with_intervals.csv.gz")
        test = test.copy()  # all seeds: statistical 0, networks 1 to 5
        test["series_key"] = label + "|" + test["series_id"]
        test["dataset"] = label
        test["scored"] = test["eval"].astype(int)
        keep = ["series_key", "dataset", "model", "origin_date", "date", "horizon", "seed", "actual", "forecast",
                "lower", "upper", "scale", "scored"]
        forecasts.append(test[keep])
        per = pd.read_csv(config.OUTPUT_DIR / "tables" / f"{name}_test_per_series.csv")
        per["series_key"] = label + "|" + per["series_id"]
        per["dataset"] = label
        metrics.append(per[["series_key", "dataset", "model", "seed", "rmse", "mae", "mape", "mase", "coverage",
                            "width_scaled"]])
        scored = test[test["scored"] == 1]
        acceptance[label] = acceptance_values(scored)
        check_against_report(acceptance[label], name)
    dim_date = build_dim_date(pd.concat(dates)["date"])
    dim_model = pd.DataFrame({
        "model": list(experiment.MODEL_LABELS),
        "model_label": list(experiment.MODEL_LABELS.values()),
        "family": [MODEL_FAMILY[m] for m in experiment.MODEL_LABELS],
    })
    outputs = {
        "dim_date": dim_date,
        "dim_series": pd.concat(series, ignore_index=True),
        "dim_model": dim_model,
        "fact_actuals": pd.concat(actuals, ignore_index=True),
        "fact_forecast": pd.concat(forecasts, ignore_index=True),
        "fact_metrics": pd.concat(metrics, ignore_index=True),
    }
    for table, frame in outputs.items():
        frame.to_csv(DASH_DIR / f"{table}.csv", index=False, date_format="%Y-%m-%d")
    (DASH_DIR / "acceptance_values.json").write_text(json.dumps(acceptance, indent=2), encoding="utf-8")
    return {t: len(f) for t, f in outputs.items()}
