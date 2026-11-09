"""Hybrid ARIMA-LSTM: residual preparation, network inputs and forecast combination.

General principle (Zhang-type decomposition)::

    y_t = L_t + N_t,   hybrid forecast = ARIMA forecast + predicted non-linear residual

Three variants are implemented so that the choices discussed in the
dissertation can be tested empirically:

``hyb_d`` (direct, one-step residuals)
    An LSTM receives the window of past one-step ARIMA residuals (plus
    calendar covariates) and outputs the next ``H`` one-step residuals at once.
``hyb_z`` (recursive, one-step residuals)
    The classical formulation: an LSTM predicts the next one-step residual and
    is iterated ``H`` times, feeding its own predictions back as inputs.
``hyb_ms`` (direct, multi-step error correction)
    The targets are the actual ``h``-step-ahead ARIMA forecast errors
    ``y_{o+h-1} - yhat_{o+h-1|o-1}`` rather than one-step residuals. The network
    also sees recent sales and the ARIMA forecast path.

Residuals are always produced by the causal Kalman filter with parameters
estimated on the training period only, and are aligned with the calendar index
(burn-in days and missing days are NaN and masked).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .feature_engineering import WindowData


@dataclass
class ResidualScaler:
    """Per-series residual standard deviation estimated on the training period."""

    std: np.ndarray

    @classmethod
    def fit(cls, resid: np.ndarray, end: int) -> "ResidualScaler":
        stds = []
        for s in range(resid.shape[0]):
            vals = resid[s, :end]
            vals = vals[np.isfinite(vals)]
            if vals.size < 10:
                raise ValueError(f"Too few residuals to scale series {s}.")
            stds.append(vals.std() if vals.std() > 0 else 1.0)
        return cls(np.asarray(stds))

    def transform(self, resid: np.ndarray) -> np.ndarray:
        return resid / self.std[:, None]


def residual_valid(resid: np.ndarray, model_mask: np.ndarray) -> np.ndarray:
    """Days where the residual is defined and the observation is usable."""
    return np.isfinite(resid) & model_mask


def multistep_error_targets(
    paths: np.ndarray,
    y: np.ndarray,
    model_mask: np.ndarray,
    series: np.ndarray,
    origins: np.ndarray,
    res_scaler: ResidualScaler,
    horizon: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Scaled multi-step ARIMA errors and their masks for each window.

    Args:
        paths: ``(S, T - H + 1, H)`` ARIMA forecasts indexed by origin.
    """
    n = len(origins)
    targets = np.zeros((n, horizon), dtype=np.float32)
    masks = np.zeros((n, horizon), dtype=np.float32)
    for i, (s, o) in enumerate(zip(series, origins)):
        actual = y[s, o : o + horizon]
        ok = model_mask[s, o : o + horizon]
        err = (actual - paths[s, o]) / res_scaler.std[s]
        targets[i] = np.where(ok, err, 0.0)
        masks[i] = ok.astype(np.float32)
    return targets, masks


def path_feature(paths: np.ndarray, series: np.ndarray, origins: np.ndarray, mean: np.ndarray,
                 std: np.ndarray) -> np.ndarray:
    """ARIMA forecast path for each window, standardised with the series scaler: ``(N, H, 1)``."""
    out = np.stack([(paths[s, o] - mean[s]) / std[s] for s, o in zip(series, origins)])
    return out[..., None].astype(np.float32)


def combine(arima_path: np.ndarray, scaled_correction: np.ndarray, series: np.ndarray,
            res_scaler: ResidualScaler) -> np.ndarray:
    """Hybrid forecast = ARIMA forecast + de-standardised residual prediction."""
    return arima_path + scaled_correction * res_scaler.std[series][:, None]


def recursive_residual_forecast(
    model,
    resid_scaled: np.ndarray,
    resid_valid: np.ndarray,
    covariates: np.ndarray,
    open_flag: np.ndarray,
    series_index: np.ndarray,
    origin: int,
    lookback: int,
    horizon: int,
) -> np.ndarray:
    """Iterate a one-step residual network ``horizon`` times from ``origin``.

    Observed residuals are used up to ``origin - 1``; afterwards the network's
    own predictions are fed back with a validity flag of 1. Every series in
    ``series_index`` is processed in one batch per step.

    Returns:
        ``(len(series_index), horizon)`` scaled residual predictions.
    """
    n_series_total = resid_scaled.shape[0]
    hist = np.nan_to_num(resid_scaled[series_index, origin - lookback : origin]).astype(np.float32)
    hist_valid = resid_valid[series_index, origin - lookback : origin].astype(np.float32)
    preds = np.zeros((len(series_index), horizon), dtype=np.float32)
    static = np.zeros((len(series_index), n_series_total), dtype=np.float32)
    static[np.arange(len(series_index)), series_index] = 1.0
    for j in range(horizon):
        day0 = origin + j - lookback
        cov = covariates[series_index, day0 : origin + j]
        past = np.concatenate([hist[..., None], hist_valid[..., None], cov], axis=2)
        fut = np.concatenate(
            [covariates[series_index, origin + j : origin + j + 1],
             open_flag[series_index, origin + j : origin + j + 1, None]],
            axis=2,
        )
        step = np.asarray(model([past, fut, static], training=False))[:, 0]
        preds[:, j] = step
        # A closed day has no residual in training data (value 0, flag 0), so the
        # same encoding is fed back here to keep inputs consistent with training.
        is_open = open_flag[series_index, origin + j].astype(np.float32)
        hist = np.concatenate([hist[:, 1:], (step * is_open)[:, None]], axis=1)
        hist_valid = np.concatenate([hist_valid[:, 1:], is_open[:, None]], axis=1)
    return preds


def windows_series_origins(data: WindowData) -> tuple[np.ndarray, np.ndarray]:
    """Convenience accessor for the bookkeeping arrays of a window set."""
    return data.series, data.origin
