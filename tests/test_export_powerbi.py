"""Acceptance values written for the dashboard test plan (D07)."""

import pandas as pd
import pytest

from src.export_powerbi import acceptance_values


def frame():
    # Two stores, one model; store B has two rows, store A one row.
    return pd.DataFrame({
        "model": ["arima"] * 3,
        "series_key": ["M5|A", "M5|B", "M5|B"],
        "actual": [100.0, 50.0, 80.0],
        "forecast": [90.0, 60.0, 80.0],
        "lower": [95.0, 40.0, 70.0],
        "upper": [110.0, 55.0, 90.0],
        "scale": [10.0, 5.0, 5.0],
    })


def test_acceptance_values_match_hand_calculation():
    v = acceptance_values(frame())["arima"]
    assert v["total_actual_scored"] == 230.0
    assert v["total_forecast_scored"] == 230.0
    assert v["mean_abs_error"] == pytest.approx(20.0 / 3)
    # Store A: |100-90|/10 = 1.0; store B: (10/5 + 0/5)/2 = 1.0; mean of stores = 1.0
    assert v["mase_store_average"] == pytest.approx(1.0)
    # Coverage: A inside [95,110] yes; B row 1 inside [40,55] yes; B row 2 inside [70,90] yes
    assert v["coverage"] == pytest.approx(1.0)


def test_risk_day_counts():
    f = frame()
    f.loc[0, "actual"] = 120.0   # above upper -> stock-out risk day
    f.loc[1, "actual"] = 30.0    # below lower -> overstock risk day
    v = acceptance_values(f)["arima"]
    assert v["stockout_risk_days"] == 1
    assert v["overstock_risk_days"] == 1


def test_store_average_differs_from_pooled_mase():
    f = frame()
    f.loc[2, "actual"] = 100.0   # store B row 2 error 20 -> scaled 4
    v = acceptance_values(f)["arima"]
    pooled = ((f["actual"] - f["forecast"]).abs() / f["scale"]).mean()
    assert v["mase_store_average"] == pytest.approx((1.0 + (2.0 + 4.0) / 2) / 2)
    assert v["mase_store_average"] != pytest.approx(pooled)
