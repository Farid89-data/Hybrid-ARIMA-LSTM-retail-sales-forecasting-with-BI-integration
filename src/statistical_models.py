"""Statistical benchmarks: seasonal naive, (S)ARIMA(X) and ETS.

Design (DECISIONS_LOG D-016):

* **Seasonal naive** repeats the most recent valid value observed on the same
  weekday.
* **ARIMA** is a seasonal ARIMA with weekly seasonal differencing and
  regression on known-in-advance regressors (annual Fourier terms plus event,
  SNAP or promotion flags), i.e. a regression with SARIMA errors. The
  non-seasonal differencing order ``d`` is chosen with a KPSS test, and the
  ARMA orders by a stepwise AICc search in the spirit of the automatic
  procedure used by ``forecast::auto.arima``.
* **ETS** is the linear (additive-error) state-space exponential smoothing
  model with additive weekly seasonality; the trend component (none, additive,
  damped) is chosen by AICc.

All models are estimated once on the training period. At later origins the
parameters stay fixed and the Kalman filter is re-run on the data available at
that origin, so no future information reaches the forecasts. Unusable days
(closures, anomalies) are passed as missing values, which the state-space
filter handles natively.
"""

from __future__ import annotations

import logging
import math
import time
import warnings
from dataclasses import dataclass, field

import numpy as np
from statsmodels.tools.sm_exceptions import ConvergenceWarning
from statsmodels.tsa.statespace.exponential_smoothing import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.stattools import kpss

from . import config

LOGGER = logging.getLogger(__name__)
Z_95 = 1.959963984540054


def seasonal_naive_forecast(
    y: np.ndarray, valid: np.ndarray, origin: int, horizon: int, m: int = config.SEASONAL_PERIOD
) -> np.ndarray:
    """Forecast days ``origin .. origin + horizon - 1`` for one series.

    For target day ``t`` the forecast is the value on the latest valid day
    ``t - k*m`` that lies before ``origin``. A weekday with no valid history
    at all (for example Sundays in stores that never open on Sundays) is
    forecast as zero; such days are closures and are never scored.
    """
    out = np.empty(horizon)
    for h in range(1, horizon + 1):
        target = origin + h - 1
        base = target - m * math.ceil(h / m)
        while base >= 0 and not valid[base]:
            base -= m
        out[h - 1] = y[base] if base >= 0 else 0.0
    return out


# --------------------------------------------------------------------------- ARIMA


@dataclass
class ArimaSpec:
    """Selected ARIMA specification and its estimated parameters."""

    order: tuple[int, int, int]
    seasonal_order: tuple[int, int, int, int]
    params: np.ndarray
    aicc: float
    n_models_tried: int
    fit_seconds: float
    search_log: list = field(default_factory=list)


def _fit_sarimax(y, exog, order, seasonal_order, maxiter=200):
    model = SARIMAX(
        y,
        exog=exog,
        order=order,
        seasonal_order=seasonal_order,
        trend="n",
        enforce_stationarity=True,
        enforce_invertibility=True,
        concentrate_scale=True,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        warnings.simplefilter("ignore", UserWarning)
        res = model.fit(disp=False, method="lbfgs", maxiter=maxiter)
    return res


def choose_d(y: np.ndarray, m: int = config.SEASONAL_PERIOD, alpha: float = 0.05) -> int:
    """Non-seasonal differencing order from a KPSS test on the seasonally differenced series."""
    sd = y[m:] - y[:-m]
    sd = sd[np.isfinite(sd)]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _, p_value, _, _ = kpss(sd, regression="c", nlags="auto")
    return 1 if p_value < alpha else 0


def select_arima(
    y: np.ndarray,
    exog: np.ndarray | None,
    m: int = config.SEASONAL_PERIOD,
    max_pq: int = 3,
    max_PQ: int = 2,
) -> ArimaSpec:
    """Stepwise AICc search over ARMA and seasonal ARMA orders.

    Seasonal differencing ``D = 1`` is fixed because every series shows a
    strong weekly cycle (see the EDA); ``d`` comes from :func:`choose_d`.
    """
    start = time.perf_counter()
    d, D = choose_d(y, m), 1
    tried: dict = {}
    log = []

    def evaluate(p, q, P, Q):
        key = (p, q, P, Q)
        if key in tried:
            return tried[key]
        if not (0 <= p <= max_pq and 0 <= q <= max_pq and 0 <= P <= max_PQ and 0 <= Q <= max_PQ):
            return np.inf
        try:
            res = _fit_sarimax(y, exog, (p, d, q), (P, D, Q, m))
            score = float(res.aicc) if np.isfinite(res.aicc) else np.inf
            tried[key] = score
            log.append({"order": (p, d, q), "seasonal": (P, D, Q, m), "aicc": score})
        except Exception as exc:  # noqa: BLE001 - a failed candidate is skipped and logged
            tried[key] = np.inf
            log.append({"order": (p, d, q), "seasonal": (P, D, Q, m), "error": str(exc)[:120]})
        return tried[key]

    starts = [(2, 2, 1, 1), (0, 0, 0, 0), (1, 0, 1, 0), (0, 1, 0, 1)]
    best = min(starts, key=lambda k: evaluate(*k))
    improved = True
    while improved:
        improved = False
        p, q, P, Q = best
        neighbours = [
            (p + 1, q, P, Q), (p - 1, q, P, Q), (p, q + 1, P, Q), (p, q - 1, P, Q),
            (p + 1, q + 1, P, Q), (p - 1, q - 1, P, Q),
            (p, q, P + 1, Q), (p, q, P - 1, Q), (p, q, P, Q + 1), (p, q, P, Q - 1),
            (p, q, P + 1, Q + 1), (p, q, P - 1, Q - 1),
        ]
        for cand in neighbours:
            if evaluate(*cand) < evaluate(*best) - 1e-9:
                best = cand
                improved = True
    p, q, P, Q = best
    final = _fit_sarimax(y, exog, (p, d, q), (P, D, Q, m), maxiter=500)
    elapsed = time.perf_counter() - start
    return ArimaSpec(
        order=(p, d, q),
        seasonal_order=(P, D, Q, m),
        params=np.asarray(final.params),
        aicc=float(final.aicc),
        n_models_tried=len(tried),
        fit_seconds=elapsed,
        search_log=log,
    )


def _arima_model(spec: ArimaSpec, y, exog):
    return SARIMAX(
        y,
        exog=exog,
        order=spec.order,
        seasonal_order=spec.seasonal_order,
        trend="n",
        enforce_stationarity=True,
        enforce_invertibility=True,
        concentrate_scale=True,
    )


def arima_forecast(spec: ArimaSpec, y: np.ndarray, exog: np.ndarray | None, origin: int, horizon: int):
    """Point forecast and 95% interval from ``origin`` with fixed parameters.

    ``y`` must already contain NaN for unusable days. Only ``y[:origin]`` and
    exogenous values up to ``origin + horizon`` (known in advance) are used.
    """
    ex_hist = None if exog is None else exog[:origin]
    ex_fut = None if exog is None else exog[origin : origin + horizon]
    res = _arima_model(spec, y[:origin], ex_hist).filter(spec.params)
    fc = res.get_forecast(steps=horizon, exog=ex_fut)
    mean = np.asarray(fc.predicted_mean)
    se = np.sqrt(np.asarray(fc.var_pred_mean))
    return mean, mean - Z_95 * se, mean + Z_95 * se


def arima_one_step_residuals(spec: ArimaSpec, y: np.ndarray, exog: np.ndarray | None) -> np.ndarray:
    """Causal one-step-ahead prediction errors ``y_t - E[y_t | y_<t]``.

    The Kalman filter is causal, so the error at day ``t`` uses data up to
    ``t`` only, whatever the length of ``y``. Days with missing ``y`` get NaN,
    and so do the first ``burn`` days, where the diffuse initialisation of the
    differenced states makes the errors meaningless (differencing offset).
    """
    res = _arima_model(spec, y, exog).filter(spec.params)
    err = np.asarray(res.filter_results.forecasts_error[0], dtype=np.float64).copy()
    d, D, m = spec.order[1], spec.seasonal_order[1], spec.seasonal_order[3]
    burn = max(int(res.loglikelihood_burn), d + D * m)
    err[:burn] = np.nan
    err[~np.isfinite(y)] = np.nan
    return err


def arima_one_step_fitted(spec: ArimaSpec, y: np.ndarray, exog: np.ndarray | None) -> np.ndarray:
    """One-step-ahead predictions aligned with ``y`` (useful for checks)."""
    res = _arima_model(spec, y, exog).filter(spec.params)
    return np.asarray(res.filter_results.forecasts[0], dtype=np.float64)


def refit_arima(spec: ArimaSpec, y: np.ndarray, exog: np.ndarray | None) -> ArimaSpec:
    """Re-estimate the parameters of an already selected specification on new data.

    Used at the final stage: the orders chosen on the tuning-stage training
    period are kept and the parameters are re-estimated on the full training
    period (training + validation) before the test origins.
    """
    start = time.perf_counter()
    res = _fit_sarimax(y, exog, spec.order, spec.seasonal_order, maxiter=500)
    return ArimaSpec(
        order=spec.order,
        seasonal_order=spec.seasonal_order,
        params=np.asarray(res.params),
        aicc=float(res.aicc),
        n_models_tried=1,
        fit_seconds=time.perf_counter() - start,
    )


def arima_multistep_paths(
    spec: ArimaSpec, y: np.ndarray, exog: np.ndarray | None, origins, horizon: int
) -> np.ndarray:
    """Multi-step ARIMA point forecasts from many origins using one filter pass.

    For origin ``o`` the predicted state ``a_{o|o-1}`` (which depends only on
    ``y[:o]``) is propagated through the transition matrix, and the regression
    effect of the known exogenous variables is added through the observation
    intercept. The result equals :func:`arima_forecast` at every origin (this
    is checked in the unit tests) but is much cheaper when forecasts are needed
    from every day of the training period, as the multi-step error-correction
    hybrid requires.

    Returns:
        Array of shape ``(len(origins), horizon)``.
    """
    res = _arima_model(spec, y, exog).filter(spec.params)
    ssm = res.model.ssm
    pred_state = np.asarray(res.filter_results.predicted_state)
    n = len(y)

    def time_invariant(name: str) -> np.ndarray:
        mat = np.asarray(ssm[name])
        return mat[:, :, 0] if mat.ndim == 3 else mat

    def per_day(name: str, rows: int) -> np.ndarray:
        """Return a (rows, n) array for an intercept that may be time-invariant."""
        vec = np.asarray(ssm[name], dtype=float)
        if vec.ndim == 1:
            vec = vec.reshape(rows, 1)
        return np.broadcast_to(vec, (rows, n)) if vec.shape[1] == 1 else vec

    design = time_invariant("design")
    transition = time_invariant("transition")
    obs_int = per_day("obs_intercept", 1)
    state_int = per_day("state_intercept", transition.shape[0])
    out = np.empty((len(origins), horizon))
    for i, o in enumerate(origins):
        state = pred_state[:, o].copy()
        for h in range(horizon):
            out[i, h] = (design @ state)[0] + obs_int[0, o + h]
            state = transition @ state + state_int[:, min(o + h, n - 1)]
    return out


# --------------------------------------------------------------------------- ETS


@dataclass
class EtsSpec:
    """Selected linear ETS specification and its estimated parameters."""

    trend: bool
    damped: bool
    params: np.ndarray
    aicc: float
    fit_seconds: float
    label: str


def _ets_model(y, trend: bool, damped: bool, m: int = config.SEASONAL_PERIOD):
    # "concentrated" initial states are the only statsmodels initialisation that
    # copes with missing observations (closure days); see DECISIONS_LOG D-016.
    return ExponentialSmoothing(
        y,
        trend=trend,
        damped_trend=damped,
        seasonal=m,
        initialization_method="concentrated",
        concentrate_scale=True,
    )


def select_ets(y: np.ndarray, m: int = config.SEASONAL_PERIOD) -> EtsSpec:
    """Choose ETS(A,N,A), ETS(A,A,A) or ETS(A,Ad,A) by AICc."""
    start = time.perf_counter()
    best = None
    for trend, damped, label in ((False, False, "ETS(A,N,A)"), (True, False, "ETS(A,A,A)"), (True, True, "ETS(A,Ad,A)")):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res = _ets_model(y, trend, damped, m).fit(disp=False, maxiter=500)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("ETS %s failed: %s", label, exc)
            continue
        if best is None or res.aicc < best[0].aicc:
            best = (res, trend, damped, label)
    if best is None:
        raise RuntimeError("No ETS model could be estimated.")
    res, trend, damped, label = best
    return EtsSpec(trend, damped, np.asarray(res.params), float(res.aicc), time.perf_counter() - start, label)


def refit_ets(spec: EtsSpec, y: np.ndarray) -> EtsSpec:
    """Re-estimate a selected ETS specification on a longer training period."""
    start = time.perf_counter()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = _ets_model(y, spec.trend, spec.damped).fit(disp=False, maxiter=500)
    return EtsSpec(spec.trend, spec.damped, np.asarray(res.params), float(res.aicc),
                   time.perf_counter() - start, spec.label)


def ets_forecast(spec: EtsSpec, y: np.ndarray, origin: int, horizon: int):
    """Point forecast and 95% interval from ``origin`` with fixed parameters."""
    res = _ets_model(y[:origin], spec.trend, spec.damped).filter(spec.params)
    fc = res.get_forecast(steps=horizon)
    mean = np.asarray(fc.predicted_mean)
    se = np.sqrt(np.asarray(fc.var_pred_mean))
    return mean, mean - Z_95 * se, mean + Z_95 * se
