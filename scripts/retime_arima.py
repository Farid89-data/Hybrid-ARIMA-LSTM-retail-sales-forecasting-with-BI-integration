"""Re-time the ARIMA order search for one series without changing any saved output.

Used when a recorded fit time is invalid (for example, the machine slept during the search).
The selected order is compared with the saved specification; the timing is written to
outputs/metrics/<dataset>_arima_retime_<series>.json.

Usage (from Code/):  PYTHONHASHSEED=0 python scripts/retime_arima.py --dataset rossmann --series store_421
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import config, experiment, statistical_models as sm, utils  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--series", required=True)
    args = parser.parse_args()
    prep = experiment.prepare(args.dataset)
    s = list(prep.panel.series_ids).index(args.series)
    plan = prep.plan
    y_s, ex = prep.y_fit[s], prep.exog[s]
    spec_t = sm.select_arima(y_s[: plan.val_start], ex[: plan.val_start])
    spec_f = sm.refit_arima(spec_t, y_s[: plan.test_start], ex[: plan.test_start])
    saved = json.loads((config.METRIC_DIR / f"{args.dataset}_statistical_specs.json").read_text())
    saved = saved if isinstance(saved, list) else saved.get("specs", saved)
    old = next(r for r in saved if r["series_id"] == args.series)
    out = {
        "series_id": args.series,
        "arima_order": list(spec_t.order),
        "arima_seasonal_order": list(spec_t.seasonal_order),
        "same_order_as_saved": list(spec_t.order) == list(old["arima_order"])
        and list(spec_t.seasonal_order) == list(old["arima_seasonal_order"]),
        "arima_select_seconds": spec_t.fit_seconds,
        "arima_refit_seconds": spec_f.fit_seconds,
        "saved_arima_select_seconds": old["arima_select_seconds"],
        "saved_arima_refit_seconds": old["arima_refit_seconds"],
    }
    utils.save_json(out, config.METRIC_DIR / f"{args.dataset}_arima_retime_{args.series}.json")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
