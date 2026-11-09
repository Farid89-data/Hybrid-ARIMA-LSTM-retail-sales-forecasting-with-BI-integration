"""Shared fixtures: small synthetic panels so the tests run in seconds without the Kaggle files."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_loader import Panel, calendar_features  # noqa: E402


def synthetic_panel(n_series: int = 3, n_days: int = 420, seed: int = 0, closures: bool = True) -> Panel:
    """Weekly-seasonal AR(1) series with optional Sunday closures (unit-test data only)."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-06", periods=n_days, freq="D")
    week = np.array([1.0, 0.9, 0.95, 1.0, 1.2, 1.4, 0.8])
    y = np.empty((n_series, n_days))
    for s in range(n_series):
        level = 1000 + 200 * s
        noise = np.zeros(n_days)
        for t in range(1, n_days):
            noise[t] = 0.5 * noise[t - 1] + rng.normal(0, 30)
        y[s] = level * week[dates.dayofweek] + noise
    closed = np.zeros_like(y, dtype=bool)
    if closures:
        closed[:, dates.dayofweek == 6] = True
        y[closed] = 0.0
    feats, names = calendar_features(dates)
    cov = np.repeat(feats[None], n_series, axis=0)
    return Panel(
        name="synthetic",
        series_ids=[f"s{s}" for s in range(n_series)],
        dates=dates,
        y=y,
        closed=closed,
        covariates=cov,
        covariate_names=names,
        arima_exog_names=["year_sin1", "year_cos1"],
        meta=pd.DataFrame({"series_id": [f"s{s}" for s in range(n_series)]}),
    )


@pytest.fixture
def panel() -> Panel:
    return synthetic_panel()
