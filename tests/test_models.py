"""Statistical model behaviour, horizon consistency and network shapes."""

import numpy as np
import pytest

from src import preprocessing as pp
from src import statistical_models as sm


def test_seasonal_naive_repeats_last_valid_week(panel):
    valid = ~panel.closed[0]
    fc = sm.seasonal_naive_forecast(panel.y[0], valid, origin=300, horizon=14)
    for h in range(1, 15):
        target = 300 + h - 1
        base = target - 7 * int(np.ceil(h / 7))
        while base >= 0 and not valid[base]:
            base -= 7
        expected = panel.y[0, base] if base >= 0 else 0.0
        assert fc[h - 1] == expected
        if panel.closed[0, target]:
            assert fc[h - 1] == 0.0  # weekday never open: forecast is zero
    assert len(fc) == 14


def test_arima_forecast_horizon_and_interval_order(panel):
    mask = pp.model_mask(panel.y, panel.closed, np.zeros_like(panel.closed))
    y = pp.with_missing(panel.y, mask)[0]
    exog = panel.covariates[0][:, panel.covariate_index(panel.arima_exog_names)].astype(float)
    spec = sm.ArimaSpec((1, 0, 0), (0, 1, 1, 7), np.array([]), 0, 0, 0)
    res = sm._fit_sarimax(y[:300], exog[:300], spec.order, spec.seasonal_order)
    spec.params = np.asarray(res.params)
    mean, lo, hi = sm.arima_forecast(spec, y, exog, origin=300, horizon=28)
    assert mean.shape == (28,) and np.all(lo < mean) and np.all(mean < hi)


def test_one_pass_paths_equal_per_origin_forecasts(panel):
    """The cheap multi-step paths used by the hybrid equal the standard forecasts."""
    mask = pp.model_mask(panel.y, panel.closed, np.zeros_like(panel.closed))
    y = pp.with_missing(panel.y, mask)[1]
    exog = panel.covariates[1][:, panel.covariate_index(panel.arima_exog_names)].astype(float)
    res = sm._fit_sarimax(y[:300], exog[:300], (1, 0, 1), (0, 1, 1, 7))
    spec = sm.ArimaSpec((1, 0, 1), (0, 1, 1, 7), np.asarray(res.params), 0, 0, 0)
    origins = [300, 328, 356]
    paths = sm.arima_multistep_paths(spec, y, exog, origins, 28)
    for i, o in enumerate(origins):
        mean, _, _ = sm.arima_forecast(spec, y, exog, o, 28)
        assert np.allclose(paths[i], mean, rtol=1e-6, atol=1e-6)


def test_ets_handles_missing_days(panel):
    mask = pp.model_mask(panel.y, panel.closed, np.zeros_like(panel.closed))
    y = pp.with_missing(panel.y, mask)[0]
    spec = sm.select_ets(y[:300])
    mean, lo, hi = sm.ets_forecast(spec, y, 300, 28)
    assert np.isfinite(mean).all() and np.all(lo <= hi)


def test_network_output_shape_matches_horizon():
    nn = pytest.importorskip("src.neural_networks")
    model = nn.build_lstm(lookback=14, n_past=5, horizon=28, n_future=4, n_static=3, units=8)
    past = np.zeros((2, 14, 5), np.float32)
    fut = np.zeros((2, 28, 4), np.float32)
    stat = np.zeros((2, 3), np.float32)
    assert model.predict([past, fut, stat], verbose=0).shape == (2, 28)
    ff = nn.build_ffnn(lookback=14, n_past=5, horizon=28, n_future=4, n_static=3, units=8, n_layers=1)
    assert ff.predict([past, fut, stat], verbose=0).shape == (2, 28)


def test_masked_loss_ignores_masked_days():
    nn = pytest.importorskip("src.neural_networks")
    y_true = np.array([[[1.0, 1.0], [100.0, 0.0]]], dtype=np.float32)
    y_pred = np.array([[0.0, 0.0]], dtype=np.float32)
    assert float(nn.masked_mse(y_true, y_pred)) == pytest.approx(1.0)
