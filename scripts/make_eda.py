"""Exploratory data analysis figures and tables for both datasets (Chapter 3).

Usage (from ``Code``)::

    python scripts/make_eda.py

Outputs: ``outputs/figures/eda_*.png`` (300 dpi) and ``outputs/tables/*.csv``.
All statistics are computed from the Kaggle files via the prepared panels.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from statsmodels.tsa.stattools import acf  # noqa: E402

from src import config, experiment, utils  # noqa: E402
from src.visualisation import apply_style, save  # noqa: E402

TABLE_DIR = config.OUTPUT_DIR / "tables"


def dataset_table(preps: dict) -> pd.DataFrame:
    rows = []
    for name, p in preps.items():
        panel, plan = p.panel, p.plan
        valid = p.model_mask
        y = np.where(valid, panel.y, np.nan)
        rows.append(
            {
                "Dataset": "M5 (Walmart)" if name == "m5" else "Rossmann",
                "Series": panel.n_series,
                "Days": panel.n_days,
                "Period": f"{panel.dates[0]:%d %b %Y} to {panel.dates[-1]:%d %b %Y}",
                "Mean daily sales": f"{np.nanmean(y):,.0f}",
                "Coefficient of variation": f"{np.nanmean(np.nanstd(y, axis=1) / np.nanmean(y, axis=1)):.2f}",
                "Closure days (share)": f"{p.panel.closed.mean() * 100:.1f}%",
                "Anomalies flagged": int(p.anomalies.sum()),
                "Training days (final)": plan.test_start,
                "Validation days": plan.test_start - plan.val_start,
                "Test days": panel.n_days - plan.test_start,
                "Unit": "items sold" if name == "m5" else "turnover (currency not stated)",
            }
        )
    return pd.DataFrame(rows)


def fig_m5_overview(p):
    panel, plan = p.panel, p.plan
    fig, ax = plt.subplots(figsize=(7.5, 3.2))
    for i, sid in enumerate(panel.series_ids):
        ls = ["-", "--", ":", "-."][i % 4]
        y = pd.Series(np.where(p.model_mask[i], panel.y[i], np.nan), index=panel.dates)
        ax.plot(y.rolling(7, min_periods=4).mean(), linestyle=ls, linewidth=0.8, label=sid,
                color=str(0.15 + 0.07 * i))
    ax.axvspan(panel.dates[plan.val_start], panel.dates[plan.test_start - 1], color="0.92", label="Validation")
    ax.axvspan(panel.dates[plan.test_start], panel.dates[-1], color="0.84", label="Test")
    ax.set_ylabel("Units sold per day (7-day mean)")
    ax.set_xlabel("Date")
    ax.legend(ncol=6, fontsize=6.5, loc="upper left", frameon=False)
    return save(fig, "eda_m5_store_series")


def fig_rossmann_overview(p, n_show=4):
    panel, plan = p.panel, p.plan
    fig, axes = plt.subplots(n_show, 1, figsize=(7.5, 5.2), sharex=True)
    for k, ax in enumerate(axes):
        y = np.where(panel.closed[k], np.nan, panel.y[k])
        ax.plot(panel.dates, y, linewidth=0.5, color="0.2")
        closed_days = panel.dates[panel.closed[k] & (panel.dates.dayofweek != 6)]
        ax.plot(closed_days, np.full(len(closed_days), np.nanmin(y) * 0.9), "|", color="0.4", markersize=5)
        ax.axvspan(panel.dates[plan.test_start], panel.dates[-1], color="0.85")
        meta = p.panel.meta.iloc[k]
        ax.set_title(f"{panel.series_ids[k]} (type {meta['StoreType']}, assortment {meta['Assortment']})", fontsize=8)
        ax.set_ylabel("Daily sales")
    axes[-1].set_xlabel("Date (shaded: test period; ticks: weekday closures)")
    return save(fig, "eda_rossmann_sample_series")


def fig_weekly_profiles(preps):
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 2.8))
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for ax, (name, p) in zip(axes, preps.items()):
        panel = p.panel
        train = slice(0, p.plan.test_start)
        prof = []
        for s in range(panel.n_series):
            y = pd.Series(np.where(p.model_mask[s], panel.y[s], np.nan)[train], index=panel.dates[train])
            by = y.groupby(y.index.dayofweek).mean()
            prof.append((by / np.nanmean(y)).reindex(range(7)).to_numpy())
        prof = np.array(prof)
        ax.boxplot([prof[:, d][np.isfinite(prof[:, d])] if np.isfinite(prof[:, d]).any() else [np.nan] for d in range(7)],
                   tick_labels=days, widths=0.6)
        ax.axhline(1.0, color="0.5", linestyle=":")
        ax.set_title("M5 stores" if name == "m5" else "Rossmann stores (closed on Sundays)")
        ax.set_ylabel("Sales relative to series mean")
    return save(fig, "eda_weekly_profiles")


def fig_acf(preps):
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 2.6))
    for ax, (name, p) in zip(axes, preps.items()):
        s = 0
        y = pd.Series(np.where(p.model_mask[s], p.panel.y[s], np.nan)[: p.plan.test_start])
        vals = acf(y.interpolate(limit_direction="both"), nlags=35, missing="drop")
        ax.bar(range(len(vals)), vals, color="0.35", width=0.6)
        ax.axhline(0, color="black", linewidth=0.6)
        bound = 1.96 / np.sqrt(y.notna().sum())
        ax.axhline(bound, color="0.5", linestyle="--", linewidth=0.7)
        ax.axhline(-bound, color="0.5", linestyle="--", linewidth=0.7)
        ax.set_title(f"{'M5' if name == 'm5' else 'Rossmann'} {p.panel.series_ids[s]} (training period)")
        ax.set_xlabel("Lag (days)")
        ax.set_ylabel("Autocorrelation")
    return save(fig, "eda_acf")


def fig_split_timeline(preps):
    fig, ax = plt.subplots(figsize=(7.5, 1.9))
    for row, (name, p) in enumerate(preps.items()):
        plan, dates = p.plan, p.panel.dates
        segs = [(0, plan.val_start, "0.55", "Training (tuning stage)"),
                (plan.val_start, plan.test_start, "0.8", "Validation: 5 origins x 28 days"),
                (plan.test_start, p.panel.n_days, "0.25", "Test: 28-day origins (M5: 14, Rossmann: 7)")]
        for a, b, colour, label in segs:
            ax.barh(row, (dates[b - 1] - dates[a]).days + 1, left=dates[a], color=colour, edgecolor="white",
                    label=label if row == 0 else None, height=0.5)
        for o in list(plan.val_origins) + list(plan.test_origins):
            ax.plot([dates[o], dates[o]], [row - 0.25, row + 0.25], color="white", linewidth=0.6)
    ax.set_yticks([0, 1], ["M5", "Rossmann"])
    ax.set_xlabel("Date (white ticks: forecast origins)")
    ax.legend(ncol=3, fontsize=7, loc="upper center", bbox_to_anchor=(0.5, 1.45), frameon=False)
    ax.grid(False)
    return save(fig, "eda_split_timeline")


def eda_facts(preps: dict) -> dict:
    """Descriptive statistics quoted in the text of Chapter 3 (written to outputs/metrics/eda_facts.json)."""
    from src import data_loader  # noqa: PLC0415

    facts: dict = {}
    for name, p in preps.items():
        panel = p.panel
        y, trading = panel.y, ~panel.closed
        means = np.array([y[s][trading[s]].mean() for s in range(panel.n_series)])
        dow = panel.dates.dayofweek.to_numpy()
        profile = []
        for s in range(panel.n_series):
            m = y[s][trading[s]].mean()
            profile.append([y[s][(dow == d) & trading[s]].mean() / m if ((dow == d) & trading[s]).any() else 0.0
                            for d in range(7)])
        f = {
            "store_mean_min": float(means.min()),
            "store_mean_max": float(means.max()),
            "store_mean_ratio": float(means.max() / means.min()),
            "weekday_profile_mon_to_sun": [round(float(v), 4) for v in np.mean(profile, axis=0)],
            "zero_sales_trading_days": int((trading & (y <= 0)).sum()),
            "anomalies": [
                {"series": panel.series_ids[s], "date": str(panel.dates[t].date()), "sales": float(y[s, t]),
                 "median_previous_28": float(np.median(y[s, t - 28:t][~panel.closed[s, t - 28:t]]))}
                for s, t in np.argwhere(p.anomalies)
            ],
        }
        if name == "m5":
            snap = panel.covariates[:, :, panel.covariate_names.index("snap")]
            ok = p.model_mask
            ratios = [y[s][ok[s] & (snap[s] == 1)].mean() / y[s][ok[s] & (snap[s] == 0)].mean()
                      for s in range(panel.n_series)]
            f.update({"snap_ratio_mean": float(np.mean(ratios)), "snap_ratio_min": float(np.min(ratios)),
                      "snap_ratio_max": float(np.max(ratios))})
        else:
            promo = panel.covariates[:, :, panel.covariate_names.index("promo")]
            dec = (panel.dates.month == 12) & (panel.dates.day <= 24)
            f.update({
                "promo_ratio": float(np.nanmean(np.where(trading & (promo == 1), y, np.nan))
                                     / np.nanmean(np.where(trading & (promo == 0), y, np.nan))),
                "december_1_24_ratio": float(np.nanmean(np.where(trading[:, dec], y[:, dec], np.nan))
                                             / np.nanmean(np.where(trading, y, np.nan))),
            })
            raw = config.RAW_DATA_DIR / config.ROSSMANN_CONFIG.raw_subdir
            train = pd.read_csv(raw / "train.csv", dtype={"StateHoliday": str}, parse_dates=["Date"])
            stores = pd.read_csv(raw / "store.csv")
            # Same eligibility rule as the panel builder: pre-test records only (D-025).
            all_dates = pd.date_range(train["Date"].min(), train["Date"].max(), freq="D")
            eligible = data_loader.eligible_rossmann_stores(
                train, stores, cutoff=data_loader.rossmann_test_start(all_dates))
            sample = panel.meta
            strata = eligible.groupby(["StoreType", "Assortment"]).size()
            chosen = sample.groupby(["StoreType", "Assortment"]).size()
            f.update({
                "stores_total": int(len(stores)),
                "stores_eligible": int(len(eligible)),
                "strata": [{"store_type": a, "assortment": b, "eligible": int(n),
                            "sampled": int(chosen.get((a, b), 0))} for (a, b), n in strata.items()],
                "type_b_stores": int((stores["StoreType"] == "b").sum()),
                "type_b_open_on_some_sunday": int(
                    (train[train["DayOfWeek"] == 7].groupby("Store")["Open"].max()
                     .reindex(stores.loc[stores["StoreType"] == "b", "Store"]) > 0).sum()),
                "type_b_eligible": int((eligible["StoreType"] == "b").sum()),
                "type_b_in_sample": int((sample["StoreType"] == "b").sum()),
            })
        if name == "m5":
            raw_m5 = config.RAW_DATA_DIR / config.M5_CONFIG.raw_subdir
            f["products_total"] = int(len(pd.read_csv(raw_m5 / "sales_train_evaluation.csv", usecols=["item_id"])
                                          ["item_id"].unique()))
        mon_to_sun = f["weekday_profile_mon_to_sun"]
        f["weekend_peak_ratio"] = float(max(mon_to_sun[5], mon_to_sun[6]))
        f["monday_peak_ratio"] = float(mon_to_sun[0])
        facts[name] = f
    utils.save_json(facts, config.METRIC_DIR / "eda_facts.json")
    return facts


def main() -> None:
    utils.setup_logging()
    apply_style()
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    preps = {name: experiment.prepare(name) for name in ("m5", "rossmann")}
    table = dataset_table(preps)
    table.to_csv(TABLE_DIR / "dataset_summary.csv", index=False)
    print(table.T.to_string())
    store_table = preps["rossmann"].panel.meta.copy()
    store_table.to_csv(TABLE_DIR / "rossmann_sample_stores.csv", index=False)
    print(eda_facts(preps))
    for f in (fig_m5_overview(preps["m5"]), fig_rossmann_overview(preps["rossmann"]),
              fig_weekly_profiles(preps), fig_acf(preps), fig_split_timeline(preps)):
        print("saved", f)


if __name__ == "__main__":
    main()
