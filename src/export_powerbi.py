"""Export a star schema of actuals, forecasts and metrics for the Power BI dashboard.

Tables written to ``dashboard/data`` (CSV, UTF-8, ISO dates):

* ``dim_date``      one row per calendar day of both datasets
* ``dim_series``    stores (M5) and sampled stores (Rossmann) with attributes
* ``dim_model``     the eight forecasting models
* ``fact_actuals``  daily sales with closure flag and data split label
* ``fact_forecast`` test-period forecasts with 95% conformal intervals
                    (neural models: seed 1, the run used for the significance tests)
* ``fact_metrics``  per-series test metrics for every model (seed 1 for neural models)
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


def acceptance_values(scored: pd.DataFrame) -> dict:
    """Reference values that the dashboard measures must reproduce (test plan TP-07 to TP-13).

    ``scored`` holds the exported forecast rows of one dataset with ``scored == 1``
    (columns ``model``, ``series_key``, ``actual``, ``forecast``, ``lower``,
    ``upper``, ``scale``). MASE is the mean of the per-store MASE values, as in
    the report; the DAX measure "MASE (store average)" reproduces it.
    """
    out = {}
    for model, g in scored.groupby("model"):
        abs_err = (g["actual"] - g["forecast"]).abs()
        per_store_mase = (abs_err / g["scale"]).groupby(g["series_key"]).mean()
        out[model] = {
            "total_actual_scored": float(g["actual"].sum()),
            "total_forecast_scored": float(g["forecast"].sum()),
            "mean_abs_error": float(abs_err.mean()),
            "coverage": float(((g["actual"] >= g["lower"]) & (g["actual"] <= g["upper"])).mean()),
            "mase_store_average": float(per_store_mase.mean()),
            "stockout_risk_days": int((g["actual"] > g["upper"]).sum()),
            "overstock_risk_days": int((g["actual"] < g["lower"]).sum()),
        }
    return out


def export(primary_seed: int = config.PRIMARY_SEED) -> dict:
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
        test = test[(test["seed"] == 0) | (test["seed"] == primary_seed)].copy()
        test["series_key"] = label + "|" + test["series_id"]
        test["dataset"] = label
        test["scored"] = test["eval"].astype(int)
        keep = ["series_key", "dataset", "model", "origin_date", "date", "horizon", "actual", "forecast",
                "lower", "upper", "scale", "scored"]
        forecasts.append(test[keep])
        per = pd.read_csv(config.OUTPUT_DIR / "tables" / f"{name}_test_per_series.csv")
        per = per[(per["seed"] == 0) | (per["seed"] == primary_seed)].copy()
        per["series_key"] = label + "|" + per["series_id"]
        per["dataset"] = label
        metrics.append(per[["series_key", "dataset", "model", "rmse", "mae", "mape", "mase", "coverage",
                            "width_scaled"]])
        scored = test[test["scored"] == 1]
        acceptance[label] = acceptance_values(scored)
    dim_date = pd.concat(dates).drop_duplicates().sort_values("date")
    dim_date["year"] = dim_date["date"].dt.year
    dim_date["month"] = dim_date["date"].dt.month
    dim_date["month_name"] = dim_date["date"].dt.strftime("%b")
    dim_date["iso_week"] = dim_date["date"].dt.isocalendar().week.astype(int)
    dim_date["weekday"] = dim_date["date"].dt.strftime("%a")
    dim_date["weekday_number"] = dim_date["date"].dt.dayofweek + 1
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
