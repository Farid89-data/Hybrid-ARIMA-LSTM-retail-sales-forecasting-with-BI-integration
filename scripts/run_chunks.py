"""Pausable pipeline runner (D-028): lanes with dependencies, memory admission and safe pauses.

Lanes (each stage resumes from its own checkpoints; a stage whose artefacts are complete is skipped):
  A  Rossmann networks: ffnn, lstm, hyb_d, hyb_z, hyb_ms (ARIMA stage already done)
  B  M5 statistical benchmarks
  C  M5 networks without ARIMA input: ffnn, lstm
  D  M5 hybrids: hyb_d, hyb_z, hyb_ms (after B and C)
  E  evaluation, dashboard export, result summary, pytest, report tables, notebooks (after A to D)

Pausing happens only between units of work (Optuna trial, final seed, statistical series). The runner
creates outputs/state/PAUSE; the stage scripts see it (src.utils.pause_requested), finish the current
unit and exit with code 75. Lane E steps are atomic and are allowed to finish. Pause with the key P in
the runner window, with Pause-Pipeline.bat, or with Ctrl+C. Processes are never suspended: if memory
runs low the newest lane is asked to pause (outputs/state/PAUSE_<lane>) and restarts when memory allows.

Usage (from Code/):
  python scripts/run_chunks.py            start or resume (use Resume-Pipeline.bat)
  python scripts/run_chunks.py --status   print the latest summary without starting anything
"""
from __future__ import annotations

import argparse
import csv
import ctypes
import json
import os
import re
import signal
import statistics
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import psutil

CODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE))

from src import config, utils  # noqa: E402

PY = str(CODE / ".venv" / "Scripts" / "python.exe") if (CODE / ".venv").exists() else sys.executable
LOGS = config.OUTPUT_DIR / "logs"

# ---------------------------------------------------------------------------------- constants
MEM_LOW = 0.15                # keep available RAM >= 15% of total after admitting a lane
MEM_FOOTPRINT_GB = {"tf": 1.2, "stat": 0.6, "step": 1.5}  # estimated per-process footprint
RECENT_START_S = 120          # a lane started this recently still counts its full footprint
REQUEUE_COOLDOWN_S = 120      # wait before restarting a lane paused for memory
TICK_S = 1.0                  # loop period (keys, flags, process exits)
REFRESH_S = 30.0              # display / RESUME.md refresh period
N_TRIALS, N_SEEDS = 15, len(config.SEEDS)
N_SERIES = {"rossmann": config.ROSSMANN_CONFIG.sample_size, "m5": 10}  # M5: the 10 selected series
# Time-left fallbacks. Same unit type of the same model on the other dataset is scaled by this factor
# (M5 has 10 series x 1,941 days and 14 test origins; Rossmann 20 x 942 days and 7 test origins:
# similar training volume, twice the forecast origins). Otherwise a default per unit type (seconds).
DATASET_FACTOR = {("rossmann", "m5"): 2.0, ("m5", "rossmann"): 0.5}
DEFAULT_UNIT_SECONDS = {"trial": 300.0, "seed": 400.0, "validation": 300.0, "series": 600.0, "step": 300.0}
STEP_DEFAULT_SECONDS = {"evaluation": 900.0, "export_dashboard": 120.0, "summarise_results": 60.0,
                        "pytest": 240.0, "make_report_tables": 120.0, "make_notebooks": 300.0}
OUTLIER_FACTOR = 10.0         # a measured unit time above 10 x the median is treated as invalid (e.g. sleep)


def _nn(ds: str, model: str) -> dict:
    return {"name": f"nn_{ds}_{model}", "kind": "nn", "dataset": ds, "model": model,
            "args": ["scripts/run_neural.py", "--dataset", ds, "--model", model, "--trials", str(N_TRIALS)]}


def _step(name: str, args: list) -> dict:
    return {"name": name, "kind": "step", "dataset": None, "model": name, "args": args}


LANES = {
    "A": {"title": "Rossmann networks", "threads": 2, "needs": [],
          "stages": [_nn("rossmann", m) for m in ("ffnn", "lstm", "hyb_d", "hyb_z", "hyb_ms")]},
    "B": {"title": "M5 statistical", "threads": 1, "needs": [],
          "stages": [{"name": "stat_m5", "kind": "stat", "dataset": "m5", "model": "stat",
                      "args": ["scripts/run_statistical.py", "--dataset", "m5"]}]},
    "C": {"title": "M5 ffnn, lstm", "threads": 1, "needs": [],
          "stages": [_nn("m5", m) for m in ("ffnn", "lstm")]},
    "D": {"title": "M5 hybrids", "threads": 2, "needs": ["B", "C"],
          "stages": [_nn("m5", m) for m in ("hyb_d", "hyb_z", "hyb_ms")]},
    "E": {"title": "Evaluation and reports", "threads": 4, "needs": ["A", "B", "C", "D"],
          "stages": [
              _step("evaluation", ["scripts/run_evaluation.py", "--dataset", "all"]),
              _step("export_dashboard", ["scripts/export_dashboard.py"]),
              _step("summarise_results", ["scripts/summarise_results.py"]),
              _step("pytest", ["-m", "pytest", "-q", "-p", "no:cacheprovider", "--basetemp=outputs/interim/pt_tmp", "--junitxml=outputs/tests/pytest_results.xml"]),
              _step("make_report_tables", ["scripts/make_report_tables.py"]),
              _step("make_notebooks", ["scripts/make_notebooks.py"]),
          ]},
}
LANE_ORDER = list(LANES)


def state_dir() -> Path:
    return config.STATE_DIR


# ---------------------------------------------------------------------------------- process checks
def own_pids() -> set:
    """This process and its ancestors (the venv launcher starts the interpreter as a child)."""
    try:
        return {os.getpid(), *(p.pid for p in psutil.Process().parents())}
    except psutil.Error:
        return {os.getpid()}


def find_pipeline_processes(exclude=None) -> list:
    """Python processes running a pipeline script or the runner, excluding ``exclude`` (default: self + ancestors)."""
    exclude = own_pids() if exclude is None else exclude
    found = []
    for p in psutil.process_iter(["name", "cmdline"]):
        if p.pid in exclude or not (p.info.get("name") or "").lower().startswith("python"):
            continue
        cmd = " ".join(p.info.get("cmdline") or [])
        if "scripts\\run_" in cmd or "scripts/run_" in cmd or "run_chunks" in cmd:
            found.append(p)
    return found


def runner_pid_alive() -> int | None:
    """PID recorded in runner.pid if it names a live python process other than this one."""
    f = state_dir() / "runner.pid"
    if not f.exists():
        return None
    try:
        pid = int(f.read_text().strip())
    except ValueError:
        return None
    if pid in own_pids() or not psutil.pid_exists(pid):
        return None
    try:
        if not psutil.Process(pid).name().lower().startswith("python"):
            return None  # the PID was reused by an unrelated process
    except psutil.Error:
        return None
    return pid


def start_check() -> tuple[bool, str]:
    """(allowed, reason). Refuses if a pipeline process runs or runner.pid names a live process."""
    pid = runner_pid_alive()
    if pid:
        return False, f"another runner is active (pid {pid} in outputs/state/runner.pid)"
    others = find_pipeline_processes()
    if others:
        return False, "pipeline processes are already running: " + ", ".join(str(p.pid) for p in others)
    return True, ""


def set_awake(on: bool) -> None:
    if os.name == "nt":  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED, or ES_CONTINUOUS alone to release
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001 if on else 0x80000000)


def env_for(threads: int, lane: str) -> dict:
    env = dict(os.environ)
    env.update({
        "PYTHONHASHSEED": "0", "PIPELINE_LANE": lane,
        "OMP_NUM_THREADS": str(threads), "MKL_NUM_THREADS": str(threads),
        "OPENBLAS_NUM_THREADS": str(threads), "NUMEXPR_NUM_THREADS": str(threads),
        "TF_NUM_INTRAOP_THREADS": str(threads), "TF_NUM_INTEROP_THREADS": "1",
    })
    return env


# ---------------------------------------------------------------------------------- artefacts
def clean_stale_trials(live=None) -> list:
    """D-029: mark RUNNING Optuna trials as FAIL for stages that have no live process.

    ``live`` is the list of running pipeline processes (default: detected). Each change is logged.
    """
    from src import tuning_cleanup  # noqa: PLC0415 - imports optuna only when needed

    live = find_pipeline_processes() if live is None else live
    cmds = [" ".join(p.info.get("cmdline") or []) for p in live]
    changed = []
    for db in sorted(config.INTERIM_DIR.glob("optuna_*.db")):
        ds, kind = db.stem[len("optuna_"):].split("_", 1)
        if any(f"--dataset {ds}" in c and f"--model {kind}" in c for c in cmds):
            log(f"stale-trial check skipped for {db.name}: stage is running")
            continue
        for study, number in tuning_cleanup.mark_stale_trials(db):
            log(f"marked trial {number} of study {study} ({db.name}) as FAIL: {tuning_cleanup.FAILED_REASON}")
            changed.append((db.name, study, number))
    return changed


def _complete_trials(ds: str, model: str) -> int:
    import sqlite3
    db = config.INTERIM_DIR / f"optuna_{ds}_{model}.db"
    if not db.exists():
        return 0
    try:
        con = sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True, timeout=2)
        try:
            return int(con.execute("select count(*) from trials where state='COMPLETE'").fetchone()[0])
        finally:
            con.close()
    except sqlite3.Error:
        return 0


def _seeds_done(ds: str, model: str) -> int:
    return sum((config.INTERIM_DIR / f"{ds}_{model}_seed{s}_test.csv.gz").exists() for s in config.SEEDS)


def _series_done(ds: str) -> int:
    return sum((config.INTERIM_DIR / f"{ds}_stat_series_{s:02d}.pkl").exists() for s in range(N_SERIES[ds]))


def stage_complete(stage: dict) -> bool:
    ds, model = stage["dataset"], stage["model"]
    if stage["kind"] == "nn":
        return (config.FORECAST_DIR / f"{ds}_{model}_test.csv.gz").exists()
    if stage["kind"] == "stat":
        return ((config.FORECAST_DIR / f"{ds}_statistical.csv.gz").exists()
                and (config.INTERIM_DIR / f"{ds}_arima_artifacts.npz").exists())
    return (state_dir() / f"done_{stage['name']}.json").exists()


def stage_parts(stage: dict) -> list:
    """[(unit_type, total, done)] for a stage, from its artefacts."""
    ds, model = stage["dataset"], stage["model"]
    full = stage_complete(stage)
    if stage["kind"] == "nn":
        if model == "hyb_z":
            val = 1 if (full or (config.METRIC_DIR / f"{ds}_hyb_z_best_params.json").exists()) else 0
            first = ("validation", 1, val)
        else:
            first = ("trial", N_TRIALS, N_TRIALS if full else min(N_TRIALS, _complete_trials(ds, model)))
        return [first, ("seed", N_SEEDS, N_SEEDS if full else _seeds_done(ds, model))]
    if stage["kind"] == "stat":
        n = N_SERIES[ds]
        return [("series", n, n if full else _series_done(ds))]
    return [("step", 1, 1 if full else 0)]


def stage_item(stage: dict) -> str:
    """Human-readable current item, e.g. 'Rossmann LSTM, trial 4 of 15'."""
    ds = {"rossmann": "Rossmann", "m5": "M5"}.get(stage["dataset"], "")
    if stage["kind"] == "step":
        return {"pytest": "tests"}.get(stage["name"], stage["name"].replace("_", " "))
    if stage["kind"] == "stat":
        return f"{ds} statistical, series {min(_series_done(stage['dataset']) + 1, N_SERIES[stage['dataset']])} " \
               f"of {N_SERIES[stage['dataset']]}"
    name = f"{ds} {stage['model'].upper() if stage['model'] in ('ffnn', 'lstm') else stage['model']}"
    for unit, total, done in stage_parts(stage):
        if done < total:
            word = "validation run" if unit == "validation" else f"{unit} {done + 1} of {total}"
            return f"{name}, {word}"
    return f"{name}, finishing"


def newest_checkpoint() -> float | None:
    patterns = [(config.INTERIM_DIR, "optuna_*.db"), (config.INTERIM_DIR, "*_seed*_test.csv.gz"),
                (config.INTERIM_DIR, "*_trial*_validation.csv.gz"), (config.INTERIM_DIR, "*_stat_series_*.pkl"),
                (state_dir(), "done_*.json")]
    times = [f.stat().st_mtime for d, pat in patterns if d.exists() for f in d.glob(pat)]
    return max(times) if times else None


# ---------------------------------------------------------------------------------- measurements
_STAT_CACHE: dict = {}


def _stat_series_seconds(ds: str) -> list:
    """Per-series fit seconds (all models) from the specs json, else from the series checkpoints."""
    specs = config.METRIC_DIR / f"{ds}_statistical_specs.json"
    if specs.exists():
        try:
            return [_spec_seconds(s) for s in json.loads(specs.read_text(encoding="utf-8"))]
        except (OSError, ValueError):
            return []
    out = []
    for f in sorted(config.INTERIM_DIR.glob(f"{ds}_stat_series_*.pkl")):
        key = (str(f), f.stat().st_mtime)
        if key not in _STAT_CACHE:
            try:
                import pickle
                with f.open("rb") as fh:
                    _STAT_CACHE[key] = _spec_seconds(pickle.load(fh)["spec"])
            except Exception:  # noqa: BLE001 - a half-written checkpoint is simply not measured yet
                continue
        out.append(_STAT_CACHE[key])
    return out


def _spec_seconds(spec: dict) -> float:
    return float(sum(v for k, v in spec.items() if k.endswith("_seconds") and isinstance(v, (int, float))))


def _trim(values: list) -> list:
    """Drop invalid outliers (above OUTLIER_FACTOR x median), e.g. a unit that spanned a sleep."""
    if len(values) < 3:
        return values
    med = statistics.median(values)
    return [v for v in values if med <= 0 or v <= OUTLIER_FACTOR * med]


def collect_measurements(log_path: Path | None = None) -> dict:
    """{(dataset, model, unit_type): [seconds]} from EXPERIMENT_LOG, stat checkpoints and step markers."""
    raw: dict = {}
    path = log_path or config.EXPERIMENT_LOG
    if path.exists():
        with path.open(newline="", encoding="utf-8", errors="replace") as fh:
            for row in csv.DictReader(fh):
                ds, model, phase = row.get("dataset"), row.get("model"), row.get("phase")
                if ds not in config.DATASETS or model not in ("ffnn", "lstm", "hyb_d", "hyb_z", "hyb_ms"):
                    continue
                if "superseded" in (row.get("notes") or ""):
                    continue
                try:
                    secs = float(row["runtime_s"])
                except (TypeError, ValueError):
                    continue
                if phase == "tuning":
                    unit = "validation" if str(row.get("run_id", "")).endswith("-validation") else "trial"
                elif phase == "final":
                    unit = "seed"
                else:
                    continue
                raw.setdefault((ds, model, unit), []).append(secs)
    for ds in config.DATASETS:
        vals = _stat_series_seconds(ds)
        if vals:
            raw[(ds, "stat", "series")] = vals
    if state_dir().exists():
        for f in state_dir().glob("done_*.json"):
            try:
                raw[(None, f.stem[len("done_"):], "step")] = [float(json.loads(f.read_text())["runtime_s"])]
            except (OSError, ValueError, KeyError):
                pass
    return {k: _trim(v) for k, v in raw.items()}


def mean_measurements(raw: dict) -> dict:
    return {k: sum(v) / len(v) for k, v in raw.items() if v}


# ---------------------------------------------------------------------------------- estimation
def unit_seconds(dataset, model, unit, measurements: dict) -> float:
    """Mean seconds per unit: measured, else other dataset x DATASET_FACTOR, else a default constant."""
    m = measurements.get((dataset, model, unit))
    if m:
        return float(m)
    for other in config.DATASETS:
        if other != dataset and measurements.get((other, model, unit)) and (other, dataset) in DATASET_FACTOR:
            return float(measurements[(other, model, unit)]) * DATASET_FACTOR[(other, dataset)]
    if unit == "step":
        return STEP_DEFAULT_SECONDS.get(model, DEFAULT_UNIT_SECONDS["step"])
    return DEFAULT_UNIT_SECONDS[unit]


def stage_seconds_left(stage: dict, measurements: dict) -> float:
    """stage = {"dataset", "model", "parts": [(unit, total, done)]}."""
    return sum(max(total - done, 0) * unit_seconds(stage["dataset"], stage["model"], unit, measurements)
               for unit, total, done in stage["parts"])


def estimate_time_left(lanes: dict, measurements: dict, now: float) -> dict:
    """Time left per lane and overall, with lanes running in parallel.

    lanes = {lane: {"needs": [...], "state": "done"|"failed"|"blocked"|other, "stages": [stage, ...]}}.
    Returns lane_left (own work), lane_finish (seconds from now, including waits for dependencies),
    total_left (finish of the last lane) and finish_time (epoch seconds). Failed/blocked lanes count 0.
    """
    left, finish = {}, {}
    for lane, spec in lanes.items():
        dead = spec.get("state") in ("done", "failed", "blocked")
        left[lane] = 0.0 if dead else sum(stage_seconds_left(s, measurements) for s in spec["stages"])

    def fin(lane: str) -> float:
        if lane not in finish:
            start = max([fin(d) for d in lanes[lane]["needs"] if d in lanes] or [0.0])
            finish[lane] = start + left[lane]
        return finish[lane]

    for lane in lanes:
        fin(lane)
    total = max(finish.values()) if finish else 0.0
    return {"lane_left": left, "lane_finish": finish, "total_left": total, "finish_time": now + total}


# ---------------------------------------------------------------------------------- summary
def fmt_dur(seconds: float) -> str:
    seconds = max(int(seconds), 0)
    h, rem = divmod(seconds, 3600)
    m = rem // 60
    return f"{h} h {m:02d} min" if h else f"{m} min"


def build_view(statuses: dict, now: float | None = None) -> dict:
    """Compute the summary data from artefacts + lane statuses ({lane: status})."""
    now = now or time.time()
    raw = collect_measurements()
    meas = mean_measurements(raw)
    lanes, rows = {}, {}
    done_units = total_units = 0
    for lane, spec in LANES.items():
        stages, ldone, ltotal, current = [], 0, 0, None
        for st in spec["stages"]:
            parts = stage_parts(st)
            stages.append({"dataset": st["dataset"], "model": st["model"], "parts": parts})
            ldone += sum(d for _, _, d in parts)
            ltotal += sum(t for _, t, _ in parts)
            if current is None and not stage_complete(st):
                current = stage_item(st)
        status = statuses.get(lane, "waiting for dependency")
        if ldone == ltotal:
            status = "done" if status not in ("failed", "blocked") else status
        lanes[lane] = {"needs": spec["needs"], "state": status, "stages": stages}
        rows[lane] = {"title": spec["title"], "status": status, "item": current or "-",
                      "done": ldone, "total": ltotal}
        done_units += ldone
        total_units += ltotal
    est = estimate_time_left(lanes, meas, now)
    for lane in rows:
        rows[lane]["left"] = est["lane_left"][lane]
    elapsed = sum(sum(v) for v in raw.values())
    return {"rows": rows, "est": est, "done": done_units, "total": total_units, "elapsed": elapsed, "now": now}


def render(view: dict, errors: dict, runner_note: str = "") -> str:
    rows, est = view["rows"], view["est"]
    pct = 100.0 * view["done"] / view["total"] if view["total"] else 100.0
    finishing = "-" if view["done"] >= view["total"] else f"{datetime.fromtimestamp(est['finish_time']):%a %d %b %H:%M}"
    lines = [f"PIPELINE  {datetime.fromtimestamp(view['now']):%Y-%m-%d %H:%M:%S}  {runner_note}".rstrip(),
             f"Overall: {view['done']} of {view['total']} units ({pct:.1f}%) | compute time so far "
             f"{fmt_dur(view['elapsed'])} | est. left {fmt_dur(est['total_left'])} | est. finish {finishing}", ""]
    for lane, r in rows.items():
        lines.append(f"Lane {lane} {r['title']:<24} {r['status']:<24} {r['done']:>3}/{r['total']:<3} "
                     f"left {fmt_dur(r['left']):<11} {r['item'] if r['status'] not in ('done', 'blocked') else ''}")
        if lane in errors:
            lines.append(f"     ERROR: {errors[lane]['short']}")
    waiting = [f"{k} ({r['title']}) waits for {', '.join(LANES[k]['needs'])}" for k, r in rows.items()
               if r["status"] == "waiting for dependency"]
    lines += ["", "Waiting for dependencies: " + ("; ".join(waiting) if waiting else "none")]
    vm = psutil.virtual_memory()
    ck = newest_checkpoint()
    last = f"{datetime.fromtimestamp(ck):%H:%M:%S}" if ck else "none"
    lines.append(f"RAM {vm.percent:.0f}% used, {vm.available / 2**30:.1f} GB available | CPU "
                 f"{psutil.cpu_percent(interval=None):.0f}% | last checkpoint {last}")
    return "\n".join(lines)


RESUME_HEADER = """# Pipeline state

- Resume: run `Resume-Pipeline.bat` (in Code\\). It opens the runner window and continues from the checkpoints.
- Pause safely: press P in the runner window, run `Pause-Pipeline.bat`, or press Ctrl+C. Wait for
  "Paused safely" before shutting the computer down.
- Status: `Status-Pipeline.bat` (or `python scripts/run_chunks.py --status`) prints this summary.
- Lane E steps are marked done by `outputs/state/done_<step>.json`; delete a marker to run that step again.
- Never run pipeline stages inside the chat.

"""


def write_resume(text: str, errors: dict) -> None:
    out = [RESUME_HEADER, "```", text, "```", "", "## Lane errors", ""]
    if errors:
        for lane, e in errors.items():
            out += [f"### Lane {lane}: {e['stage']} (exit {e['code']})", "", "```", e["tail"], "```", ""]
    else:
        out.append("None.")
    state_dir().mkdir(parents=True, exist_ok=True)
    (state_dir() / "RESUME.md").write_text("\n".join(out) + "\n", encoding="utf-8")


def tail_lines(path: Path, n: int = 60) -> str:
    try:
        return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-n:])
    except OSError:
        return "(no log)"


def log(msg: str) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    with (LOGS / "run_chunks.log").open("a", encoding="utf-8") as fh:
        fh.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")


def next_run_number(stage_name: str) -> int:
    """Next n for run_id pipeline-<stage>-<n> (continues across runner sessions)."""
    pat, last = re.compile(rf"^pipeline-{re.escape(stage_name)}-(\d+)$"), 0
    if config.EXPERIMENT_LOG.exists():
        with config.EXPERIMENT_LOG.open(newline="", encoding="utf-8", errors="replace") as fh:
            for row in csv.DictReader(fh):
                m = pat.match(row.get("run_id") or "")
                if m:
                    last = max(last, int(m.group(1)))
    return last + 1


def record_run(stage_name, lane, start, end, code, threads) -> None:
    n = next_run_number(stage_name)
    note = (f"lane {lane}; start {datetime.fromtimestamp(start):%Y-%m-%d %H:%M:%S}; "
            f"end {datetime.fromtimestamp(end):%Y-%m-%d %H:%M:%S}; exit {code}; threads {threads}; "
            "run by scripts/run_chunks.py, see D-028")
    if code == utils.PAUSE_EXIT_CODE:
        note += "; paused at unit boundary"
    utils.log_experiment({"run_id": f"pipeline-{stage_name}-{n}", "phase": "pipeline", "dataset": "",
                          "model": "", "runtime_s": round(end - start, 1), "notes": note,
                          "script": "scripts/run_chunks.py"})


# ---------------------------------------------------------------------------------- runner
class Lane:
    def __init__(self, name: str):
        self.name, self.spec = name, LANES[name]
        self.proc = None
        self.stage = None
        self.start = 0.0
        self.status = "waiting for dependency"
        self.failures: dict = {}
        self.forced_done: set = set()
        self.cooldown_until = 0.0
        self.pause_asked = False
        self.dead = None  # "failed" | "blocked"

    def next_stage(self):
        for st in self.spec["stages"]:
            if st["name"] not in self.forced_done and not stage_complete(st):
                return st
        return None

    @property
    def done(self) -> bool:
        return self.next_stage() is None


class Runner:
    def __init__(self):
        self.lanes = {k: Lane(k) for k in LANE_ORDER}
        self.errors: dict = {}
        self.pause_asked = False
        self.cores = psutil.cpu_count() or 4
        self.last_start: dict = {}

    # -- control
    def request_pause(self, *_):
        if not self.pause_asked:
            self.pause_asked = True
            print("\nPausing: finishing current units…", flush=True)
            state_dir().mkdir(parents=True, exist_ok=True)
            (state_dir() / "PAUSE").touch()
            log("pause requested")

    def pausing(self) -> bool:
        if (state_dir() / "PAUSE").exists() and not self.pause_asked:
            self.request_pause()
        return self.pause_asked

    # -- lane processes
    def running(self) -> list:
        return [l for l in self.lanes.values() if l.proc is not None]

    def launch(self, lane: Lane, stage: dict) -> None:
        lane.stage, lane.pause_asked = stage, False
        (state_dir() / f"PAUSE_{lane.name}").unlink(missing_ok=True)
        LOGS.mkdir(parents=True, exist_ok=True)
        out = (LOGS / f"{stage['name']}.log").open("a", encoding="utf-8")
        out.write(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} lane {lane.name} =====\n")
        out.flush()
        flags = (getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        lane.proc = subprocess.Popen([PY, *stage["args"]], cwd=CODE, env=env_for(lane.spec["threads"], lane.name),
                                     stdout=out, stderr=subprocess.STDOUT, creationflags=flags)
        out.close()
        lane.start = time.time()
        lane.status = "running"
        self.last_start[lane.name] = lane.start
        log(f"start lane {lane.name} {stage['name']} pid {lane.proc.pid} threads {lane.spec['threads']}")

    def handle_exit(self, lane: Lane) -> None:
        code, end, stage = lane.proc.returncode, time.time(), lane.stage
        record_run(stage["name"], lane.name, lane.start, end, code, lane.spec["threads"])
        log(f"finished lane {lane.name} {stage['name']} exit {code} after {end - lane.start:.0f} s")
        lane.proc = None
        (state_dir() / f"PAUSE_{lane.name}").unlink(missing_ok=True)
        if code == 0:
            lane.failures.pop(stage["name"], None)
            if stage["kind"] == "step":
                state_dir().mkdir(parents=True, exist_ok=True)
                (state_dir() / f"done_{stage['name']}.json").write_text(json.dumps({
                    "step": stage["name"], "finished": datetime.now().isoformat(timespec="seconds"),
                    "runtime_s": round(end - lane.start, 1), "exit": 0}), encoding="utf-8")
            if not stage_complete(stage):
                lane.forced_done.add(stage["name"])  # exit 0 is authoritative; never loop on a missing marker
            lane.status = "done" if lane.done else "waiting for dependency"
        elif code == utils.PAUSE_EXIT_CODE:
            if self.pause_asked:
                lane.status = "paused"
            else:
                lane.status = "waiting for memory"
                lane.cooldown_until = end + REQUEUE_COOLDOWN_S
        else:
            n = lane.failures[stage["name"]] = lane.failures.get(stage["name"], 0) + 1
            if n < 2:
                log(f"retrying {stage['name']} from its checkpoint")
                lane.status = "waiting for memory"
            else:
                tail = tail_lines(LOGS / f"{stage['name']}.log")
                last = [x for x in tail.splitlines() if x.strip()][-1:] or ["no output"]
                lane.dead = "failed"
                lane.status = "failed"
                self.errors[lane.name] = {"stage": stage["name"], "code": code, "tail": tail,
                                          "short": f"{stage['name']} failed twice (exit {code}): {last[0][:110]}"}
                (LOGS / f"lane_{lane.name}_FAILED.txt").write_text(
                    f"{stage['name']} failed twice (exit {code}). Last log lines:\n{tail}\n", encoding="utf-8")
                log(f"lane {lane.name} FAILED at {stage['name']}")

    # -- scheduling
    def footprint_gb(self, lane: Lane, stage: dict) -> float:
        return MEM_FOOTPRINT_GB["tf" if stage["kind"] == "nn" else stage["kind"]]

    def update_statuses(self) -> None:
        for lane in self.lanes.values():
            if lane.proc is not None or lane.dead == "failed":
                continue
            if lane.done:
                lane.status = "done"
                continue
            deps = [self.lanes[d] for d in lane.spec["needs"]]
            if any(d.dead for d in deps):
                lane.dead, lane.status = "blocked", "blocked"
            elif lane.status in ("done", "blocked") or any(not d.done for d in deps):
                lane.status = "waiting for dependency" if any(not d.done for d in deps) else "waiting for memory"
            elif lane.status == "waiting for dependency":
                lane.status = "waiting for memory"

    def admit(self) -> None:
        if self.pausing():
            return
        now = time.time()
        for lane in self.lanes.values():
            if lane.proc is not None or lane.dead or lane.done:
                continue
            if any(not self.lanes[d].done for d in lane.spec["needs"]):
                continue
            stage = lane.next_stage()
            running = self.running()
            if running:
                if now < lane.cooldown_until:
                    lane.status = "waiting for memory"
                    continue
                if sum(l.spec["threads"] for l in running) + lane.spec["threads"] > self.cores:
                    lane.status = "waiting for memory"
                    continue
                vm = psutil.virtual_memory()
                reserved = sum(self.footprint_gb(l, l.stage) for l in running
                               if now - l.start < RECENT_START_S) * 2**30
                after = vm.available - reserved - self.footprint_gb(lane, stage) * 2**30
                if after < MEM_LOW * vm.total:
                    lane.status = "waiting for memory"
                    continue
            self.launch(lane, stage)

    def memory_guard(self) -> None:
        running = [l for l in self.running() if l.name != "E"]
        vm = psutil.virtual_memory()
        if (len(self.running()) < 2 or len(running) < 1 or vm.available / vm.total >= MEM_LOW
                or any(l.pause_asked for l in self.running())):
            return
        newest = max(running, key=lambda l: l.start)
        newest.pause_asked = True
        state_dir().mkdir(parents=True, exist_ok=True)
        (state_dir() / f"PAUSE_{newest.name}").touch()
        log(f"memory low ({vm.available / vm.total:.0%} available): asked lane {newest.name} to pause at its unit boundary")

    def tick(self) -> None:
        for lane in self.running():
            if lane.proc.poll() is not None:
                self.handle_exit(lane)
        self.update_statuses()
        self.admit()
        self.memory_guard()

    def statuses(self) -> dict:
        out = {}
        for k, l in self.lanes.items():
            s = l.status
            if l.proc is not None and l.pause_asked:
                s = "running (pausing for memory)"
            if self.pause_asked and l.proc is not None:
                s = "running (finishing unit)"
            out[k] = s
        return out

    def save_status(self, view_text: str) -> None:
        state_dir().mkdir(parents=True, exist_ok=True)
        (state_dir() / "status.json").write_text(json.dumps({
            "updated": datetime.now().isoformat(timespec="seconds"), "pid": os.getpid(),
            "statuses": self.statuses(), "errors": self.errors}), encoding="utf-8")
        write_resume(view_text, self.errors)

    def refresh(self, clear: bool = True) -> str:
        set_awake(True)
        view = build_view(self.statuses())
        note = "PAUSING" if self.pause_asked else "runner active"
        text = render(view, self.errors, note) + ("" if self.pause_asked else "\n\nP = pause safely")
        self.save_status(text)
        if clear:
            os.system("cls" if os.name == "nt" else "clear")
        print(text, flush=True)
        return text

    def all_finished(self) -> bool:
        return not self.running() and all(l.done or l.dead for l in self.lanes.values())


def poll_keys() -> bool:
    """True if P was pressed in the runner window."""
    if os.name != "nt":
        return False
    import msvcrt
    hit = False
    while msvcrt.kbhit():
        if msvcrt.getwch().lower() == "p":
            hit = True
    return hit


def clear_pause_files() -> None:
    d = state_dir()
    if d.exists():
        for f in d.glob("PAUSE*"):
            f.unlink(missing_ok=True)


def finish_pause(r: Runner) -> int:
    """All children have exited: verify nothing is left, write RESUME.md, clean flags, release awake."""
    deadline = time.time() + 300
    while True:
        left = find_pipeline_processes()
        if not left or time.time() > deadline:
            break
        time.sleep(2)
    r.refresh(clear=False)
    clear_pause_files()
    set_awake(False)
    if left:
        print("WARNING: pipeline processes still running: " + ", ".join(str(p.pid) for p in left))
        return 1
    print("Paused safely. You can shut down the computer.", flush=True)
    log("paused safely")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--status", action="store_true", help="print the latest summary and exit")
    args = ap.parse_args()
    if args.status:
        sys.exit(status_main())

    sys.stdout.reconfigure(errors="replace")
    ok, why = start_check()
    if not ok:
        print(f"Refusing to start: {why}.")
        sys.exit(1)
    sd = state_dir()
    sd.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    stale = list(sd.glob("PAUSE*"))
    if stale:
        msg = f"removed stale pause flags {[f.name for f in stale]} (a completed pause deletes them; likely a crash)"
        print(msg)
        log(msg)
        clear_pause_files()
    (sd / "runner.pid").write_text(str(os.getpid()))
    clean_stale_trials(live=[])  # start_check has confirmed that no pipeline process is running
    log(f"runner started pid {os.getpid()}, {psutil.cpu_count()} logical cores")
    psutil.cpu_percent(interval=None)
    r = Runner()
    signal.signal(signal.SIGINT, r.request_pause)
    code = 0
    try:
        last_refresh = 0.0
        while True:
            try:
                if poll_keys():
                    r.request_pause()
                r.tick()
                if time.time() - last_refresh >= REFRESH_S:
                    r.refresh(clear=not r.pause_asked)
                    last_refresh = time.time()
                if r.pausing() and not r.running():
                    code = finish_pause(r)
                    break
                if r.all_finished():
                    r.refresh(clear=False)
                    clear_pause_files()
                    print("Pipeline finished (see lane states above).", flush=True)
                    log("pipeline finished")
                    break
                time.sleep(TICK_S)
            except KeyboardInterrupt:
                r.request_pause()
    finally:
        set_awake(False)
        (sd / "runner.pid").unlink(missing_ok=True)
    sys.exit(code)


def status_main() -> int:
    """--status: recompute from artefacts and the last runner status; start nothing."""
    st, errors, note = {}, {}, "runner not running"
    f = state_dir() / "status.json"
    if f.exists():
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            st, errors = data.get("statuses", {}), data.get("errors", {})
            note = f"runner active (last update {data.get('updated')})" if runner_pid_alive() \
                else f"runner not running; last known state {data.get('updated')}"
        except ValueError:
            pass
    if not runner_pid_alive():  # lanes cannot be running without a runner
        st = {k: v for k, v in st.items() if v in ("failed", "blocked")}
        st = {k: st.get(k, "not running") for k in LANES}
    for lane in LANES:
        p = LOGS / f"lane_{lane}_FAILED.txt"
        if lane not in errors and p.exists() and st.get(lane) == "failed":
            errors[lane] = {"stage": "?", "code": "?", "tail": tail_lines(p), "short": f"see {p.name}"}
    print(render(build_view(st), errors, note))
    return 0


if __name__ == "__main__":
    main()
