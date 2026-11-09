"""Shared utilities: logging, determinism, timing, energy estimates and the experiment log."""

from __future__ import annotations

import csv
import json
import logging
import os
import random
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import config

EXPERIMENT_FIELDS = [
    "run_id", "timestamp_utc", "phase", "dataset", "series_set", "model", "parameters_json",
    "seed", "split_scheme", "origin_id", "horizon_days", "runtime_s", "energy_est_kwh",
    "rmse", "mape", "mase", "pi95_coverage", "output_path", "script", "git_commit", "notes",
]


def setup_logging(level: int = logging.INFO) -> None:
    """Configure a concise console log format once per process."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def set_determinism(seed: int) -> None:
    """Seed Python, NumPy and TensorFlow and request deterministic TF kernels.

    TensorFlow is imported lazily so that statistical-only scripts do not pay
    its start-up cost. ``TF_ENABLE_ONEDNN_OPTS=0`` must be set before the first
    TensorFlow import (it is set in :mod:`src.neural_networks`).
    """
    # PYTHONHASHSEED only takes effect at interpreter start; it is set by scripts/run_queue.sh
    # and the CI workflow. Setting it here propagates it to any child process.
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    import tensorflow as tf  # noqa: PLC0415 - deliberate lazy import

    tf.keras.utils.set_random_seed(seed)
    try:
        tf.config.experimental.enable_op_determinism()
    except Exception:  # noqa: BLE001 - older TF builds lack the switch
        pass


@contextmanager
def timer():
    """Context manager yielding a dict whose ``seconds`` key is filled on exit."""
    record = {"seconds": None}
    start = time.perf_counter()
    try:
        yield record
    finally:
        record["seconds"] = time.perf_counter() - start


def energy_kwh(seconds: float, watts: float = config.CPU_TDP_WATTS) -> float:
    """Upper-bound energy estimate: runtime multiplied by the CPU's rated TDP."""
    return seconds * watts / 3.6e6


def git_commit() -> str:
    """Short hash of the current commit, or ``"uncommitted"`` outside a repository."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=config.CODE_DIR,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except Exception:  # noqa: BLE001
        return "uncommitted"


def log_experiment(row: dict, path: Path = config.EXPERIMENT_LOG) -> None:
    """Append one row to ``EXPERIMENT_LOG.csv`` (header written if missing)."""
    exists = path.exists() and path.stat().st_size > 0
    clean = {k: row.get(k, "") for k in EXPERIMENT_FIELDS}
    clean.setdefault("timestamp_utc", "")
    if not clean["timestamp_utc"]:
        clean["timestamp_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if not clean["git_commit"]:
        clean["git_commit"] = git_commit()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPERIMENT_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow(clean)


def save_json(obj, path: Path) -> None:
    """Write JSON with NumPy types converted to built-ins."""

    def convert(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, tuple):
            return list(o)
        raise TypeError(f"Unserialisable type {type(o)}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=convert), encoding="utf-8")


def load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
