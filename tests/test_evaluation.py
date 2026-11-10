"""Metric and Diebold-Mariano correctness on known inputs."""

import numpy as np
import pandas as pd
import pytest

from src import evaluation as ev
from src import statistical_tests as st


def _frame(actual, forecast, scale=2.0, lower=None, upper=None, eval_flags=None):
    n = len(actual)
    return pd.DataFrame(
        {
            "actual": actual,
            "forecast": forecast,
            "scale": scale,
            "lower": lower if lower is not None else [np.nan] * n,
            "upper": upper if upper is not None else [np.nan] * n,
            "eval": eval_flags if eval_flags is not None else [True] * n,
            "horizon": list(range(1, n + 1)),
        }
    )


def test_point_metrics_known_values():
    f = _frame([10.0, 20.0, 40.0], [12.0, 18.0, 44.0], scale=2.0)
    m = ev.point_metrics(f)
    assert m["rmse"] == pytest.approx(np.sqrt((4 + 4 + 16) / 3))
    assert m["mae"] == pytest.approx(8 / 3)
    assert m["mape"] == pytest.approx((0.2 + 0.1 + 0.1) / 3 * 100)
    assert m["mase"] == pytest.approx(8 / 3 / 2)


def test_unscored_days_are_ignored():
    f = _frame([10.0, 0.0], [12.0, 500.0], eval_flags=[True, False])
    assert ev.point_metrics(f)["mae"] == pytest.approx(2.0)


def test_interval_metrics_known_values():
    f = _frame([10.0, 20.0], [10.0, 20.0], scale=1.0, lower=[9.0, 21.0], upper=[11.0, 22.0])
    m = ev.interval_metrics(f)
    assert m["coverage"] == pytest.approx(0.5)
    assert m["width_scaled"] == pytest.approx(1.5)
    # second point is 1 below the lower bound: penalty 2/0.05 * 1 = 40
    assert m["winkler_scaled"] == pytest.approx((2 + 1 + 40) / 2)


def test_conformal_quantile_uses_finite_sample_rank():
    rows = []
    for h in (1, 2):
        for err in range(1, 20):
            rows.append({"actual": 100 + err, "forecast": 100.0, "scale": 1.0, "eval": True, "horizon": h})
    q = ev.conformal_quantiles(pd.DataFrame(rows), horizon=2, level=0.95)
    # n = 19, rank = ceil(20 * 0.95) = 19 -> largest error
    assert np.allclose(q, [19.0, 19.0])


def test_dm_identical_forecasts_not_significant():
    e = np.random.default_rng(0).normal(size=200)
    res = st.dm_test(e, e.copy(), horizon=5)
    assert res.p_value == pytest.approx(1.0) and res.statistic == 0.0


def test_dm_detects_clearly_better_model():
    rng = np.random.default_rng(1)
    e_good = rng.normal(0, 1, 400)
    e_bad = rng.normal(0, 3, 400)
    res = st.dm_test(e_bad, e_good, horizon=1)
    assert res.statistic > 0 and res.p_value < 0.001


def test_dm_hln_matches_manual_calculation():
    d = np.array([0.5, -0.2, 0.3, 0.8, 0.1, -0.4, 0.6, 0.2, 0.0, 0.4])
    h = 2
    n = len(d)
    c = d - d.mean()
    g0 = np.dot(c, c) / n
    g1 = np.dot(c[1:], c[:-1]) / n
    dm = d.mean() / np.sqrt((g0 + 2 * g1) / n)
    hln = np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    res = st.diebold_mariano(d, horizon=h)
    assert res.statistic == pytest.approx(hln * dm)


def test_holm_adjustment_matches_hand_calculation():
    adjusted = st.holm_adjust([0.01, 0.04, 0.03, 0.5])
    assert adjusted == pytest.approx([0.04, 0.09, 0.09, 0.5])


def test_conformal_unscored_horizon_gives_nan():
    rows = []
    for h in (1, 2, 3):
        for i in range(10):
            rows.append({"horizon": h, "actual": 10.0 + i, "forecast": 10.0, "scale": 2.0, "eval": h != 2})
    q = ev.conformal_quantiles(pd.DataFrame(rows), 3)
    assert np.isnan(q[1]) and np.isfinite(q[0]) and np.isfinite(q[2])
    test = pd.DataFrame({"horizon": [1, 2, 3], "actual": [10.0, 0.0, 12.0], "forecast": [10.0, 5.0, 10.0],
                         "scale": 2.0, "eval": [True, False, True]})
    out = ev.apply_conformal(test, q)
    assert np.isnan(out.loc[1, "lower"]) and np.isnan(out.loc[1, "upper"])
    assert out.loc[[0, 2], ["lower", "upper"]].notna().all().all()
    m = ev.interval_metrics(out)  # NaN rows are ignored (also if they were flagged as scored)
    assert m["coverage"] == pytest.approx(1.0) and np.isfinite(m["width_scaled"])
    out["eval"] = True
    assert ev.interval_metrics(out)["coverage"] == pytest.approx(1.0)
