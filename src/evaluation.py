"""Forecast accuracy and interval metrics.

All metrics are computed only on scored days (``eval`` flag: trading days with
positive sales; see :func:`src.preprocessing.evaluation_mask`).

* RMSE and MAE are in units of the series (items for M5, turnover for Rossmann; the source does not state the currency).
* MAPE is the mean absolute percentage error (percent).
* MASE divides the MAE by the in-sample mean absolute error of the weekly
  seasonal naive method on the training period (``scale`` column).
* Interval metrics: empirical coverage of the 95% interval, mean width and the
  interval (Winkler) score, both divided by ``scale`` so that series of
  different size can be averaged.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

ALPHA = 1 - config.PI_LEVEL


def point_metrics(frame: pd.DataFrame) -> pd.Series:
    """RMSE, MAE, MAPE and MASE for one group of forecasts."""
    f = frame[frame["eval"]]
    err = f["actual"] - f["forecast"]
    return pd.Series(
        {
            "n": int(len(f)),
            "rmse": float(np.sqrt(np.mean(np.square(err)))),
            "mae": float(np.mean(np.abs(err))),
            "mape": float(np.mean(np.abs(err) / f["actual"]) * 100),
            "mase": float(np.mean(np.abs(err) / f["scale"])),
        }
    )


def interval_metrics(frame: pd.DataFrame) -> pd.Series:
    """Coverage, scaled width and scaled Winkler score of the 95% intervals."""
    f = frame[frame["eval"] & frame["lower"].notna() & frame["upper"].notna()]
    if f.empty:
        return pd.Series({"coverage": np.nan, "width_scaled": np.nan, "winkler_scaled": np.nan})
    y, lo, hi = f["actual"], f["lower"], f["upper"]
    width = hi - lo
    penalty = (2 / ALPHA) * ((lo - y).clip(lower=0) + (y - hi).clip(lower=0))
    return pd.Series(
        {
            "coverage": float(((y >= lo) & (y <= hi)).mean()),
            "width_scaled": float((width / f["scale"]).mean()),
            "winkler_scaled": float(((width + penalty) / f["scale"]).mean()),
        }
    )


def summarise(forecasts: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Point and interval metrics per group (e.g. per model and series)."""
    pts = forecasts.groupby(by, observed=True).apply(point_metrics, include_groups=False)
    ints = forecasts.groupby(by, observed=True).apply(interval_metrics, include_groups=False)
    return pts.join(ints).reset_index()


def dataset_summary(forecasts: pd.DataFrame, group: list[str]) -> pd.DataFrame:
    """Average of per-series metrics (each series weighted equally)."""
    per_series = summarise(forecasts, group + ["series_id"])
    cols = ["rmse", "mae", "mape", "mase", "coverage", "width_scaled", "winkler_scaled"]
    agg = per_series.groupby(group)[cols].mean().reset_index()
    sd = per_series.groupby(group)["mase"].std().rename("mase_sd_across_series").reset_index()
    return agg.merge(sd, on=group)


def conformal_quantiles(calibration: pd.DataFrame, horizon: int, level: float = config.PI_LEVEL) -> np.ndarray:
    """Horizon-specific split-conformal quantiles of absolute scaled errors.

    For each horizon ``h`` the quantile of ``|actual - forecast| / scale`` over
    the validation origins is taken at level ``ceil((n + 1) * level) / n``
    (finite-sample correction). Intervals are ``forecast +/- q_h * scale``.

    A horizon without any calibration error (for example a weekday on which the
    store is always closed, because origins spaced 28 days apart share a
    weekday) gets ``q = NaN``: such horizons are never scored, so they need no
    interval. :func:`apply_conformal` then gives NaN bounds there.
    """
    cal = calibration[calibration["eval"]]
    q = np.empty(horizon)
    for h in range(1, horizon + 1):
        err = (np.abs(cal.loc[cal["horizon"] == h, "actual"] - cal.loc[cal["horizon"] == h, "forecast"])
               / cal.loc[cal["horizon"] == h, "scale"]).to_numpy()
        n = len(err)
        if n == 0:
            q[h - 1] = np.nan
            continue
        rank = min(int(np.ceil((n + 1) * level)), n)
        q[h - 1] = np.sort(err)[rank - 1]
    return q


def apply_conformal(frame: pd.DataFrame, quantiles: np.ndarray) -> pd.DataFrame:
    """Return a copy with conformal ``lower``/``upper`` columns (lower bound clipped at zero)."""
    out = frame.copy()
    q = quantiles[out["horizon"].to_numpy() - 1] * out["scale"].to_numpy()
    out["lower"] = np.maximum(out["forecast"].to_numpy() - q, 0.0)
    out["upper"] = out["forecast"].to_numpy() + q
    return out


# --------------------------------------------------------------------------- pairwise tests and ablation


def _scaled_day_losses(test: pd.DataFrame, kind: str) -> dict:
    """Cross-series mean scaled loss per test day, for every (model, seed): ``{(model, seed): Series}``."""
    g = test[test["eval"]]
    err = (g["actual"] - g["forecast"]) / g["scale"]
    loss = err.abs() if kind == "absolute" else err ** 2
    per_day = loss.groupby([g["model"], g["seed"], g["day_index"]]).mean()
    return {key: s.droplevel([0, 1]) for key, s in per_day.groupby(level=[0, 1])}


def dm_matrix(test: pd.DataFrame, horizon: int, losses: tuple[str, ...] = ("squared",),
              order: list[str] | None = None) -> pd.DataFrame:
    """All-pairs Diebold-Mariano (HLN) tests between models, in long format.

    Uses the same per-seed logic as ``run_evaluation.dm_table``: the loss
    differential is the cross-series mean of the scaled loss per test day, and
    each seed is analysed separately. Models with a single run (statistical
    models, seed 0) are paired with every seed of the other models. Within one
    seed and loss, the raw p-values of all unordered model pairs form one
    family that is Holm-adjusted. Over the seeds, ``dm_stat`` is the **mean**
    statistic and ``p_holm`` / ``p_raw`` the **median** adjusted / raw p-value.

    Sign convention: ``dm_stat`` for (row, col) tests ``loss(col) - loss(row)``,
    so a positive statistic means the **row model is more accurate**. The
    result is antisymmetric in the statistic and symmetric in the p-values.
    Columns: ``row, col, loss, dm_stat, p_holm, p_raw, mean_loss_diff, n_days, n_seeds``.
    """
    from . import statistical_tests as st  # local import keeps evaluation importable on its own

    models = [m for m in (order or sorted(test["model"].unique())) if m in set(test["model"])]
    seeds_of = {m: sorted(test.loc[test["model"] == m, "seed"].unique()) for m in models}
    seeds = sorted({s for v in seeds_of.values() for s in v})
    pairs = [(a, b) for i, a in enumerate(models) for b in models[i + 1:]]
    rows = []
    for kind in losses:
        series = _scaled_day_losses(test, kind)
        acc: dict = {}
        for s in seeds:
            res = {}
            for a, b in pairs:
                la = series[(a, s if s in seeds_of[a] else seeds_of[a][0])]
                lb = series[(b, s if s in seeds_of[b] else seeds_of[b][0])]
                common = la.index.intersection(lb.index)
                try:
                    res[(a, b)] = st.diebold_mariano((lb.loc[common] - la.loc[common]).to_numpy(), horizon)
                except ValueError:
                    res[(a, b)] = None
            raw = [1.0 if res[p] is None or not np.isfinite(res[p].p_value) else res[p].p_value for p in pairs]
            adj = st.holm_adjust(raw) if raw else []
            for p, pr, pa in zip(pairs, raw, adj):
                r = res[p]
                acc.setdefault(p, []).append((np.nan if r is None else r.statistic, pr, pa,
                                              np.nan if r is None else r.mean_differential,
                                              0 if r is None else r.n))
        for (a, b), vals in acc.items():
            v = np.array(vals, dtype=float)
            stat = np.nanmean(v[:, 0]) if np.isfinite(v[:, 0]).any() else np.nan
            md = np.nanmean(v[:, 3]) if np.isfinite(v[:, 3]).any() else np.nan
            praw, padj, n = float(np.median(v[:, 1])), float(np.median(v[:, 2])), int(v[:, 4].max())
            rows.append({"row": a, "col": b, "loss": kind, "dm_stat": stat, "p_holm": padj, "p_raw": praw,
                         "mean_loss_diff": md, "n_days": n, "n_seeds": len(seeds)})
            rows.append({"row": b, "col": a, "loss": kind, "dm_stat": -stat, "p_holm": padj, "p_raw": praw,
                         "mean_loss_diff": -md, "n_days": n, "n_seeds": len(seeds)})
    return pd.DataFrame(rows, columns=["row", "col", "loss", "dm_stat", "p_holm", "p_raw", "mean_loss_diff",
                                       "n_days", "n_seeds"])


def dm_matrix_wide(long: pd.DataFrame, loss: str, value: str, order: list[str]) -> pd.DataFrame:
    """Square model-by-model matrix of one column of :func:`dm_matrix` (diagonal NaN)."""
    g = long[long["loss"] == loss]
    models = [m for m in order if m in set(g["row"]) | set(g["col"])]
    return g.pivot(index="row", columns="col", values=value).reindex(index=models, columns=models)


def hybrid_ablation(summary: pd.DataFrame, dm_long: pd.DataFrame,
                    hybrids: tuple[str, ...] = ("hyb_d", "hyb_z", "hyb_ms"), loss: str = "squared") -> pd.DataFrame:
    """Each hybrid against its two components (ARIMA and LSTM).

    ``summary`` has one row per model with a ``mase`` column (``*_test_summary.csv``); ``dm_long`` is the
    output of :func:`dm_matrix`. ``pct_change_vs_*`` is the relative MASE change of the hybrid (negative =
    better). DM statistics are positive when the hybrid is more accurate than the component.
    """
    mase = summary.set_index("model")["mase"]
    dm = dm_long[dm_long["loss"] == loss].set_index(["row", "col"])
    rows = []
    for h in hybrids:
        if h not in mase.index or "arima" not in mase.index or "lstm" not in mase.index:
            continue
        r = {"hybrid": h, "mase_hybrid": mase[h], "mase_arima": mase["arima"], "mase_lstm": mase["lstm"],
             "pct_change_vs_arima": 100 * (mase[h] / mase["arima"] - 1),
             "pct_change_vs_lstm": 100 * (mase[h] / mase["lstm"] - 1)}
        for comp in ("arima", "lstm"):
            ok = (h, comp) in dm.index
            r[f"dm_stat_vs_{comp}"] = dm.loc[(h, comp), "dm_stat"] if ok else np.nan
            r[f"p_holm_vs_{comp}"] = dm.loc[(h, comp), "p_holm"] if ok else np.nan
        rows.append(r)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- residual diagnostics


def residual_diagnostics(resid: np.ndarray, series_ids: list[str], valid: np.ndarray | None = None,
                         end: int | None = None) -> pd.DataFrame:
    """Ljung-Box (lags 7 and 14) and BDS (embedding dimension 2) p-values of one-step ARIMA residuals.

    ``resid`` has shape (series, days); ``valid`` optionally masks days that carry no information
    (closed days); only days before ``end`` and finite values are used. Columns: ``store, lb7_p,
    lb14_p, bds_p, n`` (NaN where a test cannot be computed).
    """
    from statsmodels.stats.diagnostic import acorr_ljungbox
    from statsmodels.tsa.stattools import bds

    rows = []
    for i, sid in enumerate(series_ids):
        r = np.asarray(resid[i], dtype=float)[:end]
        keep = np.isfinite(r)
        if valid is not None:
            keep &= np.asarray(valid[i])[:end].astype(bool)
        x = r[keep]
        out = {"store": sid, "lb7_p": np.nan, "lb14_p": np.nan, "bds_p": np.nan, "n": int(len(x))}
        if len(x) > 30 and np.std(x) > 0:
            lb = acorr_ljungbox(x, lags=[7, 14], return_df=True)["lb_pvalue"]
            out["lb7_p"], out["lb14_p"] = float(lb.iloc[0]), float(lb.iloc[1])
            out["bds_p"] = float(np.atleast_1d(bds(x, max_dim=2)[1])[0])
        rows.append(out)
    return pd.DataFrame(rows)
