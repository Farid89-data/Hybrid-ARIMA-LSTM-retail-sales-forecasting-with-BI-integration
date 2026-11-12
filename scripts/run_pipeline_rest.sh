#!/usr/bin/env bash
# Remaining pipeline after the Rossmann statistical stage, one step after another.
# Each stage resumes from its own checkpoints, so the script can simply be started again
# after an interruption. Progress is in outputs/logs/queue.log and outputs/logs/pipeline_rest.log.
#
# Usage (from Code/):  bash scripts/run_pipeline_rest.sh
set -u
cd "$(dirname "$0")/.."
PY=./.venv/Scripts/python.exe
[ -x "$PY" ] || PY=python
LOG=outputs/logs/pipeline_rest.log
step() {
  echo "$(date +%H:%M:%S) start $*" >> "$LOG"
  PYTHONHASHSEED=0 "$PY" "$@" >> "$LOG" 2>&1
  echo "$(date +%H:%M:%S) finished $* exit=$?" >> "$LOG"
}

bash scripts/run_queue.sh nn:rossmann:ffnn nn:rossmann:lstm nn:rossmann:hyb_d nn:rossmann:hyb_z nn:rossmann:hyb_ms
step scripts/run_evaluation.py --dataset rossmann
bash scripts/run_queue.sh stat:m5 nn:m5:ffnn nn:m5:lstm nn:m5:hyb_d nn:m5:hyb_z nn:m5:hyb_ms
step scripts/run_evaluation.py --dataset all
step scripts/export_dashboard.py
step scripts/make_report_tables.py
step scripts/summarise_results.py
echo "$(date +%H:%M:%S) pipeline complete" >> "$LOG"
