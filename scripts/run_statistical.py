"""Fit the statistical benchmarks (seasonal naive, ARIMA, ETS) for one dataset.

Usage (from ``Code``)::

    python scripts/run_statistical.py --dataset m5

Outputs:
    outputs/forecasts/<dataset>_statistical.csv.gz   validation and test forecasts
    outputs/metrics/<dataset>_statistical_specs.json selected orders and timings
    outputs/interim/<dataset>_arima_artifacts.npz    residuals and multi-step paths
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import config, experiment, utils  # noqa: E402
from src.evaluation import dataset_summary  # noqa: E402

LOGGER = logging.getLogger("run_statistical")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=sorted(config.DATASETS), required=True)
    args = parser.parse_args()
    utils.setup_logging()
    config.ensure_output_dirs()
    prep = experiment.prepare(args.dataset)
    utils.save_json(prep.plan.describe(), config.METRIC_DIR / f"{args.dataset}_split_plan.json")

    with utils.timer() as t:
        table, arts = experiment.run_statistical(prep)
    out = config.FORECAST_DIR / f"{args.dataset}_statistical.csv.gz"
    table.to_csv(out, index=False)
    experiment.save_stat_artifacts(prep, arts)

    summary = dataset_summary(table, ["model", "stage"])
    LOGGER.info("\n%s", summary.to_string(index=False))
    for spec_model in ("snaive", "arima", "ets"):
        test_row = summary[(summary["model"] == spec_model) & (summary["stage"] == "test")].iloc[0]
        if spec_model == "arima":
            secs = sum(s["arima_select_seconds"] + s["arima_refit_seconds"] for s in arts.specs)
        elif spec_model == "ets":
            secs = sum(s["ets_select_seconds"] + s["ets_refit_seconds"] for s in arts.specs)
        else:
            secs = 0.0
        utils.log_experiment(
            {
                "run_id": f"{args.dataset}-{spec_model}-final",
                "phase": "final",
                "dataset": args.dataset,
                "series_set": f"{prep.panel.n_series} series",
                "model": spec_model,
                "parameters_json": json.dumps({"see": f"metrics/{args.dataset}_statistical_specs.json"}),
                "seed": 0,
                "split_scheme": f"rolling origin, {len(prep.plan.test_origins)} test origins",
                "origin_id": "all",
                "horizon_days": prep.plan.horizon,
                "runtime_s": round(secs, 2),
                "energy_est_kwh": f"{utils.energy_kwh(secs):.6f}",
                "rmse": round(test_row["rmse"], 3),
                "mape": round(test_row["mape"], 3),
                "mase": round(test_row["mase"], 4),
                "pi95_coverage": round(test_row["coverage"], 4) if spec_model != "snaive" else "",
                "output_path": str(out.relative_to(config.CODE_DIR)),
                "script": "scripts/run_statistical.py",
                "notes": "metrics = mean of per-series values on scored test days",
            }
        )
    LOGGER.info("Statistical stage finished in %.1f s", t["seconds"])


if __name__ == "__main__":
    main()
