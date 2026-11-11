#!/usr/bin/env bash
# Inverse contact-height calibration sweep.
#
# WHAT THIS DOES
#   Runs the SAME frozen round-1/round-2 driver (run_batch_v2.sh) once per commanded
#   contact_height_m, single-shot arm, one attempt, dev seed2000. The ONLY variable across
#   runs is contact_height_m. Every run therefore has a genuinely instantiated dev instance
#   (run_batch_v2.sh step 2b), a full evidence bundle, and the per-step contact log the
#   calibration reads.
#
# WHY THE DRIVER IS CALLED RATHER THAN COPIED
#   The measurement has to come from the same code path that produced the trials being
#   explained. Forking the driver for a calibration would make the calibration a statement
#   about a different program. run_batch_v2.sh is unmodified; this script only loops.
#
# WHY ONE HEIGHT PER INVOCATION
#   run_batch_v2.sh takes the flock and refuses if a simulator is already running, which is
#   exactly the guard that must not be bypassed. Calling it once per height keeps that guard
#   in force for every run instead of holding the lock in a parent and deadlocking the child.
#
# HEIGHTS
#   The sweep brackets the predicted face-contact command. The rigid-offset model, fitted to
#   the already-measured (0.0200 -> 0.0349) point, predicts the command that puts contact at
#   the block centre (0.0175) is near 0.0026, so the sweep includes 0.0050 and 0.0000
#   around it and extends in both directions to show the slope.
set -u

WT=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
DRIVER=$WT/setup/acceptance/evobot_t08_instance_pose_20261112/run_batch_v2.sh
TASK=$WT/benchmark/tasks/t08_dev/T08-push-seed2000.json
OUT=${1:-$WT/setup/acceptance/evobot_t08_contact_calibration_20261112/runs}

# height|arm-label. Arm labels are descriptive only; the analysis reads the commanded
# height from each run's manifest.txt so a label can never be confused with a measurement.
POINTS="0.0200|H0200 0.0150|H0150 0.0100|H0100 0.0050|H0050 0.0000|H0000 -0.0050|HM0050"

mkdir -p "$OUT"
for point in $POINTS; do
  H="${point%%|*}"; LABEL="${point##*|}"
  echo
  echo "################################################################"
  echo "### commanded contact_height_m = $H   (arm $LABEL)"
  echo "################################################################"
  # single shot (1 attempt), ceiling guard 0.140 as specified for this sweep
  bash "$DRIVER" "$OUT" "$LABEL" "$TASK" 1 1 "$H" 0.140
  RC=$?
  echo "### driver rc=$RC for contact_height_m=$H"
  # A non-zero rc is recorded, not fatal: the next height is still a valid measurement.
  echo "$RC" > "$OUT/$LABEL/driver_rc.txt" 2>/dev/null || true
done

echo
echo "SWEEP_DONE"
