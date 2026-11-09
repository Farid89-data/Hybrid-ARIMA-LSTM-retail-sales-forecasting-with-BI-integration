"""Diebold-Mariano test of equal predictive accuracy with the Harvey-Leybourne-Newbold correction.

Notation: ``d_t = L(e1_t) - L(e2_t)``. A **positive** mean differential means
model 1 has the larger loss (model 2 is more accurate). The long-run variance
of ``d`` uses autocovariances up to lag ``h - 1`` because ``h``-step-ahead
forecast errors follow at most an MA(``h - 1``) process. If that rectangular
estimate is not positive, Bartlett (Newey-West) weights are used instead. The
small-sample correction multiplies the statistic by
``sqrt((n + 1 - 2h + h(h - 1)/n) / n)`` and compares it with Student's t with
``n - 1`` degrees of freedom.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass(frozen=True)
class DMResult:
    statistic: float
    p_value: float
    mean_differential: float
    n: int
    horizon: int
    variance_method: str


def loss(errors: np.ndarray, kind: str) -> np.ndarray:
    """Pointwise loss: ``"squared"`` or ``"absolute"``."""
    if kind == "squared":
        return np.square(errors)
    if kind == "absolute":
        return np.abs(errors)
    raise ValueError(f"Unknown loss: {kind}")


def long_run_variance(d: np.ndarray, max_lag: int) -> tuple[float, str]:
    """Long-run variance of the mean-centred differential."""
    n = len(d)
    centred = d - d.mean()
    gammas = [float(np.dot(centred[k:], centred[: n - k]) / n) for k in range(max_lag + 1)]
    rect = gammas[0] + 2.0 * sum(gammas[1:])
    if rect > 0:
        return rect, "rectangular"
    bartlett = gammas[0] + 2.0 * sum((1 - k / (max_lag + 1)) * g for k, g in enumerate(gammas[1:], 1))
    return bartlett, "bartlett"


def diebold_mariano(differential: np.ndarray, horizon: int) -> DMResult:
    """DM-HLN test on a precomputed loss differential series (NaNs dropped)."""
    d = np.asarray(differential, dtype=float)
    d = d[np.isfinite(d)]
    n = len(d)
    if n < 3:
        raise ValueError("Too few observations for the DM test.")
    max_lag = max(min(horizon - 1, n - 2), 0)
    var, method = long_run_variance(d, max_lag)
    mean_d = float(d.mean())
    if var <= 0:
        # identical forecasts: no evidence of a difference
        return DMResult(0.0, 1.0, mean_d, n, horizon, "degenerate")
    dm = mean_d / np.sqrt(var / n)
    h = horizon
    correction = np.sqrt(max((n + 1 - 2 * h + h * (h - 1) / n) / n, 1e-12))
    stat = float(correction * dm)
    p_value = float(2 * stats.t.sf(abs(stat), df=n - 1))
    return DMResult(stat, p_value, mean_d, n, horizon, method)


def dm_test(e1: np.ndarray, e2: np.ndarray, horizon: int, kind: str = "squared") -> DMResult:
    """Convenience wrapper: build the differential from two error vectors."""
    return diebold_mariano(loss(np.asarray(e1), kind) - loss(np.asarray(e2), kind), horizon)


def holm_adjust(p_values) -> list[float]:
    """Holm step-down adjusted p-values for one family of tests.

    The ``k``-th smallest p-value is multiplied by ``m - k + 1``; monotonicity
    is enforced with a running maximum and values are capped at one.
    """
    p = np.asarray(p_values, dtype=float)
    m = len(p)
    order = np.argsort(p, kind="stable")
    adjusted = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p[idx]))
        adjusted[idx] = running
    return adjusted.tolist()
