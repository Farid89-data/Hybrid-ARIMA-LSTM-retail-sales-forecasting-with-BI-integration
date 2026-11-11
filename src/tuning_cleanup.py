"""Clean-up of interrupted Optuna trials (D-029).

A process that stops during a trial leaves the trial in state RUNNING; Optuna never changes it.
Such trials are marked FAIL with the user attribute ``failed_reason``. No trial is deleted, and
only COMPLETE trials are written to the tuning-trials CSV; a sidecar JSON records how many trials
failed so that the report can say so.
"""
from __future__ import annotations

from pathlib import Path

import optuna
from optuna.trial import TrialState

from src import utils

FAILED_REASON = "interrupted run (process stopped 11 Nov 2026 03:15)"


def storage_url(db_path: Path) -> str:
    return f"sqlite:///{Path(db_path).as_posix()}"


def mark_stale_trials(db_path: Path, reason: str = FAILED_REASON) -> list[tuple[str, int]]:
    """Mark every RUNNING trial in the database as FAIL with ``failed_reason``.

    Only safe when no process is writing to the database. Returns (study name, trial number) pairs.
    """
    storage = optuna.storages.RDBStorage(storage_url(db_path))
    changed = []
    for summary in optuna.study.get_all_study_summaries(storage):
        study = optuna.load_study(study_name=summary.study_name, storage=storage)
        for trial in study.get_trials(deepcopy=False, states=(TrialState.RUNNING,)):
            storage.set_trial_user_attr(trial._trial_id, "failed_reason", reason)
            storage.set_trial_state_values(trial._trial_id, TrialState.FAIL)
            changed.append((summary.study_name, trial.number))
    return changed


def complete_trial_count(study: optuna.Study) -> int:
    return sum(t.state == TrialState.COMPLETE for t in study.trials)


def write_trials_csv(study: optuna.Study, path: Path) -> dict:
    """Write only COMPLETE trials to ``path``; record counts in ``<stem>_summary.json``."""
    frame = study.trials_dataframe()
    if not frame.empty:
        frame = frame[frame["state"] == "COMPLETE"]
    frame.to_csv(path, index=False)
    failed = [t for t in study.trials if t.state == TrialState.FAIL]
    summary = {
        "study": study.study_name,
        "complete_trials": complete_trial_count(study),
        "failed_trials": len(failed),
        "failed_reasons": sorted({t.user_attrs.get("failed_reason", "unknown") for t in failed}),
    }
    utils.save_json(summary, Path(path).with_name(Path(path).stem + "_summary.json"))
    return summary
