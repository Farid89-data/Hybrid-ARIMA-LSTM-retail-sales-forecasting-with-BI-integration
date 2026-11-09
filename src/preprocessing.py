"""Chronological splitting, missing-value handling and scaling.

Conventions used throughout the code base:

* Days are indexed ``0 .. T-1``. A forecast **origin** ``o`` uses information
  up to and including day ``o - 1`` and predicts days ``o .. o + H - 1``.
* The **test period** is the final ``n_test_origins x H`` days, split into
  non-overlapping windows. The **validation period** is the
  ``N_VALIDATION_ORIGINS x H`` days immediately before it.
* Everything that is *fitted* (scalers, ARIMA/ETS parameters, network
  weights) uses only days before the relevant cut-off. Nothing is shuffled.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import config


@dataclass(frozen=True)
class SplitPlan:
    """Chronological evaluation plan for one dataset."""

    n_days: int
    horizon: int
    val_origins: tuple[int, ...]
    test_origins: tuple[int, ...]

    @property
    def val_start(self) -> int:
        """First validation day; the tuning-stage training period ends before it."""
        return self.val_origins[0]

    @property
    def test_start(self) -> int:
        """First test day; the final training period ends before it."""
        return self.test_origins[0]

    def describe(self) -> dict:
        return {
            "n_days": self.n_days,
            "horizon": self.horizon,
            "tuning_train_days": self.val_start,
            "validation_days": self.test_start - self.val_start,
            "final_train_days": self.test_start,
            "test_days": self.n_days - self.test_start,
            "val_origins": list(self.val_origins),
            "test_origins": list(self.test_origins),
        }


def make_split_plan(
    n_days: int,
    n_test_origins: int,
    horizon: int = config.HORIZON,
    n_val_origins: int = config.N_VALIDATION_ORIGINS,
) -> SplitPlan:
    """Create non-overlapping rolling origins for validation and test.

    Raises:
        ValueError: if the series is too short for the requested design.
    """
    test_start = n_days - n_test_origins * horizon
    val_start = test_start - n_val_origins * horizon
    if val_start <= 2 * horizon:
        raise ValueError("Series too short for the requested validation/test design.")
    test_origins = tuple(test_start + k * horizon for k in range(n_test_origins))
    val_origins = tuple(val_start + k * horizon for k in range(n_val_origins))
    return SplitPlan(n_days, horizon, val_origins, test_origins)


def flag_anomalies(
    y: np.ndarray,
    closed: np.ndarray,
    fraction: float = config.ANOMALY_FRACTION,
    window: int = config.ANOMALY_WINDOW,
) -> np.ndarray:
    """Causal anomaly flags.

    A day is flagged when it is not a known closure and its sales fall below
    ``fraction`` times the median of the preceding ``window`` non-closure days.
    Only past values enter the median, so the rule can be applied online
    without look-ahead.
    """
    flags = np.zeros_like(closed, dtype=bool)
    n_series, n_days = y.shape
    for s in range(n_series):
        for t in range(window, n_days):
            if closed[s, t]:
                continue
            hist = y[s, t - window : t][~closed[s, t - window : t]]
            if hist.size < window // 2:
                continue
            if y[s, t] < fraction * np.median(hist):
                flags[s, t] = True
    return flags


def model_mask(y: np.ndarray, closed: np.ndarray, anomalies: np.ndarray) -> np.ndarray:
    """Days usable as model inputs and fitting targets (closures and anomalies excluded)."""
    return (~closed) & (~anomalies) & np.isfinite(y)


def evaluation_mask(y: np.ndarray, closed: np.ndarray) -> np.ndarray:
    """Days on which forecasts are scored: trading days with positive recorded sales.

    Closed days are excluded because closures are known in advance and every
    model would be set to zero; zero-sales days are excluded because MAPE is
    undefined there (the Rossmann competition applied the same exclusion).
    """
    return (~closed) & (y > 0)


def with_missing(y: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Copy of ``y`` with unusable days set to NaN (for state-space models)."""
    out = y.astype(np.float64).copy()
    out[~mask] = np.nan
    return out


@dataclass
class SeriesScaler:
    """Per-series standardisation fitted on a training window only."""

    mean: np.ndarray
    std: np.ndarray

    @classmethod
    def fit(cls, y: np.ndarray, mask: np.ndarray, end: int) -> "SeriesScaler":
        """Fit on days ``0 .. end-1`` where ``mask`` is true."""
        means, stds = [], []
        for s in range(y.shape[0]):
            vals = y[s, :end][mask[s, :end]]
            if vals.size < 2:
                raise ValueError(f"Series {s} has too few training observations to scale.")
            means.append(vals.mean())
            stds.append(vals.std() if vals.std() > 0 else 1.0)
        return cls(np.asarray(means), np.asarray(stds))

    def transform(self, y: np.ndarray) -> np.ndarray:
        return (y - self.mean[:, None]) / self.std[:, None]

    def inverse(self, z: np.ndarray, series_index: np.ndarray | None = None) -> np.ndarray:
        """Undo the scaling. ``series_index`` maps rows of ``z`` to series when ``z`` is not ``(S, ...)``."""
        if series_index is None:
            shape = (-1,) + (1,) * (z.ndim - 1)
            return z * self.std.reshape(shape) + self.mean.reshape(shape)
        shape = (-1,) + (1,) * (z.ndim - 1)
        return z * self.std[series_index].reshape(shape) + self.mean[series_index].reshape(shape)


def seasonal_naive_scale(
    y: np.ndarray, mask: np.ndarray, end: int, m: int = config.SEASONAL_PERIOD
) -> np.ndarray:
    """MASE denominator: in-sample mean absolute seasonal-naive error per series.

    Computed on days ``0 .. end-1`` using only pairs where both days are valid.
    """
    scales = np.empty(y.shape[0])
    for s in range(y.shape[0]):
        cur = y[s, m:end]
        lag = y[s, : end - m]
        ok = mask[s, m:end] & mask[s, : end - m]
        diffs = np.abs(cur[ok] - lag[ok])
        if diffs.size == 0:
            raise ValueError(f"Cannot compute MASE scale for series {s}.")
        scales[s] = diffs.mean()
    return scales
