"""Look-ahead protection: training windows, scalers and inputs must not see the future.

The strategy is perturbation: values after a cut-off are changed drastically,
and every training artefact built before the cut-off must stay identical.
"""

import numpy as np

from src import feature_engineering as fe
from src import preprocessing as pp


def _channels(panel, cutoff):
    mask = pp.model_mask(panel.y, panel.closed, np.zeros_like(panel.closed))
    scaler = pp.SeriesScaler.fit(panel.y, mask, cutoff)
    z = scaler.transform(panel.y)
    z_in = np.where(mask, z, 0.0)
    past = np.concatenate([z_in[..., None], mask[..., None].astype(float), panel.covariates], axis=2)
    future = np.concatenate([panel.covariates, (~panel.closed)[..., None].astype(float)], axis=2)
    return past.astype(np.float32), future.astype(np.float32), z.astype(np.float32), mask.astype(np.float32)


def test_training_targets_end_before_cutoff():
    origins = fe.training_origins(lookback=28, horizon=28, cutoff=300)
    assert origins.min() == 28 and origins.max() + 28 == 300


def test_early_stopping_block_is_later_and_disjoint():
    origins = fe.training_origins(lookback=28, horizon=28, cutoff=400)
    fit, es = fe.split_early_stopping(origins, horizon=28)
    assert fit.max() + 28 <= es.min()


def test_training_windows_unchanged_by_future_perturbation(panel):
    cutoff, lookback, horizon = 300, 28, 28
    origins = {s: fe.training_origins(lookback, horizon, cutoff) for s in range(panel.n_series)}
    w1 = fe.build_windows(*_channels(panel, cutoff), origins, lookback, horizon)
    panel.y[:, cutoff:] = panel.y[:, cutoff:] * 100 + 12345
    w2 = fe.build_windows(*_channels(panel, cutoff), origins, lookback, horizon)
    assert np.array_equal(w1.past, w2.past)
    assert np.array_equal(w1.target, w2.target)


def test_forecast_inputs_use_only_data_before_origin(panel):
    cutoff, lookback, horizon, origin = 300, 28, 28, 320
    past, future, target, mask = _channels(panel, cutoff)
    w1 = fe.build_windows(past, future, target, mask, {0: np.array([origin])}, lookback, horizon)
    panel.y[:, origin:] = -999.0
    past2, future2, target2, mask2 = _channels(panel, cutoff)
    w2 = fe.build_windows(past2, future2, target2, mask2, {0: np.array([origin])}, lookback, horizon)
    assert np.array_equal(w1.past, w2.past)
    assert np.array_equal(w1.future, w2.future)  # future block holds only calendar information
