"""Forecast accuracy and interval metrics.

All metrics are computed only on scored days (``eval`` flag: trading days with
positive sales; see :func:`src.preprocessing.evaluation_mask`).

* RMSE and MAE are in units of the series (items for M5, turnover for Rossmann; the source does not state the currency).
* MAPE is the mean absolute percentage error (percent).
* MASE divides the MAE by the in-sample mean absolute error of the weekly
  seasonal naive method on the training period (``scale`` column).
* Interval metrics: empirical coverage of the 95% interval, mean width and the
  interval (Winkler) score, both divided by ``scale`` so that series of
  different size can be averaged.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

ALPHA = 1 - config.PI_LEVEL


def point_metrics(frame: pd.DataFrame) -> pd.Series:
    """RMSE, MAE, MAPE and MASE for one group of forecasts."""
    f = frame[frame["eval"]]
    err = f["actual"] - f["forecast"]
    return pd.Series(
        {
            "n": int(len(f)),
            "rmse": float(np.sqrt(np.mean(np.square(err)))),
            "mae": float(np.mean(np.abs(err))),
            "mape": float(np.mean(np.abs(err) / f["actual"]) * 100),
            "mase": float(np.mean(np.abs(err) / f["scale"])),
        }
    )


def interval_metrics(frame: pd.DataFrame) -> pd.Series:
    """Coverage, scaled width and scaled Winkler score of the 95% intervals."""
    f = frame[frame["eval"] & frame["lower"].notna() & frame["upper"].notna()]
    if f.empty:
        return pd.Series({"coverage": np.nan, "width_scaled": np.nan, "winkler_scaled": np.nan})
    y, lo, hi = f["actual"], f["lower"], f["upper"]
    width = hi - lo
    penalty = (2 / ALPHA) * ((lo - y).clip(lower=0) + (y - hi).clip(lower=0))
    return pd.Series(
        {
            "coverage": float(((y >= lo) & (y <= hi)).mean()),
            "width_scaled": float((width / f["scale"]).mean()),
            "winkler_scaled": float(((width + penalty) / f["scale"]).mean()),
        }
    )


def summarise(forecasts: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Point and interval metrics per group (e.g. per model and series)."""
    pts = forecasts.groupby(by, observed=True).apply(point_metrics, include_groups=False)
    ints = forecasts.groupby(by, observed=True).apply(interval_metrics, include_groups=False)
    return pts.join(ints).reset_index()


def dataset_summary(forecasts: pd.DataFrame, group: list[str]) -> pd.DataFrame:
    """Average of per-series metrics (each series weighted equally)."""
    per_series = summarise(forecasts, group + ["series_id"])
    cols = ["rmse", "mae", "mape", "mase", "coverage", "width_scaled", "winkler_scaled"]
    agg = per_series.groupby(group)[cols].mean().reset_index()
    sd = per_series.groupby(group)["mase"].std().rename("mase_sd_across_series").reset_index()
    return agg.merge(sd, on=group)


def conformal_quantiles(calibration: pd.DataFrame, horizon: int, level: float = config.PI_LEVEL) -> np.ndarray:
    """Horizon-specific split-conformal quantiles of absolute scaled errors.

    For each horizon ``h`` the quantile of ``|actual - forecast| / scale`` over
    the validation origins is taken at level ``ceil((n + 1) * level) / n``
    (finite-sample correction). Intervals are ``forecast +/- q_h * scale``.
    """
    cal = calibration[calibration["eval"]]
    q = np.empty(horizon)
    for h in range(1, horizon + 1):
        err = (np.abs(cal.loc[cal["horizon"] == h, "actual"] - cal.loc[cal["horizon"] == h, "forecast"])
               / cal.loc[cal["horizon"] == h, "scale"]).to_numpy()
        n = len(err)
        if n == 0:
            raise ValueError(f"No calibration errors for horizon {h}.")
        rank = min(int(np.ceil((n + 1) * level)), n)
        q[h - 1] = np.sort(err)[rank - 1]
    return q


def apply_conformal(frame: pd.DataFrame, quantiles: np.ndarray) -> pd.DataFrame:
    """Return a copy with conformal ``lower``/``upper`` columns (lower bound clipped at zero)."""
    out = frame.copy()
    q = quantiles[out["horizon"].to_numpy() - 1] * out["scale"].to_numpy()
    out["lower"] = np.maximum(out["forecast"].to_numpy() - q, 0.0)
    out["upper"] = out["forecast"].to_numpy() + q
    return out
