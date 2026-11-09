"""Supervised windows for the neural models.

Each training example corresponds to one series ``s`` and one origin ``o``:

* **past block**: days ``o - L .. o - 1`` (observed values, validity flags and
  calendar covariates);
* **future block**: days ``o .. o + H - 1`` (known-in-advance covariates and
  the opening flag only, never the target);
* **static block**: one-hot identity of the series (the networks are global
  models trained on all series of a dataset);
* **target**: the ``H`` values to forecast, stacked with a 0/1 mask so that
  closures and anomalies do not contribute to the loss.

A window is admissible for training only if its whole target lies before the
training cut-off, which is what prevents look-ahead (tested in
``tests/test_leakage.py``).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class WindowData:
    """Arrays fed to a Keras model, plus bookkeeping indices."""

    past: np.ndarray
    future: np.ndarray
    static: np.ndarray
    target: np.ndarray
    series: np.ndarray
    origin: np.ndarray

    def __len__(self) -> int:
        return len(self.origin)

    def inputs(self) -> list[np.ndarray]:
        return [self.past, self.future, self.static]

    def subset(self, idx: np.ndarray) -> "WindowData":
        return WindowData(
            self.past[idx], self.future[idx], self.static[idx], self.target[idx],
            self.series[idx], self.origin[idx],
        )


def training_origins(lookback: int, horizon: int, cutoff: int) -> np.ndarray:
    """Origins whose input window starts at day >= 0 and whose target ends before ``cutoff``."""
    last = cutoff - horizon
    if last < lookback:
        raise ValueError("Training period too short for this lookback and horizon.")
    return np.arange(lookback, last + 1)


def build_windows(
    past_channels: np.ndarray,
    future_channels: np.ndarray,
    target: np.ndarray,
    target_mask: np.ndarray,
    origins_by_series: dict[int, np.ndarray],
    lookback: int,
    horizon: int,
    target_override: np.ndarray | None = None,
    mask_override: np.ndarray | None = None,
    future_extra: np.ndarray | None = None,
) -> WindowData:
    """Assemble windows for the given ``(series, origin)`` pairs.

    Args:
        past_channels: ``(S, T, Fp)`` per-day inputs available up to ``o - 1``.
        future_channels: ``(S, T, Ff)`` per-day inputs known in advance.
        target: ``(S, T)`` per-day target values (ignored if ``target_override``).
        target_mask: ``(S, T)`` per-day 0/1 loss weights.
        origins_by_series: series index -> array of origins.
        target_override: optional ``(N, H)`` per-window targets (multi-step errors).
        mask_override: optional ``(N, H)`` per-window masks.
        future_extra: optional ``(N, H, k)`` per-window future features (ARIMA path).
    """
    n_series = past_channels.shape[0]
    pairs = [(s, o) for s in sorted(origins_by_series) for o in origins_by_series[s]]
    n = len(pairs)
    fp, ff = past_channels.shape[2], future_channels.shape[2]
    extra_k = 0 if future_extra is None else future_extra.shape[2]
    past = np.empty((n, lookback, fp), dtype=np.float32)
    future = np.empty((n, horizon, ff + extra_k), dtype=np.float32)
    static = np.zeros((n, n_series), dtype=np.float32)
    tgt = np.empty((n, horizon, 2), dtype=np.float32)
    series = np.empty(n, dtype=np.int32)
    origin = np.empty(n, dtype=np.int32)
    for i, (s, o) in enumerate(pairs):
        if o - lookback < 0:
            raise ValueError("Window starts before the first day.")
        past[i] = past_channels[s, o - lookback : o]
        future[i, :, :ff] = future_channels[s, o : o + horizon]
        if future_extra is not None:
            future[i, :, ff:] = future_extra[i]
        static[i, s] = 1.0
        if target_override is None:
            seg = target[s, o : o + horizon]
            msk = target_mask[s, o : o + horizon]
        else:
            seg = target_override[i]
            msk = mask_override[i]
        tgt[i, :, 0] = np.where(msk > 0, np.nan_to_num(seg), 0.0)
        tgt[i, :, 1] = msk
        series[i] = s
        origin[i] = o
    return WindowData(past, future, static, tgt, series, origin)


def split_early_stopping(origins: np.ndarray, horizon: int, fraction: float = 0.1):
    """Chronological split of training origins into fit and early-stopping parts.

    The early-stopping block is the final ``fraction`` of origins. Fit origins
    are cut back by ``horizon`` days so that no fit target overlaps the
    early-stopping targets.
    """
    n_es = max(int(len(origins) * fraction), horizon)
    es = origins[-n_es:]
    fit = origins[origins + horizon <= es[0]]
    return fit, es
