#!/bin/bash
# Run probe phases.  Usage: run_phase.sh <phase> <tasks> [N_INIT]
#   phase : measure | settle | descend | info | basket | matrix | release | carry | fixed
#   tasks : comma separated task indexes, e.g. 2,4
#   N_INIT: only used by the 'fixed' phase (how many shipped init states to try)
#
# Output goes to raw/<phase>/ for the per-task phases, so re-running a phase regenerates
# exactly the files verify.py reads.  The 'fixed' phase writes raw/fixed_*.json at the top.
V=/home/ros/ext-bench/venv-libero
. "$V/bin/activate"
export MUJOCO_GL=osmesa
export NEWOBS=${NEWOBS:-0}
HERE=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp/setup/acceptance/evobot_tall_bottles_20261111
PHASE=$1
TASKS=$2
N_INIT=${3:-5}
mkdir -p "$HERE/raw"

filter() {
  grep -vE "^\[robosuite|Gym has|Please upgrade|Users of|migration|WARNING|^$"
}

if [ "$PHASE" = "fixed" ]; then
  TASKS="$TASKS" N_INIT="$N_INIT" PHASE=fixed LIBERO_OUTDIR="$HERE/raw" \
    python -u "$HERE/evobot_tall_probe.py" 2>&1 | filter \
    | tee "$HERE/raw/run_fixed_${TASKS}.log"
else
  OUT="$HERE/raw/$PHASE"
  mkdir -p "$OUT"
  for T in $(echo "$TASKS" | tr ',' ' '); do
    echo "##### phase=$PHASE task=$T"
    LIBERO_TASK="$T" PHASE="$PHASE" LIBERO_OUTDIR="$OUT" \
      python -u "$HERE/evobot_tall_probe.py" 2>&1 | filter \
      | tee "$HERE/raw/run_${PHASE}_${T}.log"
  done
fi
