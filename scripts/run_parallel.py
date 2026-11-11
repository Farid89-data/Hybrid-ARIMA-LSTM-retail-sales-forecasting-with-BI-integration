"""Run the remaining pipeline in parallel lanes with dependencies, a memory guard and retries.

Lanes (each lane runs its steps in order; every step resumes from its own checkpoints):
  A  Rossmann networks: ffnn, lstm, hyb_d, hyb_z, hyb_ms (uses the saved Rossmann ARIMA residuals)
  B  M5 statistical benchmarks (seasonal naive, ARIMA, ETS)
  C  M5 networks without ARIMA input: ffnn, lstm
  D  M5 hybrids: hyb_d, hyb_z, hyb_ms (starts when B and C have finished)
  E  evaluation, Power BI export, report tables and result facts (starts when A to D have finished)

Thread limits are passed through OMP/MKL/OpenBLAS and the TensorFlow environment variables, so
the total stays within the logical core count. If available memory falls below MEM_LOW of the
total, the newest running step is suspended (never the last running one) and resumed when memory
recovers above MEM_RESUME. Suspended time is recorded per step, because it inflates wall-clock
runtimes. A failed step is retried once; a second failure stops only that lane (and lanes that
depend on it) and writes outputs/logs/lane_<X>_FAILED.txt.

The machine is kept awake while the scheduler runs. Progress: outputs/logs/parallel.log,
process IDs: outputs/logs/pids.txt, step logs: outputs/logs/<stage>.log.

Usage (from Code/):  python scripts/run_parallel.py
"""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil

CODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE))

from src import utils  # noqa: E402

PY = str(CODE / ".venv" / "Scripts" / "python.exe") if (CODE / ".venv").exists() else sys.executable
LOGS = CODE / "outputs" / "logs"
STATE = LOGS / "parallel_state.json"
MEM_LOW, MEM_RESUME = 0.15, 0.25
POLL = 30


def nn(ds, model):
    return (f"nn_{ds}_{model}", ["scripts/run_neural.py", "--dataset", ds, "--model", model, "--trials", "15"])


LANES = {
    "A": {"threads": 2, "needs": [], "steps": [nn("rossmann", m) for m in ("ffnn", "lstm", "hyb_d", "hyb_z", "hyb_ms")]},
    "B": {"threads": 1, "needs": [], "steps": [("stat_m5", ["scripts/run_statistical.py", "--dataset", "m5"])]},
    "C": {"threads": 1, "needs": [], "steps": [nn("m5", m) for m in ("ffnn", "lstm")]},
    "D": {"threads": 2, "needs": ["B", "C"], "steps": [nn("m5", m) for m in ("hyb_d", "hyb_z", "hyb_ms")]},
    "E": {"threads": 4, "needs": ["A", "B", "C", "D"], "steps": [
        ("evaluation", ["scripts/run_evaluation.py", "--dataset", "all"]),
        ("export_dashboard", ["scripts/export_dashboard.py"]),
        ("report_tables", ["scripts/make_report_tables.py"]),
        ("summarise_results", ["scripts/summarise_results.py"]),
    ]},
}


def log(msg: str) -> None:
    with (LOGS / "parallel.log").open("a", encoding="utf-8") as fh:
        fh.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")


def keep_awake() -> None:
    if os.name == "nt":  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)


def env_for(threads: int) -> dict:
    env = dict(os.environ)
    env.update({
        "PYTHONHASHSEED": "0",
        "OMP_NUM_THREADS": str(threads), "MKL_NUM_THREADS": str(threads),
        "OPENBLAS_NUM_THREADS": str(threads), "NUMEXPR_NUM_THREADS": str(threads),
        "TF_NUM_INTRAOP_THREADS": str(threads), "TF_NUM_INTEROP_THREADS": "1",
    })
    return env


def record(stage, lane, start, end, code, threads, suspended, attempt):
    utils.log_experiment({
        "run_id": f"pipeline-{stage}-attempt{attempt}", "phase": "pipeline", "dataset": "",
        "model": "", "runtime_s": round(end - start, 1),
        "notes": (f"lane {lane}; start {datetime.fromtimestamp(start):%Y-%m-%d %H:%M:%S}; "
                  f"end {datetime.fromtimestamp(end):%Y-%m-%d %H:%M:%S}; exit {code}; threads {threads}; "
                  f"suspended {suspended:.0f} s; run in parallel lanes, see D-027"),
    })


class Step:
    def __init__(self, lane, stage, args, threads):
        self.lane, self.stage, self.args, self.threads = lane, stage, args, threads
        self.proc, self.start, self.attempt = None, None, 0
        self.suspended_at, self.suspended_total = None, 0.0

    def launch(self):
        self.attempt += 1
        out = (LOGS / f"{self.stage}.log").open("a", encoding="utf-8")
        out.write(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} attempt {self.attempt} =====\n")
        out.flush()
        self.proc = subprocess.Popen([PY, *self.args], cwd=CODE, env=env_for(self.threads),
                                     stdout=out, stderr=subprocess.STDOUT,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.start = time.time()
        with (LOGS / "pids.txt").open("a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} lane {self.lane} {self.stage} attempt {self.attempt} "
                     f"pid {self.proc.pid} threads {self.threads}\n")
        log(f"start lane {self.lane} {self.stage} (attempt {self.attempt}, pid {self.proc.pid}, threads {self.threads})")

    def _tree(self):
        try:
            p = psutil.Process(self.proc.pid)
            return [p, *p.children(recursive=True)]
        except psutil.NoSuchProcess:
            return []

    def suspend(self):
        for p in self._tree():
            p.suspend()
        self.suspended_at = time.time()
        log(f"memory low: suspended {self.stage}")

    def resume(self):
        for p in self._tree():
            p.resume()
        self.suspended_total += time.time() - self.suspended_at
        self.suspended_at = None
        log(f"memory recovered: resumed {self.stage}")


def main() -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    # The venv launcher starts the interpreter as a child process, so exclude this process's ancestors.
    own = {os.getpid(), *(p.pid for p in psutil.Process().parents())}
    others = [p for p in psutil.process_iter(["name", "cmdline"])
              if p.pid not in own and (p.info["name"] or "").lower().startswith("python")
              and any("run_" in a for a in (p.info["cmdline"] or []))]
    if others:
        log(f"refusing to start: pipeline processes already running {[p.pid for p in others]}")
        sys.exit(1)
    with (LOGS / "pids.txt").open("a", encoding="utf-8") as fh:
        fh.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} scheduler pid {os.getpid()}\n")
    log(f"scheduler started (pid {os.getpid()}, {psutil.cpu_count()} logical cores)")
    state = {k: "waiting" for k in LANES}
    pos = {k: 0 for k in LANES}
    running: dict[str, Step] = {}
    while True:
        keep_awake()
        # finished steps
        for lane, step in list(running.items()):
            code = step.proc.poll()
            if code is None:
                continue
            end = time.time()
            record(step.stage, lane, step.start, end, code, step.threads, step.suspended_total, step.attempt)
            log(f"finished lane {lane} {step.stage} exit {code} after {end - step.start:.0f} s "
                f"(suspended {step.suspended_total:.0f} s)")
            del running[lane]
            if code == 0:
                pos[lane] += 1
                if pos[lane] == len(LANES[lane]["steps"]):
                    state[lane] = "done"
            elif step.attempt < 2:
                log(f"retrying {step.stage} from its checkpoint")
                step.launch()
                running[lane] = step
            else:
                state[lane] = "failed"
                tail = (LOGS / f"{step.stage}.log").read_text(encoding="utf-8", errors="replace")[-8000:]
                (LOGS / f"lane_{lane}_FAILED.txt").write_text(
                    f"{step.stage} failed twice (exit {code}). Last log lines:\n{tail}", encoding="utf-8")
                log(f"lane {lane} FAILED at {step.stage}")
        # lanes blocked by a failed dependency
        for lane, spec in LANES.items():
            if state[lane] == "waiting" and any(state[d] == "failed" for d in spec["needs"]):
                state[lane] = "blocked"
                log(f"lane {lane} blocked: a lane it depends on failed")
        # start ready steps
        for lane, spec in LANES.items():
            if lane in running or state[lane] in ("done", "failed", "blocked"):
                continue
            if all(state[d] == "done" for d in spec["needs"]):
                state[lane] = "running"
                stage, args = spec["steps"][pos[lane]]
                step = Step(lane, stage, args, spec["threads"])
                step.launch()
                running[lane] = step
        # memory guard
        vm = psutil.virtual_memory()
        frac = vm.available / vm.total
        active = [s for s in running.values() if s.suspended_at is None]
        paused = [s for s in running.values() if s.suspended_at is not None]
        if frac < MEM_LOW and len(active) > 1:
            max(active, key=lambda s: s.start).suspend()
        elif frac > MEM_RESUME and paused:
            min(paused, key=lambda s: s.start).resume()
        STATE.write_text(json.dumps({
            "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "available_memory_fraction": round(frac, 3), "lanes": state,
            "running": {k: {"stage": s.stage, "pid": s.proc.pid, "suspended": s.suspended_at is not None}
                        for k, s in running.items()},
        }, indent=2), encoding="utf-8")
        if not running and all(v in ("done", "failed", "blocked") for v in state.values()):
            log(f"scheduler finished: {state}")
            if os.name == "nt":
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            break
        time.sleep(POLL)


if __name__ == "__main__":
    main()
