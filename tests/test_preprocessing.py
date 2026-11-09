"""Splits, masks, anomaly flags and scaling."""

import numpy as np
import pytest

from src import preprocessing as pp


def test_split_plan_is_chronological_and_non_overlapping():
    plan = pp.make_split_plan(n_days=1941, n_test_origins=14, horizon=28, n_val_origins=5)
    assert plan.test_origins[-1] + 28 == 1941
    assert plan.test_start - plan.val_start == 5 * 28
    origins = list(plan.val_origins) + list(plan.test_origins)
    assert origins == sorted(origins)
    assert all(b - a == 28 for a, b in zip(origins, origins[1:]))


def test_split_plan_rejects_short_series():
    with pytest.raises(ValueError):
        pp.make_split_plan(n_days=300, n_test_origins=7, horizon=28, n_val_origins=5)


def test_anomaly_rule_is_causal():
    y = np.full((1, 100), 100.0)
    y[0, 60] = 1.0
    closed = np.zeros_like(y, dtype=bool)
    flags = pp.flag_anomalies(y, closed, fraction=0.1, window=28)
    assert flags[0, 60] and flags.sum() == 1
    # Changing a future value must not change any earlier flag (no look-ahead).
    y2 = y.copy()
    y2[0, 80:] = 1e6
    flags2 = pp.flag_anomalies(y2, closed, fraction=0.1, window=28)
    assert np.array_equal(flags[0, :80], flags2[0, :80])


def test_evaluation_mask_excludes_closures_and_zero_sales(panel):
    emask = pp.evaluation_mask(panel.y, panel.closed)
    assert not emask[panel.closed].any()
    assert (panel.y[emask] > 0).all()


def test_scaler_uses_training_period_only_and_inverts(panel):
    mask = pp.model_mask(panel.y, panel.closed, np.zeros_like(panel.closed))
    end = 200
    scaler = pp.SeriesScaler.fit(panel.y, mask, end)
    y_mod = panel.y.copy()
    y_mod[:, end:] *= 50  # future values must not affect the fitted scaler
    scaler2 = pp.SeriesScaler.fit(y_mod, mask, end)
    assert np.allclose(scaler.mean, scaler2.mean) and np.allclose(scaler.std, scaler2.std)
    z = scaler.transform(panel.y)
    assert np.allclose(scaler.inverse(z), panel.y)
    rows = np.array([2, 0, 1, 1])
    assert np.allclose(scaler.inverse(z[rows][:, :5], rows), panel.y[rows][:, :5])


def test_seasonal_naive_scale_matches_hand_calculation():
    y = np.array([[1.0, 2, 3, 4, 5, 6, 7, 3, 2, 3, 4, 5, 6, 9]])
    mask = np.ones_like(y, dtype=bool)
    scale = pp.seasonal_naive_scale(y, mask, end=14, m=7)
    expected = np.mean(np.abs(y[0, 7:] - y[0, :7]))
    assert scale[0] == pytest.approx(expected)
