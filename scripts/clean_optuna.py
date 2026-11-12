"""Back up the Optuna databases and mark interrupted (RUNNING) trials as FAIL (D-029).

Run only while no pipeline process is running. Rewrites the tuning-trials CSV of every finished
study with COMPLETE trials only. Usage (from Code/):  python scripts/clean_optuna.py [--relabel]

--relabel (V-3) only rewrites ``failed_reason`` of FAIL trials that carry the old text
"interrupted run (process stopped 11 Nov 2026 03:15)" with one built from the trial's own start time.
"""
import json
import shutil
import sqlite3
import sys
from datetime import date
from pathlib import Path

import optuna
from optuna.trial import TrialState

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import config, tuning_cleanup  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_chunks  # noqa: E402


def relabel(dbs) -> None:
    """Rewrite the old, wrongly dated failed_reason of FAIL trials (no state or value is touched)."""
    for db in dbs:
        storage = optuna.storages.RDBStorage(tuning_cleanup.storage_url(db))
        for summary in optuna.study.get_all_study_summaries(storage):
            study = optuna.load_study(study_name=summary.study_name, storage=storage)
            changed = False
            for trial in study.get_trials(deepcopy=False, states=(TrialState.FAIL,)):
                if trial.user_attrs.get("failed_reason") == tuning_cleanup.OLD_WRONG_REASON:
                    new = tuning_cleanup.reason_for(trial)
                    # Optuna refuses to update a finished trial through its API (UpdateFinishedTrialError),
                    # so the single attribute row is rewritten directly; state and values are untouched.
                    with sqlite3.connect(db) as con:
                        con.execute("UPDATE trial_user_attributes SET value_json = ? WHERE trial_id = ? AND key = ?",
                                    (json.dumps(new), trial._trial_id, "failed_reason"))
                    print(f"{db.name}: study {summary.study_name} trial {trial.number}: {new}")
                    run_chunks.log(f"relabelled failed_reason of trial {trial.number} of study "
                                   f"{summary.study_name} ({db.name}): {new}")
                    changed = True
            ds, kind = db.stem[len("optuna_"):].split("_", 1)
            csv_path = config.METRIC_DIR / f"{ds}_{kind}_tuning_trials.csv"
            if changed and csv_path.exists():
                study = optuna.load_study(study_name=summary.study_name, storage=storage)
                print(f"{csv_path.name}: {tuning_cleanup.write_trials_csv(study, csv_path)}")


def main() -> None:
    live = run_chunks.find_pipeline_processes()
    if live:
        sys.exit(f"pipeline processes are running ({[p.pid for p in live]}); pause first")
    dbs = sorted(config.INTERIM_DIR.glob("optuna_*.db"))
    backup = config.INTERIM_DIR / f"backup_{date.today():%Y-%m-%d}"
    backup.mkdir(exist_ok=True)
    for db in dbs:
        shutil.copy2(db, backup / db.name)
    print(f"backed up {len(dbs)} databases to {backup}")
    if "--relabel" in sys.argv:
        relabel(dbs)
        return
    for db in dbs:
        for study, number in tuning_cleanup.mark_stale_trials(db):
            print(f"{db.name}: study {study} trial {number} RUNNING -> FAIL")
            run_chunks.log(f"marked trial {number} of study {study} ({db.name}) as FAIL: {tuning_cleanup.FAILED_REASON}")
        ds, kind = db.stem[len("optuna_"):].split("_", 1)
        csv_path = config.METRIC_DIR / f"{ds}_{kind}_tuning_trials.csv"
        if csv_path.exists():  # the study finished earlier: rewrite its CSV with COMPLETE trials only
            study = optuna.load_study(study_name=f"{ds}-{kind}", storage=tuning_cleanup.storage_url(db))
            print(f"{csv_path.name}: {tuning_cleanup.write_trials_csv(study, csv_path)}")


if __name__ == "__main__":
    main()
