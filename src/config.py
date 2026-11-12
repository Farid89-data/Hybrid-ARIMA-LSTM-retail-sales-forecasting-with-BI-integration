"""Central configuration: paths, experimental constants and dataset settings.

All paths are resolved relative to this file so the repository stays portable.
The location of the raw Kaggle files can be overridden with the environment
variable ``RAW_DATA_DIR`` (useful on CI or another machine).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = CODE_DIR.parent
RAW_DATA_DIR = Path(os.environ.get("RAW_DATA_DIR", PROJECT_ROOT / "Dataset"))
OUTPUT_DIR = CODE_DIR / "outputs"
FIGURE_DIR = OUTPUT_DIR / "figures"
FORECAST_DIR = OUTPUT_DIR / "forecasts"
METRIC_DIR = OUTPUT_DIR / "metrics"
MODEL_DIR = OUTPUT_DIR / "models"
COMPARISON_DIR = OUTPUT_DIR / "model_comparisons"
INTERIM_DIR = OUTPUT_DIR / "interim"
STATE_DIR = OUTPUT_DIR / "state"  # runner state: PAUSE flags, RESUME.md, done markers (not committed)
EXPERIMENT_LOG = CODE_DIR / "EXPERIMENT_LOG.csv"

# Forecasting protocol (DECISIONS_LOG D-005, D-015).
HORIZON = 28  # days ahead forecast at every origin
SEASONAL_PERIOD = 7  # weekly seasonality of daily retail sales
N_VALIDATION_ORIGINS = 5  # rolling origins used for tuning and interval calibration
PI_LEVEL = 0.95  # nominal coverage of prediction intervals
SEEDS = (1, 2, 3, 4, 5)  # seeds for neural-network stability analysis
PRIMARY_SEED = 1

# Energy estimate: runtime x processor thermal design power (TDP).
# Intel Core i7-4510U TDP = 15 W (Intel product specification); see D-019.
CPU_TDP_WATTS = 15.0

# Anomaly rule applied causally to model inputs (D-015): a non-closure day whose
# sales fall below this fraction of the trailing 28-day median is treated as missing.
ANOMALY_FRACTION = 0.10
ANOMALY_WINDOW = 28


@dataclass(frozen=True)
class DatasetConfig:
    """Settings that differ between the two experiments."""

    name: str
    n_test_origins: int
    raw_subdir: str
    sample_size: int | None = None
    sample_seed: int = 2026
    extra: dict = field(default_factory=dict)


M5_CONFIG = DatasetConfig(
    name="m5",
    n_test_origins=14,  # 14 x 28 = 392 days = 20.2% of 1,941 days
    raw_subdir="m5-forecasting-accuracy",
)

ROSSMANN_CONFIG = DatasetConfig(
    name="rossmann",
    n_test_origins=7,  # 7 x 28 = 196 days = 20.8% of 942 days
    raw_subdir="rossmann-store-sales",
    sample_size=20,
    sample_seed=2026,
)

DATASETS = {"m5": M5_CONFIG, "rossmann": ROSSMANN_CONFIG}

KAGGLE_SOURCES = {
    "m5": "https://www.kaggle.com/competitions/m5-forecasting-accuracy/data",
    "rossmann": "https://www.kaggle.com/competitions/rossmann-store-sales/data",
}


def ensure_output_dirs() -> None:
    """Create every output directory used by the pipeline."""
    for directory in (
        OUTPUT_DIR,
        FIGURE_DIR,
        FORECAST_DIR,
        METRIC_DIR,
        MODEL_DIR,
        COMPARISON_DIR,
        INTERIM_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
