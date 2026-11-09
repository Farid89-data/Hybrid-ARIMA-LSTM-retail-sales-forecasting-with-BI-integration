"""Feed-forward and LSTM forecasters (Keras 3 / TensorFlow).

Both networks use the same information set and the same direct
multi-output (MIMO) strategy: one forward pass returns all ``H`` forecasts.

* **FFNN**: the past block and the future block are flattened and concatenated
  with the static block, then passed through ``n_layers`` ReLU layers.
* **LSTM**: the past block is encoded by an LSTM layer; its final hidden state
  is concatenated with the flattened future block and the static block and
  passed through a ReLU layer.

The loss is a masked mean squared error on standardised targets: days marked
0 in the mask (closures, anomalies, burn-in residuals) do not contribute.
"""

from __future__ import annotations

import os

os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")  # deterministic CPU kernels (D-018)
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import time  # noqa: E402

import keras  # noqa: E402
import numpy as np  # noqa: E402
from keras import layers  # noqa: E402

from .feature_engineering import WindowData  # noqa: E402


@keras.saving.register_keras_serializable(package="hybridforecast")
def masked_mse(y_true, y_pred):
    """Mean squared error over unmasked target days.

    ``y_true`` has shape ``(batch, H, 2)``: value and 0/1 mask; ``y_pred`` has
    shape ``(batch, H)``.
    """
    value = y_true[..., 0]
    mask = y_true[..., 1]
    sq = keras.ops.square(value - y_pred) * mask
    return keras.ops.sum(sq) / keras.ops.maximum(keras.ops.sum(mask), 1.0)


def _inputs(lookback, n_past, horizon, n_future, n_static):
    past = keras.Input(shape=(lookback, n_past), name="past")
    future = keras.Input(shape=(horizon, n_future), name="future")
    static = keras.Input(shape=(n_static,), name="static")
    return past, future, static


def build_ffnn(lookback, n_past, horizon, n_future, n_static, units=64, n_layers=2,
               dropout=0.1, learning_rate=1e-3) -> keras.Model:
    """Feed-forward network with flattened inputs and ``horizon`` linear outputs."""
    past, future, static = _inputs(lookback, n_past, horizon, n_future, n_static)
    x = layers.Concatenate()([layers.Flatten()(past), layers.Flatten()(future), static])
    for i in range(n_layers):
        x = layers.Dense(units, activation="relu", name=f"dense_{i}")(x)
        if dropout > 0:
            x = layers.Dropout(dropout)(x)
    out = layers.Dense(horizon, name="forecast")(x)
    model = keras.Model([past, future, static], out, name="ffnn")
    model.compile(optimizer=keras.optimizers.Adam(learning_rate), loss=masked_mse)
    return model


def build_lstm(lookback, n_past, horizon, n_future, n_static, units=32, dropout=0.1,
               learning_rate=1e-3) -> keras.Model:
    """LSTM encoder with a dense direct multi-output head."""
    past, future, static = _inputs(lookback, n_past, horizon, n_future, n_static)
    h = layers.LSTM(units, name="lstm")(past)
    x = layers.Concatenate()([h, layers.Flatten()(future), static])
    x = layers.Dense(units, activation="relu", name="head")(x)
    if dropout > 0:
        x = layers.Dropout(dropout)(x)
    out = layers.Dense(horizon, name="forecast")(x)
    model = keras.Model([past, future, static], out, name="lstm")
    model.compile(optimizer=keras.optimizers.Adam(learning_rate), loss=masked_mse)
    return model


def build_model(kind: str, lookback, n_past, horizon, n_future, n_static, params: dict) -> keras.Model:
    """Factory used by the tuning and training scripts."""
    if kind == "ffnn":
        return build_ffnn(lookback, n_past, horizon, n_future, n_static,
                          units=params["units"], n_layers=params["n_layers"],
                          dropout=params["dropout"], learning_rate=params["learning_rate"])
    if kind == "lstm":
        return build_lstm(lookback, n_past, horizon, n_future, n_static,
                          units=params["units"], dropout=params["dropout"],
                          learning_rate=params["learning_rate"])
    raise ValueError(f"Unknown network kind: {kind}")


def fit_model(model: keras.Model, train: WindowData, early: WindowData, batch_size: int,
              max_epochs: int = 60, patience: int = 6, verbose: int = 0) -> dict:
    """Train with early stopping on a chronologically later block.

    Returns a dict with the number of epochs run, the best early-stopping loss
    and the wall-clock training time.
    """
    stop = keras.callbacks.EarlyStopping(monitor="val_loss", patience=patience,
                                         restore_best_weights=True)
    start = time.perf_counter()
    hist = model.fit(
        train.inputs(), train.target,
        validation_data=(early.inputs(), early.target),
        batch_size=batch_size, epochs=max_epochs, shuffle=True,
        callbacks=[stop], verbose=verbose,
    )
    seconds = time.perf_counter() - start
    val_losses = hist.history["val_loss"]
    return {
        "epochs": len(val_losses),
        "best_epoch": int(np.argmin(val_losses)) + 1,
        "best_val_loss": float(np.min(val_losses)),
        "train_seconds": seconds,
    }


def predict(model: keras.Model, data: WindowData, batch_size: int = 1024) -> np.ndarray:
    """Point forecasts in model (scaled) units, shape ``(N, H)``."""
    return np.asarray(model.predict(data.inputs(), batch_size=batch_size, verbose=0))
