"""Back up the Optuna databases and mark interrupted (RUNNING) trials as FAIL (D-029).

Run only while no pipeline process is running. Rewrites the tuning-trials CSV of every finished
study with COMPLETE trials only. Usage (from Code/):  python scripts/clean_optuna.py
"""
import shutil
import sys
from datetime import date
from pathlib import Path

import optuna

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import config, tuning_cleanup  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_chunks  # noqa: E402


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
