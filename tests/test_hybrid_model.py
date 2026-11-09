"""Residual alignment and hybrid combination."""

import numpy as np
import pytest

from src import hybrid_model as hm
from src import preprocessing as pp
from src import statistical_models as sm


@pytest.fixture
def fitted(panel):
    mask = pp.model_mask(panel.y, panel.closed, np.zeros_like(panel.closed))
    y = pp.with_missing(panel.y, mask)[0]
    exog = panel.covariates[0][:, panel.covariate_index(panel.arima_exog_names)].astype(float)
    res = sm._fit_sarimax(y[:300], exog[:300], (1, 0, 0), (0, 1, 1, 7))
    spec = sm.ArimaSpec((1, 0, 0), (0, 1, 1, 7), np.asarray(res.params), 0, 0, 0)
    return spec, y, exog


def test_residuals_are_aligned_with_calendar_index(fitted):
    spec, y, exog = fitted
    resid = sm.arima_one_step_residuals(spec, y, exog)
    fitted_vals = sm.arima_one_step_fitted(spec, y, exog)
    assert resid.shape == y.shape
    ok = np.isfinite(resid)
    # residual at day t equals y_t minus the one-step prediction made at t-1
    assert np.allclose(resid[ok], (y - fitted_vals)[ok])


def test_burn_in_and_missing_days_are_masked(fitted):
    spec, y, exog = fitted
    resid = sm.arima_one_step_residuals(spec, y, exog)
    burn = spec.order[1] + spec.seasonal_order[1] * spec.seasonal_order[3]
    assert np.isnan(resid[:burn]).all()
    assert np.isnan(resid[~np.isfinite(y)]).all()


def test_residuals_are_causal(fitted):
    """Residuals up to day t do not change when later data change."""
    spec, y, exog = fitted
    r1 = sm.arima_one_step_residuals(spec, y, exog)
    y2 = y.copy()
    y2[350:] = y2[350:] * 3
    r2 = sm.arima_one_step_residuals(spec, y2, exog)
    assert np.allclose(r1[:350], r2[:350], equal_nan=True)


def test_hybrid_combination_adds_destandardised_correction():
    scaler = hm.ResidualScaler(std=np.array([2.0, 10.0]))
    arima = np.array([[100.0, 100.0], [50.0, 50.0]])
    corr = np.array([[1.0, -1.0], [0.5, 0.0]])
    out = hm.combine(arima, corr, np.array([0, 1]), scaler)
    assert np.allclose(out, [[102.0, 98.0], [55.0, 50.0]])


def test_multistep_targets_are_actual_minus_path():
    y = np.arange(100, dtype=float)[None, :]
    mask = np.ones_like(y, dtype=bool)
    mask[0, 12] = False
    paths = np.zeros((1, 90, 5))
    paths[0, 10] = [9, 9, 9, 9, 9]
    scaler = hm.ResidualScaler(std=np.array([1.0]))
    tgt, msk = hm.multistep_error_targets(paths, y, mask, np.array([0]), np.array([10]), scaler, 5)
    assert np.allclose(tgt[0], [1, 2, 0, 4, 5]) and np.allclose(msk[0], [1, 1, 0, 1, 1])
