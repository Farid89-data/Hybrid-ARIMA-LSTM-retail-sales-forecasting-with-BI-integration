"""Rossmann store eligibility must not use information from the test period (D-025)."""

import numpy as np
import pandas as pd

from src import data_loader as dl

CUTOFF = pd.Timestamp("2015-01-17")


def synthetic_train() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Three stores trading Monday to Saturday from 2014-11-01 to 2015-02-28."""
    dates = pd.date_range("2014-11-01", "2015-02-28", freq="D")
    rows = []
    for store in (1, 2, 3):
        for d in dates:
            is_open = int(d.dayofweek != 6)
            rows.append({"Store": store, "DayOfWeek": d.dayofweek + 1, "Date": d,
                         "Sales": 5000 * is_open, "Open": is_open})
    train = pd.DataFrame(rows)
    stores = pd.DataFrame({"Store": [1, 2, 3], "StoreType": ["a", "a", "c"], "Assortment": ["a", "a", "c"]})
    return train, stores


def test_eligibility_ignores_records_on_or_after_cutoff():
    train, stores = synthetic_train()
    before = set(dl.eligible_rossmann_stores(train, stores, cutoff=CUTOFF)["Store"])
    perturbed = train.copy()
    future = perturbed["Date"] >= CUTOFF
    # Disqualifying events that happen only in the test period:
    perturbed.loc[future & (perturbed["Store"] == 1) & (perturbed["DayOfWeek"] == 7), "Open"] = 1   # Sunday trading
    perturbed.loc[future & (perturbed["Store"] == 2) & (perturbed["DayOfWeek"] != 7), "Open"] = 0   # long closure
    perturbed.loc[future & (perturbed["Store"] == 3) & (perturbed["DayOfWeek"] == 1), "Sales"] = 0  # open, zero sales
    after = set(dl.eligible_rossmann_stores(perturbed, stores, cutoff=CUTOFF)["Store"])
    assert before == after == {1, 2, 3}


def test_eligibility_still_applies_rules_before_cutoff():
    train, stores = synthetic_train()
    past = train["Date"] < CUTOFF
    train.loc[past & (train["Store"] == 2) & (train["DayOfWeek"] == 7), "Open"] = 1
    eligible = set(dl.eligible_rossmann_stores(train, stores, cutoff=CUTOFF)["Store"])
    assert eligible == {1, 3}


def test_test_start_matches_split_plan():
    dates = pd.date_range("2013-01-01", "2015-07-31", freq="D")
    assert dl.rossmann_test_start(dates) == pd.Timestamp("2015-01-17")
    assert np.sum(dates >= dl.rossmann_test_start(dates)) == 7 * 28
