"""Tune (Optuna) and train one neural model kind for one dataset.

Usage (from ``Code``)::

    python scripts/run_neural.py --dataset m5 --model lstm --trials 15

Tuning: a Tree-structured Parzen Estimator searches the space below. Each trial
trains on the tuning-stage training period (before the validation origins)
with seed 1 and is scored by the mean per-series MASE over the five
validation origins. ``hyb_z`` reuses the hyper-parameters selected for
``hyb_d`` (same residual inputs), so it is not tuned separately.

Final stage: the selected configuration is retrained on the full training
period (before the test origins) with each of the five seeds and forecasts
the test origins.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import optuna  # noqa: E402
import pandas as pd  # noqa: E402

from src import config, experiment, utils  # noqa: E402
from src.evaluation import dataset_summary  # noqa: E402

LOGGER = logging.getLogger("run_neural")


def suggest(trial: optuna.Trial, kind: str) -> dict:
    """Hyper-parameter search space (DECISIONS_LOG D-017)."""
    params = {
        "lookback": trial.suggest_categorical("lookback", [28, 56]),
        "dropout": trial.suggest_float("dropout", 0.0, 0.3),
        "learning_rate": trial.suggest_float("learning_rate", 3e-4, 3e-3, log=True),
        "batch_size": trial.suggest_categorical("batch_size", [64, 128]),
    }
    if kind == "ffnn":
        params["units"] = trial.suggest_categorical("units", [32, 64, 128])
        params["n_layers"] = trial.suggest_int("n_layers", 1, 2)
    else:
        params["units"] = trial.suggest_categorical("units", [16, 32, 64])
    return params


def trial_file(prep, kind: str, number: int) -> Path:
    return config.INTERIM_DIR / f"{prep.name}_{kind}_trial{number:02d}_validation.csv.gz"


def tune(prep, arts, kind: str, n_trials: int) -> dict:
    """Optuna search; the study is stored in SQLite so an interrupted search resumes."""
    task = experiment.NeuralTask(prep, arts, kind, "tune")

    def objective(trial: optuna.Trial) -> float:
        params = suggest(trial, kind)
        table, info, _ = task.train_and_forecast(params, seed=config.PRIMARY_SEED)
        score = experiment.validation_mase(table)
        table.to_csv(trial_file(prep, kind, trial.number), index=False)
        utils.log_experiment(
            {
                "run_id": f"{prep.name}-{kind}-trial{trial.number}",
                "phase": "tuning",
                "dataset": prep.name,
                "series_set": f"{prep.panel.n_series} series",
                "model": kind,
                "parameters_json": json.dumps(params),
                "seed": config.PRIMARY_SEED,
                "split_scheme": f"fit before validation; {len(prep.plan.val_origins)} validation origins",
                "origin_id": "validation",
                "horizon_days": prep.plan.horizon,
                "runtime_s": round(info["train_seconds"], 2),
                "energy_est_kwh": f"{utils.energy_kwh(info['train_seconds']):.6f}",
                "mase": round(score, 5),
                "script": "scripts/run_neural.py",
                "notes": f"epochs={info['epochs']} best_epoch={info['best_epoch']}",
            }
        )
        trial.set_user_attr("train_seconds", info["train_seconds"])
        trial.set_user_attr("epochs", info["epochs"])
        return score

    sampler = optuna.samplers.TPESampler(seed=2026)
    storage = f"sqlite:///{(config.INTERIM_DIR / f'optuna_{prep.name}_{kind}.db').as_posix()}"
    study = optuna.create_study(direction="minimize", sampler=sampler, storage=storage,
                                study_name=f"{prep.name}-{kind}", load_if_exists=True)
    done = sum(t.state == optuna.trial.TrialState.COMPLETE for t in study.trials)
    if done:
        LOGGER.info("%s %s: resuming study with %d completed trials", prep.name, kind, done)
    if n_trials - done > 0:
        study.optimize(objective, n_trials=n_trials - done)
    trials = study.trials_dataframe()
    trials.to_csv(config.METRIC_DIR / f"{prep.name}_{kind}_tuning_trials.csv", index=False)
    best = dict(study.best_params)
    best_table = pd.read_csv(trial_file(prep, kind, study.best_trial.number))
    best_table.to_csv(config.FORECAST_DIR / f"{prep.name}_{kind}_validation.csv.gz", index=False)
    utils.save_json({"best_params": best, "best_value": study.best_value,
                     "best_trial": study.best_trial.number, "n_trials": n_trials},
                    config.METRIC_DIR / f"{prep.name}_{kind}_best_params.json")
    LOGGER.info("%s %s best validation MASE %.4f with %s", prep.name, kind, study.best_value, best)
    return best


def final(prep, arts, kind: str, params: dict, seeds) -> None:
    task = experiment.NeuralTask(prep, arts, kind, "final")
    tables = []
    for seed in seeds:
        done_file = config.INTERIM_DIR / f"{prep.name}_{kind}_seed{seed}_test.csv.gz"
        if done_file.exists():
            tables.append(pd.read_csv(done_file))
            LOGGER.info("%s %s seed %d: loaded checkpoint", prep.name, kind, seed)
            continue
        table, info, model = task.train_and_forecast(params, seed=seed)
        table.to_csv(done_file, index=False)
        tables.append(table)
        model_path = config.MODEL_DIR / f"{prep.name}_{kind}_seed{seed}.keras"
        model.save(model_path)
        summ = dataset_summary(table, ["model"]).iloc[0]
        utils.log_experiment(
            {
                "run_id": f"{prep.name}-{kind}-final-seed{seed}",
                "phase": "final",
                "dataset": prep.name,
                "series_set": f"{prep.panel.n_series} series",
                "model": kind,
                "parameters_json": json.dumps(params),
                "seed": seed,
                "split_scheme": f"fit before test; {len(prep.plan.test_origins)} test origins",
                "origin_id": "test",
                "horizon_days": prep.plan.horizon,
                "runtime_s": round(info["train_seconds"], 2),
                "energy_est_kwh": f"{utils.energy_kwh(info['train_seconds']):.6f}",
                "rmse": round(summ["rmse"], 3),
                "mape": round(summ["mape"], 3),
                "mase": round(summ["mase"], 4),
                "output_path": str(model_path.relative_to(config.CODE_DIR)),
                "script": "scripts/run_neural.py",
                "notes": f"epochs={info['epochs']} best_epoch={info['best_epoch']}",
            }
        )
        LOGGER.info("%s %s seed %d: test MASE %.4f (%.0fs)", prep.name, kind, seed, summ["mase"],
                    info["train_seconds"])
    pd.concat(tables, ignore_index=True).to_csv(
        config.FORECAST_DIR / f"{prep.name}_{kind}_test.csv.gz", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=sorted(config.DATASETS), required=True)
    parser.add_argument("--model", choices=experiment.NEURAL_KINDS, required=True)
    parser.add_argument("--trials", type=int, default=15)
    parser.add_argument("--seeds", type=int, nargs="*", default=list(config.SEEDS))
    parser.add_argument("--skip-tuning", action="store_true", help="reuse saved best parameters")
    args = parser.parse_args()
    utils.setup_logging()
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    config.ensure_output_dirs()
    prep = experiment.prepare(args.dataset)
    arts = experiment.load_stat_artifacts(prep) if args.model.startswith("hyb") else None

    if args.model == "hyb_z":
        source = config.METRIC_DIR / f"{args.dataset}_hyb_d_best_params.json"
        params = utils.load_json(source)["best_params"]
        # hyb_z needs its own validation forecasts for interval calibration
        task = experiment.NeuralTask(prep, arts, "hyb_z", "tune")
        table, info, _ = task.train_and_forecast(params, seed=config.PRIMARY_SEED)
        table.to_csv(config.FORECAST_DIR / f"{args.dataset}_hyb_z_validation.csv.gz", index=False)
        utils.save_json({"best_params": params, "best_value": experiment.validation_mase(table),
                         "source": "hyb_d tuning (shared configuration)"},
                        config.METRIC_DIR / f"{args.dataset}_hyb_z_best_params.json")
    elif args.skip_tuning:
        params = utils.load_json(config.METRIC_DIR / f"{args.dataset}_{args.model}_best_params.json")["best_params"]
    else:
        params = tune(prep, arts, args.model, args.trials)
    final(prep, arts, args.model, params, args.seeds)


if __name__ == "__main__":
    main()
