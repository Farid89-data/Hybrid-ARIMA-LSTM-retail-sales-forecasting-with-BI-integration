"""Experiment orchestration shared by the command-line scripts.

Stages
------
1. :func:`prepare` loads a dataset, flags anomalies, builds masks and the
   chronological split plan, and computes MASE scales.
2. :func:`run_statistical` fits the seasonal naive, ARIMA and ETS benchmarks
   (validation and test forecasts) and stores ARIMA residuals and multi-step
   paths needed by the hybrids.
3. :class:`NeuralTask` builds windows and trains/evaluates one network kind at
   one stage (``"tune"`` = fit before the validation period and forecast the
   validation origins; ``"final"`` = fit before the test period and forecast
   the test origins).

Every forecast is stored in one long table format (one row per series, origin
and horizon) so that the evaluation code treats all models identically.
"""

from __future__ import annotations

import logging
import pickle
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config, data_loader
from . import feature_engineering as fe
from . import hybrid_model as hm
from . import preprocessing as pp
from . import statistical_models as sm
from . import utils

LOGGER = logging.getLogger(__name__)
NEURAL_KINDS = ("ffnn", "lstm", "hyb_d", "hyb_ms", "hyb_z")
MODEL_LABELS = {
    "snaive": "Seasonal naive",
    "arima": "ARIMA",
    "ets": "ETS",
    "ffnn": "FFNN",
    "lstm": "LSTM",
    "hyb_d": "Hybrid (direct, one-step residuals)",
    "hyb_ms": "Hybrid (direct, multi-step errors)",
    "hyb_z": "Hybrid (recursive, one-step residuals)",
}


@dataclass
class Prepared:
    """A dataset ready for modelling."""

    panel: data_loader.Panel
    plan: pp.SplitPlan
    anomalies: np.ndarray
    model_mask: np.ndarray
    eval_mask: np.ndarray
    y_fit: np.ndarray
    exog: np.ndarray
    open_flag: np.ndarray
    scale_tune: np.ndarray
    scale_final: np.ndarray

    @property
    def name(self) -> str:
        return self.panel.name


def prepare(name: str, use_cache: bool = True) -> Prepared:
    """Load and prepare a dataset (cached as a pickle in ``outputs/interim``)."""
    config.ensure_output_dirs()
    cache = config.INTERIM_DIR / f"{name}_prepared.pkl"
    if use_cache and cache.exists():
        with cache.open("rb") as handle:
            return pickle.load(handle)
    panel = data_loader.load_panel(name)
    cfg = config.DATASETS[name]
    plan = pp.make_split_plan(panel.n_days, cfg.n_test_origins)
    anomalies = pp.flag_anomalies(panel.y, panel.closed)
    mmask = pp.model_mask(panel.y, panel.closed, anomalies)
    emask = pp.evaluation_mask(panel.y, panel.closed)
    y_fit = pp.with_missing(panel.y, mmask)
    exog = panel.covariates[:, :, panel.covariate_index(panel.arima_exog_names)].astype(np.float64)
    prepared = Prepared(
        panel=panel,
        plan=plan,
        anomalies=anomalies,
        model_mask=mmask,
        eval_mask=emask,
        y_fit=y_fit,
        exog=exog,
        open_flag=(~panel.closed).astype(np.float32),
        scale_tune=pp.seasonal_naive_scale(panel.y, mmask, plan.val_start),
        scale_final=pp.seasonal_naive_scale(panel.y, mmask, plan.test_start),
    )
    with cache.open("wb") as handle:
        pickle.dump(prepared, handle)
    return prepared


def long_table(prep: Prepared, model: str, stage: str, seed, series_idx, origins, forecast,
               lower=None, upper=None) -> pd.DataFrame:
    """Convert window forecasts into the common long format."""
    panel, H = prep.panel, prep.plan.horizon
    series_idx = np.asarray(series_idx)
    origins = np.asarray(origins)
    n = len(origins)
    s_rep = np.repeat(series_idx, H)
    o_rep = np.repeat(origins, H)
    h_rep = np.tile(np.arange(1, H + 1), n)
    day = o_rep + h_rep - 1
    scale = (prep.scale_tune if stage == "validation" else prep.scale_final)[s_rep]
    fc = np.maximum(np.asarray(forecast, dtype=float).reshape(-1), 0.0)
    frame = pd.DataFrame(
        {
            "dataset": prep.name,
            "model": model,
            "stage": stage,
            "seed": seed,
            "series_id": np.asarray(panel.series_ids)[s_rep],
            "origin_index": o_rep,
            "origin_date": panel.dates[o_rep].strftime("%Y-%m-%d"),
            "horizon": h_rep,
            "day_index": day,
            "date": panel.dates[day].strftime("%Y-%m-%d"),
            "actual": panel.y[s_rep, day],
            "forecast": fc,
            "lower": np.nan if lower is None else np.maximum(np.asarray(lower, float).reshape(-1), 0.0),
            "upper": np.nan if upper is None else np.asarray(upper, float).reshape(-1),
            "eval": prep.eval_mask[s_rep, day],
            "scale": scale,
        }
    )
    return frame


# --------------------------------------------------------------------------- statistical stage


@dataclass
class StatArtifacts:
    """Outputs of the statistical stage needed later by the hybrids."""

    resid_tune: np.ndarray
    resid_final: np.ndarray
    paths_tune: np.ndarray
    paths_final: np.ndarray
    specs: list


def run_statistical(prep: Prepared) -> tuple[pd.DataFrame, StatArtifacts]:
    """Fit seasonal naive, ARIMA and ETS for every series; return forecasts and artefacts.

    Each series is checkpointed in ``outputs/interim`` as soon as it is finished,
    so an interrupted run resumes where it stopped (timings are stored with the
    checkpoint, so resuming does not distort the cost figures).
    """
    panel, plan, H = prep.panel, prep.plan, prep.plan.horizon
    S, T = panel.n_series, panel.n_days
    frames = []
    resid_tune = np.full((S, T), np.nan)
    resid_final = np.full((S, T), np.nan)
    paths_tune = np.full((S, T - H + 1, H), np.nan)
    paths_final = np.full((S, T - H + 1, H), np.nan)
    specs = []
    for s in range(S):
        ckpt = config.INTERIM_DIR / f"{prep.name}_stat_series_{s:02d}.pkl"
        if ckpt.exists():
            with ckpt.open("rb") as handle:
                part = pickle.load(handle)
            LOGGER.info("%s %s: loaded checkpoint", prep.name, panel.series_ids[s])
        else:
            part = _statistical_series(prep, s)
            with ckpt.open("wb") as handle:
                pickle.dump(part, handle)
        frames.extend(part["frames"])
        resid_tune[s], resid_final[s] = part["resid_tune"], part["resid_final"]
        paths_tune[s], paths_final[s] = part["paths_tune"], part["paths_final"]
        specs.append(part["spec"])
    arts = StatArtifacts(resid_tune, resid_final, paths_tune, paths_final, specs)
    return pd.concat(frames, ignore_index=True), arts


def _statistical_series(prep: Prepared, s: int) -> dict:
    """All statistical models for one series (validation and test forecasts, residuals, paths)."""
    panel, plan, H = prep.panel, prep.plan, prep.plan.horizon
    T = panel.n_days
    all_origins = np.arange(0, T - H + 1)
    frames = []
    sid = panel.series_ids[s]
    y_s, ex = prep.y_fit[s], prep.exog[s]
    # Seasonal naive
    for stage, origins in (("validation", plan.val_origins), ("test", plan.test_origins)):
        fc = np.stack([sm.seasonal_naive_forecast(panel.y[s], prep.model_mask[s], o, H) for o in origins])
        frames.append(long_table(prep, "snaive", stage, 0, [s] * len(origins), origins, fc))
    # ARIMA: order selection on the tuning-stage training period
    spec_t = sm.select_arima(y_s[: plan.val_start], ex[: plan.val_start])
    val = [sm.arima_forecast(spec_t, y_s, ex, o, H) for o in plan.val_origins]
    frames.append(long_table(prep, "arima", "validation", 0, [s] * len(val), plan.val_origins,
                             np.stack([v[0] for v in val]), np.stack([v[1] for v in val]),
                             np.stack([v[2] for v in val])))
    spec_f = sm.refit_arima(spec_t, y_s[: plan.test_start], ex[: plan.test_start])
    tst = [sm.arima_forecast(spec_f, y_s, ex, o, H) for o in plan.test_origins]
    frames.append(long_table(prep, "arima", "test", 0, [s] * len(tst), plan.test_origins,
                             np.stack([v[0] for v in tst]), np.stack([v[1] for v in tst]),
                             np.stack([v[2] for v in tst])))
    resid_tune = sm.arima_one_step_residuals(spec_t, y_s, ex)
    resid_final = sm.arima_one_step_residuals(spec_f, y_s, ex)
    paths_tune = sm.arima_multistep_paths(spec_t, y_s, ex, all_origins, H)
    paths_final = sm.arima_multistep_paths(spec_f, y_s, ex, all_origins, H)
    # Consistency check: one-pass paths must equal per-origin forecasts.
    gap = max(np.max(np.abs(paths_final[o] - tst[i][0])) for i, o in enumerate(plan.test_origins))
    if gap > 1e-4 * max(1.0, np.nanmean(np.abs(y_s))):
        raise RuntimeError(f"ARIMA path mismatch for {sid}: {gap}")
    # ETS: specification chosen on the tuning-stage period, re-estimated before test
    ets_t = sm.select_ets(y_s[: plan.val_start])
    val_e = [sm.ets_forecast(ets_t, y_s, o, H) for o in plan.val_origins]
    frames.append(long_table(prep, "ets", "validation", 0, [s] * len(val_e), plan.val_origins,
                             np.stack([v[0] for v in val_e]), np.stack([v[1] for v in val_e]),
                             np.stack([v[2] for v in val_e])))
    ets_f = sm.refit_ets(ets_t, y_s[: plan.test_start])
    tst_e = [sm.ets_forecast(ets_f, y_s, o, H) for o in plan.test_origins]
    frames.append(long_table(prep, "ets", "test", 0, [s] * len(tst_e), plan.test_origins,
                             np.stack([v[0] for v in tst_e]), np.stack([v[1] for v in tst_e]),
                             np.stack([v[2] for v in tst_e])))
    spec = {
        "series_id": sid,
        "arima_order": spec_t.order,
        "arima_seasonal_order": spec_t.seasonal_order,
        "arima_models_tried": spec_t.n_models_tried,
        "arima_aicc_tune": spec_t.aicc,
        "arima_select_seconds": spec_t.fit_seconds,
        "arima_refit_seconds": spec_f.fit_seconds,
        "arima_params_final": dict(zip(_arima_param_names(spec_f, prep), spec_f.params)),
        "ets_model": ets_t.label,
        "ets_aicc_tune": ets_t.aicc,
        "ets_select_seconds": ets_t.fit_seconds,
        "ets_refit_seconds": ets_f.fit_seconds,
        "path_check_max_abs_gap": float(gap),
    }
    LOGGER.info("%s %s: ARIMA%s%s, %s (%.0fs ARIMA search)", prep.name, sid, spec_t.order,
                spec_t.seasonal_order, ets_t.label, spec_t.fit_seconds)
    return {"frames": frames, "resid_tune": resid_tune, "resid_final": resid_final,
            "paths_tune": paths_tune, "paths_final": paths_final, "spec": spec}


def _arima_param_names(spec, prep):
    model = sm._arima_model(spec, prep.y_fit[0, :50], prep.exog[0, :50])
    return list(model.param_names)


def save_stat_artifacts(prep: Prepared, arts: StatArtifacts) -> None:
    np.savez_compressed(
        config.INTERIM_DIR / f"{prep.name}_arima_artifacts.npz",
        resid_tune=arts.resid_tune, resid_final=arts.resid_final,
        paths_tune=arts.paths_tune, paths_final=arts.paths_final,
    )
    utils.save_json(arts.specs, config.METRIC_DIR / f"{prep.name}_statistical_specs.json")


def load_stat_artifacts(prep: Prepared) -> StatArtifacts:
    data = np.load(config.INTERIM_DIR / f"{prep.name}_arima_artifacts.npz")
    specs = utils.load_json(config.METRIC_DIR / f"{prep.name}_statistical_specs.json")
    return StatArtifacts(data["resid_tune"], data["resid_final"], data["paths_tune"], data["paths_final"], specs)


# --------------------------------------------------------------------------- neural stage


class NeuralTask:
    """Window construction, training and forecasting for one network kind and stage."""

    def __init__(self, prep: Prepared, arts: StatArtifacts | None, kind: str, stage: str):
        if kind not in NEURAL_KINDS:
            raise ValueError(kind)
        self.prep, self.kind, self.stage = prep, kind, stage
        plan = prep.plan
        self.cutoff = plan.val_start if stage == "tune" else plan.test_start
        self.eval_origins = np.asarray(plan.val_origins if stage == "tune" else plan.test_origins)
        self.H = plan.horizon
        self.H_model = 1 if kind == "hyb_z" else self.H
        panel = prep.panel
        self.scaler = pp.SeriesScaler.fit(panel.y, prep.model_mask, self.cutoff)
        z = self.scaler.transform(panel.y)
        v = prep.model_mask.astype(np.float32)
        z_in = np.where(prep.model_mask, z, 0.0).astype(np.float32)
        cov = panel.covariates
        self.cov = cov
        self.future = np.concatenate([cov, prep.open_flag[..., None]], axis=2).astype(np.float32)
        if kind in ("ffnn", "lstm"):
            self.past = np.concatenate([z_in[..., None], v[..., None], cov], axis=2).astype(np.float32)
            self.target, self.target_mask = z.astype(np.float32), v
            return
        if arts is None:
            raise ValueError("Hybrid kinds need the ARIMA artefacts.")
        resid = arts.resid_tune if stage == "tune" else arts.resid_final
        self.paths = arts.paths_tune if stage == "tune" else arts.paths_final
        self.res_scaler = hm.ResidualScaler.fit(resid, self.cutoff)
        r = self.res_scaler.transform(resid)
        self.r_valid = hm.residual_valid(resid, prep.model_mask)
        self.r_scaled = np.where(self.r_valid, r, np.nan)
        r_in = np.where(self.r_valid, r, 0.0).astype(np.float32)
        vr = self.r_valid.astype(np.float32)
        if kind in ("hyb_d", "hyb_z"):
            self.past = np.concatenate([r_in[..., None], vr[..., None], cov], axis=2).astype(np.float32)
            self.target, self.target_mask = np.nan_to_num(r).astype(np.float32), vr
        else:  # hyb_ms
            self.past = np.concatenate(
                [r_in[..., None], vr[..., None], z_in[..., None], v[..., None], cov], axis=2
            ).astype(np.float32)
            self.target, self.target_mask = None, None

    # ---- windows
    def _windows(self, origins_by_series: dict, lookback: int) -> fe.WindowData:
        if self.kind == "hyb_ms":
            pairs = [(s, o) for s in sorted(origins_by_series) for o in origins_by_series[s]]
            series = np.array([p[0] for p in pairs])
            origins = np.array([p[1] for p in pairs])
            tgt, msk = hm.multistep_error_targets(self.paths, self.prep.panel.y, self.prep.model_mask,
                                                  series, origins, self.res_scaler, self.H)
            extra = hm.path_feature(self.paths, series, origins, self.scaler.mean, self.scaler.std)
            return fe.build_windows(self.past, self.future, None, None, origins_by_series, lookback,
                                    self.H, target_override=tgt, mask_override=msk, future_extra=extra)
        return fe.build_windows(self.past, self.future, self.target, self.target_mask,
                                origins_by_series, lookback, self.H_model)

    def training_windows(self, lookback: int):
        origins = fe.training_origins(lookback, self.H_model, self.cutoff)
        fit_o, es_o = fe.split_early_stopping(origins, self.H_model)
        S = self.prep.panel.n_series
        fit = self._windows({s: fit_o for s in range(S)}, lookback)
        early = self._windows({s: es_o for s in range(S)}, lookback)
        return fit, early

    def eval_windows(self, lookback: int) -> fe.WindowData:
        S = self.prep.panel.n_series
        return self._windows({s: self.eval_origins for s in range(S)}, lookback)

    # ---- train + forecast
    def train_and_forecast(self, params: dict, seed: int, verbose: int = 0, max_epochs: int = 60):
        """Train one network and return ``(long_table, info, model)`` for the evaluation origins."""
        from . import neural_networks as nn  # noqa: PLC0415 - TensorFlow loaded only when needed

        utils.set_determinism(seed)
        L = params["lookback"]
        fit, early = self.training_windows(L)
        arch = "ffnn" if self.kind == "ffnn" else "lstm"
        model = nn.build_model(arch, L, fit.past.shape[2], self.H_model, fit.future.shape[2],
                               fit.static.shape[1], params)
        info = nn.fit_model(model, fit, early, batch_size=params["batch_size"], verbose=verbose,
                            max_epochs=max_epochs)
        info.update({"n_fit_windows": len(fit), "n_early_windows": len(early)})
        stage_name = "validation" if self.stage == "tune" else "test"
        S = self.prep.panel.n_series
        if self.kind == "hyb_z":
            rows_s, rows_o, preds = [], [], []
            for o in self.eval_origins:
                corr = hm.recursive_residual_forecast(
                    model, self.r_scaled, self.r_valid, self.cov, self.prep.open_flag,
                    np.arange(S), int(o), L, self.H)
                preds.append(hm.combine(self.paths[np.arange(S), o], corr, np.arange(S), self.res_scaler))
                rows_s.extend(range(S))
                rows_o.extend([int(o)] * S)
            fc = np.concatenate(preds)
            series, origins = np.array(rows_s), np.array(rows_o)
        else:
            ev = self.eval_windows(L)
            raw = nn.predict(model, ev)
            series, origins = ev.series, ev.origin
            if self.kind in ("ffnn", "lstm"):
                fc = self.scaler.inverse(raw, series)
            else:
                fc = hm.combine(self.paths[series, origins], raw, series, self.res_scaler)
        table = long_table(self.prep, self.kind, stage_name, seed, series, origins, fc)
        return table, info, model


def validation_mase(table: pd.DataFrame) -> float:
    """Objective used for tuning: mean of per-series MASE over the validation origins."""
    t = table[table["eval"]]
    per_series = (np.abs(t["actual"] - t["forecast"]) / t["scale"]).groupby(t["series_id"]).mean()
    return float(per_series.mean())
