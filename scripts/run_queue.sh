#!/usr/bin/env bash
# Run experiment steps one after another (no parallel jobs, so runtimes are not distorted).
#
# Usage (from Code/):  bash scripts/run_queue.sh stat:rossmann nn:rossmann:ffnn nn:rossmann:lstm
#   stat:<dataset>          statistical benchmarks
#   nn:<dataset>:<model>    tuning (15 Optuna trials) + five-seed final training
set -u
cd "$(dirname "$0")/.."
PY=./.venv/Scripts/python.exe
[ -x "$PY" ] || PY=python
mkdir -p outputs/logs
for step in "$@"; do
  IFS=: read -r kind ds model <<< "$step"
  echo "$(date +%H:%M:%S) start $step" >> outputs/logs/queue.log
  if [ "$kind" = "stat" ]; then
    "$PY" scripts/run_statistical.py --dataset "$ds" > "outputs/logs/stat_${ds}.log" 2>&1
  else
    "$PY" scripts/run_neural.py --dataset "$ds" --model "$model" --trials 15 > "outputs/logs/nn_${ds}_${model}.log" 2>&1
  fi
  echo "$(date +%H:%M:%S) finished $step exit=$?" >> outputs/logs/queue.log
done
