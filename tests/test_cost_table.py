"""Cost table: superseded log rows are ignored and re-timed ARIMA fits replace invalid times (D-026)."""

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

from src import config

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_evaluation.py"


@pytest.fixture()
def run_evaluation():
    spec = importlib.util.spec_from_file_location("run_evaluation", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cost_table_skips_superseded_rows_and_applies_retime(tmp_path, monkeypatch, run_evaluation):
    note = "metrics = mean of per-series values on scored test days"
    log = pd.DataFrame({
        "run_id": ["x-arima-final", "x-arima-final", "x-ets-final"],
        "phase": ["final"] * 3,
        "dataset": ["x"] * 3,
        "model": ["arima", "arima", "ets"],
        "runtime_s": [70000.0, 70010.0, 120.0],
        "notes": [note + "; superseded: duplicate concurrent process, see D-026", note, note],
    })
    log_path = tmp_path / "EXPERIMENT_LOG.csv"
    log.to_csv(log_path, index=False)
    (tmp_path / "x_arima_retime_store_1.json").write_text(json.dumps({
        "arima_select_seconds": 100.0, "arima_refit_seconds": 10.0,
        "saved_arima_select_seconds": 65000.0, "saved_arima_refit_seconds": 20.0}))
    monkeypatch.setattr(config, "EXPERIMENT_LOG", log_path)
    monkeypatch.setattr(config, "METRIC_DIR", tmp_path)
    out = run_evaluation.cost_table("x").set_index("model")
    # 70010 - (65000 + 20) + (100 + 10) = 5100; the superseded row is not counted
    assert out.loc["arima", "total_seconds"] == pytest.approx(5100.0)
    assert out.loc["ets", "total_seconds"] == pytest.approx(120.0)
