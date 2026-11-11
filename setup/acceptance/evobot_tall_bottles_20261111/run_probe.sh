#!/bin/bash
# Run the tall-bottle probe.  Usage: run_probe.sh <phase> <task-index> [more task indexes]
# NEWOBS=0 skips camera observations (physics identical, much faster on a loaded CPU).
V=/home/ros/ext-bench/venv-libero; . $V/bin/activate
export MUJOCO_GL=osmesa
export NEWOBS=${NEWOBS:-0}
SCRIPT=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp/setup/acceptance/evobot_tall_bottles_20261111/evobot_tall_probe.py
OUT=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp/setup/acceptance/evobot_tall_bottles_20261111/raw
PHASE=$1; shift
mkdir -p "$OUT"
for T in "$@"; do
  echo "##### phase=$PHASE task=$T"
  LIBERO_TASK=$T PHASE=$PHASE LIBERO_OUTDIR=$OUT python -u "$SCRIPT" 2>&1 \
    | grep -vE "^\[robosuite|Gym has|Please upgrade|Users of|migration|WARNING|^$" \
    | tee -a "$OUT/run_${PHASE}_${T}.log"
done
