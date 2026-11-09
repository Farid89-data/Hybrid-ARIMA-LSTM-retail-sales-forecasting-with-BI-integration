"""Loading the raw Kaggle files into a common daily panel structure.

Two experiments are built:

* **M5** (Walmart): the ten store-level series obtained by summing the daily
  unit sales of all 3,049 items sold in each store (``sales_train_evaluation.csv``).
* **Rossmann**: daily sales of a stratified random sample of stores with a
  complete history (``train.csv`` and ``store.csv``).

Both are returned as a :class:`Panel`: aligned ``(series x day)`` arrays plus
known-in-advance covariates. Raw files are only read, never written.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config

LOGGER = logging.getLogger(__name__)

M5_EVENT_TYPES = ("Sporting", "Cultural", "National", "Religious")


@dataclass
class Panel:
    """Aligned daily panel for one dataset.

    Attributes:
        name: dataset name (``"m5"`` or ``"rossmann"``).
        series_ids: identifiers of the series (rows of every array).
        dates: common daily calendar (columns of every array).
        y: raw sales, shape ``(S, T)``; values on closure days are kept as recorded.
        closed: known closure indicator, shape ``(S, T)``; closures are known in
            advance (Rossmann ``Open == 0``; M5 Christmas Day).
        covariates: known-in-advance features, shape ``(S, T, F)``.
        covariate_names: names of the ``F`` covariates.
        arima_exog_names: subset of covariates passed to (S)ARIMAX as regressors.
        meta: one row per series with descriptive attributes.
    """

    name: str
    series_ids: list[str]
    dates: pd.DatetimeIndex
    y: np.ndarray
    closed: np.ndarray
    covariates: np.ndarray
    covariate_names: list[str]
    arima_exog_names: list[str]
    meta: pd.DataFrame

    @property
    def n_series(self) -> int:
        return len(self.series_ids)

    @property
    def n_days(self) -> int:
        return len(self.dates)

    def covariate_index(self, names: list[str]) -> list[int]:
        """Positions of the named covariates in the covariate array."""
        return [self.covariate_names.index(n) for n in names]


def calendar_features(dates: pd.DatetimeIndex) -> tuple[np.ndarray, list[str]]:
    """Deterministic calendar features shared by both datasets.

    Day of week is one-hot encoded; month and day of year are encoded with sine
    and cosine pairs so that December and January are adjacent. Two harmonics
    of the annual cycle are produced because they also serve as Fourier
    regressors for the ARIMA models.
    """
    dow = np.eye(7)[dates.dayofweek.to_numpy()]
    month_angle = 2 * np.pi * (dates.month.to_numpy() - 1) / 12
    year_angle = 2 * np.pi * (dates.dayofyear.to_numpy() - 1) / 365.25
    feats = np.column_stack(
        [
            dow,
            np.sin(month_angle),
            np.cos(month_angle),
            np.sin(year_angle),
            np.cos(year_angle),
            np.sin(2 * year_angle),
            np.cos(2 * year_angle),
        ]
    )
    names = [f"dow_{i}" for i in range(7)] + [
        "month_sin",
        "month_cos",
        "year_sin1",
        "year_cos1",
        "year_sin2",
        "year_cos2",
    ]
    return feats.astype(np.float32), names


def load_m5_store_panel(raw_dir=None) -> Panel:
    """Build the ten M5 store-level daily series with calendar covariates."""
    raw_dir = (raw_dir or config.RAW_DATA_DIR) / config.M5_CONFIG.raw_subdir
    calendar = pd.read_csv(raw_dir / "calendar.csv", parse_dates=["date"])
    header = pd.read_csv(raw_dir / "sales_train_evaluation.csv", nrows=0).columns
    day_cols = [c for c in header if c.startswith("d_")]
    sales = pd.read_csv(
        raw_dir / "sales_train_evaluation.csv",
        usecols=["store_id", "state_id"] + day_cols,
        dtype={c: "int32" for c in day_cols},
    )
    store_state = sales.groupby("store_id")["state_id"].first()
    store_sales = sales.groupby("store_id")[day_cols].sum()
    series_ids = list(store_sales.index)

    cal = calendar.set_index("d").loc[day_cols].reset_index()
    dates = pd.DatetimeIndex(cal["date"])
    y = store_sales.to_numpy(dtype=np.float64)

    christmas = (dates.month == 12) & (dates.day == 25)
    closed = np.tile(christmas, (len(series_ids), 1))

    cal_feats, cal_names = calendar_features(dates)
    event_any = cal["event_name_1"].notna().to_numpy(dtype=np.float32)
    event_types = np.column_stack(
        [
            ((cal["event_type_1"] == t) | (cal["event_type_2"] == t)).to_numpy(dtype=np.float32)
            for t in M5_EVENT_TYPES
        ]
    )
    shared = np.column_stack([cal_feats, event_any, event_types])
    shared_names = cal_names + ["event_any"] + [f"event_{t.lower()}" for t in M5_EVENT_TYPES]

    covariates = np.zeros((len(series_ids), len(dates), shared.shape[1] + 1), dtype=np.float32)
    for i, sid in enumerate(series_ids):
        snap = cal[f"snap_{store_state[sid]}"].to_numpy(dtype=np.float32)
        covariates[i] = np.column_stack([shared, snap])
    covariate_names = shared_names + ["snap"]

    meta = pd.DataFrame(
        {"series_id": series_ids, "state": [store_state[s] for s in series_ids]}
    )
    LOGGER.info("M5 panel: %d series x %d days (%s to %s)", len(series_ids), len(dates),
                dates[0].date(), dates[-1].date())
    return Panel(
        name="m5",
        series_ids=series_ids,
        dates=dates,
        y=y,
        closed=closed,
        covariates=covariates,
        covariate_names=covariate_names,
        arima_exog_names=["year_sin1", "year_cos1", "year_sin2", "year_cos2", "event_any", "snap"],
        meta=meta,
    )


def eligible_rossmann_stores(train: pd.DataFrame, stores: pd.DataFrame,
                             cutoff: pd.Timestamp | None = None) -> pd.DataFrame:
    """Stores suitable for daily modelling (D-002, revised in D-025).

    Criteria: complete daily history, never open on Sundays (so every store
    follows the same Monday-to-Saturday trading pattern), at most 35 weekday
    closures (excludes long refurbishment closures), and no day recorded as
    open with zero sales (recording anomalies).

    Only records dated before ``cutoff`` (the first test day) are used, so the
    selection of stores uses no information from the test period. Completeness
    of the test-period records is a structural requirement of the panel and is
    checked separately when the panel is built.
    """
    if cutoff is not None:
        train = train[pd.to_datetime(train["Date"]) < pd.Timestamp(cutoff)]
    counts = train.groupby("Store").size()
    complete = counts[counts == counts.max()].index
    sunday_open = train[train["DayOfWeek"] == 7].groupby("Store")["Open"].max()
    never_sunday = sunday_open[sunday_open == 0].index
    weekday_closures = (
        train[(train["Open"] == 0) & (train["DayOfWeek"] != 7)].groupby("Store").size()
        .reindex(counts.index, fill_value=0)
    )
    few_closures = weekday_closures[weekday_closures <= 35].index
    zero_open = train[(train["Open"] == 1) & (train["Sales"] == 0)]["Store"].unique()
    keep = set(complete) & set(never_sunday) & set(few_closures)
    keep -= set(zero_open)
    return stores[stores["Store"].isin(keep)].copy()


def rossmann_test_start(dates: pd.DatetimeIndex) -> pd.Timestamp:
    """First day of the Rossmann test period under the configured split plan."""
    cfg = config.ROSSMANN_CONFIG
    return dates[len(dates) - cfg.n_test_origins * config.HORIZON]


def sample_rossmann_stores(eligible: pd.DataFrame, n: int, seed: int) -> list[int]:
    """Stratified random sample over StoreType x Assortment.

    Allocation is proportional to stratum size (largest-remainder rounding)
    with a minimum of two stores per stratum, so every store format is
    represented.
    """
    rng = np.random.default_rng(seed)
    strata = eligible.groupby(["StoreType", "Assortment"])["Store"].apply(sorted)
    sizes = strata.apply(len)
    k = len(sizes)
    base = np.full(k, 2)
    remaining = n - base.sum()
    if remaining < 0:
        raise ValueError("Sample too small for two stores per stratum.")
    share = sizes.to_numpy() / sizes.sum() * remaining
    alloc = base + np.floor(share).astype(int)
    leftover = n - alloc.sum()
    order = np.argsort(-(share - np.floor(share)), kind="stable")
    alloc[order[:leftover]] += 1
    chosen: list[int] = []
    for (key, members), m in zip(strata.items(), alloc):
        picked = rng.choice(members, size=min(m, len(members)), replace=False)
        chosen.extend(int(p) for p in sorted(picked))
        LOGGER.info("Rossmann stratum %s: %d of %d stores", key, m, len(members))
    return sorted(chosen)


def load_rossmann_panel(raw_dir=None, n_stores: int | None = None, seed: int | None = None) -> Panel:
    """Build the sampled Rossmann daily panel with promotion and holiday covariates."""
    cfg = config.ROSSMANN_CONFIG
    raw_dir = (raw_dir or config.RAW_DATA_DIR) / cfg.raw_subdir
    n_stores = n_stores or cfg.sample_size
    seed = cfg.sample_seed if seed is None else seed
    train = pd.read_csv(raw_dir / "train.csv", parse_dates=["Date"], dtype={"StateHoliday": str})
    stores = pd.read_csv(raw_dir / "store.csv")
    dates = pd.date_range(train["Date"].min(), train["Date"].max(), freq="D")
    eligible = eligible_rossmann_stores(train, stores, cutoff=rossmann_test_start(dates))
    chosen = sample_rossmann_stores(eligible, n_stores, seed)

    sub = train[train["Store"].isin(chosen)].copy()
    sub["StateHolidayAny"] = (sub["StateHoliday"] != "0").astype(float)

    def pivot(column: str) -> np.ndarray:
        wide = sub.pivot(index="Store", columns="Date", values=column).reindex(index=chosen, columns=dates)
        if wide.isna().any().any():
            raise ValueError(f"Missing Rossmann records for column {column}.")
        return wide.to_numpy(dtype=np.float64)

    y = pivot("Sales")
    open_flag = pivot("Open")
    promo = pivot("Promo")
    school = pivot("SchoolHoliday")
    state_hol = pivot("StateHolidayAny")
    closed = open_flag == 0

    cal_feats, cal_names = calendar_features(dates)
    covariates = np.zeros((len(chosen), len(dates), cal_feats.shape[1] + 3), dtype=np.float32)
    for i in range(len(chosen)):
        covariates[i] = np.column_stack([cal_feats, promo[i], school[i], state_hol[i]])
    covariate_names = cal_names + ["promo", "school_holiday", "state_holiday"]

    meta = stores.set_index("Store").loc[chosen, ["StoreType", "Assortment", "CompetitionDistance", "Promo2"]]
    meta = meta.reset_index().rename(columns={"Store": "store"})
    meta.insert(0, "series_id", [f"store_{s}" for s in chosen])
    LOGGER.info("Rossmann panel: %d stores x %d days", len(chosen), len(dates))
    return Panel(
        name="rossmann",
        series_ids=[f"store_{s}" for s in chosen],
        dates=dates,
        y=y,
        closed=closed,
        covariates=covariates,
        covariate_names=covariate_names,
        arima_exog_names=["year_sin1", "year_cos1", "year_sin2", "year_cos2", "promo", "school_holiday"],
        meta=meta,
    )


def load_panel(name: str, raw_dir=None) -> Panel:
    """Dispatch to the loader of the named dataset."""
    if name == "m5":
        return load_m5_store_panel(raw_dir)
    if name == "rossmann":
        return load_rossmann_panel(raw_dir)
    raise ValueError(f"Unknown dataset: {name}")
