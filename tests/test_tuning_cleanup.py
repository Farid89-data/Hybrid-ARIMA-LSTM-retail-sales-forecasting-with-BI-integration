"""Interrupted Optuna trials are marked FAIL and excluded (D-029)."""

import optuna
import pandas as pd
from optuna.trial import TrialState

from src import tuning_cleanup


def test_stale_running_trial_marked_fail(tmp_path):
    db = tmp_path / "optuna_x_ffnn.db"
    study = optuna.create_study(study_name="x-ffnn", storage=tuning_cleanup.storage_url(db))
    study.optimize(lambda t: t.suggest_float("a", 0, 1), n_trials=1)
    study.ask()  # a trial left RUNNING, as by a stopped process
    before = tuning_cleanup.complete_trial_count(study)

    changed = tuning_cleanup.mark_stale_trials(db)

    study = optuna.load_study(study_name="x-ffnn", storage=tuning_cleanup.storage_url(db))
    states = [t.state for t in study.trials]
    assert changed == [("x-ffnn", 1)]
    assert states == [TrialState.COMPLETE, TrialState.FAIL]
    assert study.trials[1].user_attrs["failed_reason"] == tuning_cleanup.FAILED_REASON
    assert "failed_reason" not in study.trials[0].user_attrs
    assert tuning_cleanup.complete_trial_count(study) == before == 1
    assert len(study.trials) == 2  # nothing deleted

    summary = tuning_cleanup.write_trials_csv(study, tmp_path / "x_ffnn_tuning_trials.csv")
    frame = pd.read_csv(tmp_path / "x_ffnn_tuning_trials.csv")
    assert list(frame["state"]) == ["COMPLETE"]
    assert summary["complete_trials"] == 1 and summary["failed_trials"] == 1
