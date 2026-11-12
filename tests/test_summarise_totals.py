"""V-1: logged totals use tuning/final rows only, skip superseded rows and apply the ARIMA re-timing."""

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

from src import config

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_compute_totals_excludes_superseded_pipeline_and_applies_retime(tmp_path, monkeypatch):
    sup = "superseded: duplicate concurrent process"
    log = pd.DataFrame({
        "run_id": ["a", "b", "c", "d", "e"],
        "phase": ["final", "final", "tuning", "pipeline", "final"],
        "dataset": ["x", "x", "x", None, "x"],
        "model": ["arima", "arima", "ffnn", None, "ets"],
        "runtime_s": [9000.0, 70010.0, 600.0, 99999.0, 120.0],
        "notes": [sup, "", "", "", ""],
    })
    path = tmp_path / "EXPERIMENT_LOG.csv"
    log.to_csv(path, index=False)
    (tmp_path / "x_arima_retime_s1.json").write_text(json.dumps({
        "arima_select_seconds": 100.0, "arima_refit_seconds": 10.0,
        "saved_arima_select_seconds": 65000.0, "saved_arima_refit_seconds": 20.0}))
    monkeypatch.setattr(config, "EXPERIMENT_LOG", path)
    monkeypatch.setattr(config, "METRIC_DIR", tmp_path)
    cost_table = _load("run_evaluation").cost_table
    out = _load("summarise_results").compute_totals(["x"], cost_table)
    seconds = 5100.0 + 600.0 + 120.0  # arima re-timed, ffnn tuning, ets final
    assert out["total_compute_runtime_hours"] == pytest.approx(round(seconds / 3600, 2))
    assert out["total_compute_energy_kwh"] > 0
