"""Tests for the pausable runner (D-028): pause flags, start refusal, time-left estimate, pause hooks."""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from src import config, experiment, utils
from conftest import synthetic_panel

_SPEC = importlib.util.spec_from_file_location(
    "run_chunks", Path(__file__).resolve().parents[1] / "scripts" / "run_chunks.py")
rc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(rc)


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "STATE_DIR", tmp_path)
    monkeypatch.delenv("PIPELINE_LANE", raising=False)
    return tmp_path


# (a) pause flags
def test_pause_requested_global_and_lane(state, monkeypatch):
    assert not utils.pause_requested()
    (state / "PAUSE_B").touch()
    assert not utils.pause_requested()  # no lane set
    monkeypatch.setenv("PIPELINE_LANE", "A")
    assert not utils.pause_requested()  # flag is for another lane
    monkeypatch.setenv("PIPELINE_LANE", "B")
    assert utils.pause_requested()
    (state / "PAUSE_B").unlink()
    (state / "PAUSE").touch()
    assert utils.pause_requested()
    monkeypatch.delenv("PIPELINE_LANE")
    assert utils.pause_requested()
    assert utils.PAUSE_EXIT_CODE == 75


# (b) resume refusal
def _proc(pid, cmd, name="python.exe"):
    return SimpleNamespace(pid=pid, info={"name": name, "cmdline": cmd})


def test_start_check_refuses_when_pipeline_running(state, monkeypatch):
    monkeypatch.setattr(rc, "own_pids", lambda: {100, 101})
    fake = _proc(500, ["python.exe", "scripts/run_neural.py", "--dataset", "m5"])
    monkeypatch.setattr(rc.psutil, "process_iter", lambda attrs=None: iter([fake]))
    ok, why = rc.start_check()
    assert not ok and "500" in why
    fake_win = _proc(501, ["python.exe", "scripts\\run_statistical.py"])
    monkeypatch.setattr(rc.psutil, "process_iter", lambda attrs=None: iter([fake_win]))
    assert not rc.start_check()[0]


def test_start_check_allows_when_idle_and_excludes_own_ancestors(state, monkeypatch):
    monkeypatch.setattr(rc, "own_pids", lambda: {100, 101})
    monkeypatch.setattr(rc.psutil, "process_iter", lambda attrs=None: iter([]))
    assert rc.start_check() == (True, "")
    own = [_proc(100, ["python.exe", "scripts/run_chunks.py"]),
           _proc(101, ["python.exe", "scripts/run_chunks.py"]),
           _proc(7, ["notepad.exe", "scripts/run_neural.py"], name="notepad.exe"),
           _proc(8, ["python.exe", "-m", "pytest"])]
    monkeypatch.setattr(rc.psutil, "process_iter", lambda attrs=None: iter(own))
    assert rc.start_check()[0]


def test_start_check_refuses_live_runner_pid(state, monkeypatch):
    monkeypatch.setattr(rc, "own_pids", lambda: {100})
    monkeypatch.setattr(rc.psutil, "process_iter", lambda attrs=None: iter([]))
    (state / "runner.pid").write_text("4242")
    monkeypatch.setattr(rc.psutil, "pid_exists", lambda pid: True)
    monkeypatch.setattr(rc.psutil, "Process", lambda pid=None: SimpleNamespace(name=lambda: "python.exe"))
    ok, why = rc.start_check()
    assert not ok and "4242" in why
    monkeypatch.setattr(rc.psutil, "pid_exists", lambda pid: False)
    assert rc.start_check()[0]


# (c) time-left estimate
def _lane(needs, stages, state="waiting for dependency"):
    return {"needs": needs, "state": state, "stages": stages}


def _stage(ds, model, parts):
    return {"dataset": ds, "model": model, "parts": parts}


def test_estimate_time_left_trials_and_seed_fallback():
    meas = {("rossmann", "lstm", "trial"): 100.0, ("rossmann", "lstm", "seed"): 200.0}
    # 3 of 15 trials done at 100 s each -> 1200 s; 0 of 5 seeds measured on the other dataset (x2) -> 2000 s
    a = _lane([], [_stage("m5", "lstm", [("trial", 15, 3), ("seed", 5, 0)])])
    est = rc.estimate_time_left({"A": a}, {("m5", "lstm", "trial"): 100.0, **{k: v for k, v in meas.items() if k[2] == "seed"}}, 1000.0)
    assert est["lane_left"]["A"] == pytest.approx(12 * 100.0 + 5 * 200.0 * rc.DATASET_FACTOR[("rossmann", "m5")])
    assert est["finish_time"] == pytest.approx(1000.0 + est["total_left"])
    # no measurement at all: default constants
    b = _lane([], [_stage("m5", "hyb_d", [("trial", 15, 0)])])
    assert rc.estimate_time_left({"B": b}, {}, 0.0)["total_left"] == 15 * rc.DEFAULT_UNIT_SECONDS["trial"]


def test_estimate_dependent_lanes_finish_after_dependencies():
    meas = {("m5", "stat", "series"): 60.0, ("m5", "ffnn", "trial"): 10.0, ("m5", "ffnn", "seed"): 10.0,
            ("m5", "hyb_d", "trial"): 20.0, ("m5", "hyb_d", "seed"): 20.0}
    lanes = {
        "B": _lane([], [_stage("m5", "stat", [("series", 10, 0)])]),                      # 600 s
        "C": _lane([], [_stage("m5", "ffnn", [("trial", 15, 0), ("seed", 5, 0)])]),       # 200 s
        "D": _lane(["B", "C"], [_stage("m5", "hyb_d", [("trial", 15, 0), ("seed", 5, 0)])]),  # 400 s
        "E": _lane(["B", "C", "D"], [_stage(None, "evaluation", [("step", 1, 0)])]),
    }
    est = rc.estimate_time_left(lanes, meas, 0.0)
    f = est["lane_finish"]
    assert f["B"] == 600 and f["C"] == 200
    assert f["D"] == 600 + 400                     # starts after max(B, C)
    assert f["E"] == f["D"] + rc.STEP_DEFAULT_SECONDS["evaluation"]
    assert f["C"] < f["B"] < f["D"] < f["E"]
    assert est["total_left"] == f["E"]
    lanes["B"]["state"] = "failed"                 # a failed lane contributes nothing
    assert rc.estimate_time_left(lanes, meas, 0.0)["lane_finish"]["D"] == 200 + 400


def test_trim_drops_invalid_outlier():
    assert rc._trim([100.0, 110.0, 90.0, 65657.0]) == [100.0, 110.0, 90.0]


def test_log_experiment_quotes_notes(tmp_path):
    path = tmp_path / "log.csv"
    notes = "lane A; start x, end y; exit 75; paused at unit boundary"
    utils.log_experiment({"run_id": "pipeline-nn_m5_ffnn-1", "phase": "pipeline", "runtime_s": 1.5,
                          "notes": notes, "git_commit": "abc"}, path=path)
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1 and rows[0]["notes"] == notes and rows[0]["dataset"] == ""


# (d) pause hook in the statistical loop
def test_run_statistical_raises_when_paused(state, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "INTERIM_DIR", tmp_path / "interim")
    (tmp_path / "interim").mkdir()
    panel = synthetic_panel(n_series=2, n_days=120)
    prep = SimpleNamespace(name="synthetic", panel=panel, plan=SimpleNamespace(horizon=28))
    (state / "PAUSE").touch()
    with pytest.raises(utils.PipelinePaused):
        experiment.run_statistical(prep)
