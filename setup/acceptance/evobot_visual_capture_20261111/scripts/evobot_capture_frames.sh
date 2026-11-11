#!/bin/bash
# Capture camera frames at the moments that matter, then pair them with truth.
#
# WHY A SEPARATE SCRIPT AND NOT A FLAG INSIDE evobot_run_b.sh
#   evobot_run_b.sh is how Baseline A and Baseline B are measured. Adding an
#   optional branch inside it would mean the measured path and the edited path
#   are the same file, and every future reader would have to prove the branch
#   is inert. This script WRAPS it instead: the baseline runs unchanged, and
#   this one captures around it. With CAPTURE_FRAMES unset it does nothing.
#
# WHAT A CAPTURE MEANS, AND WHAT IT DOES NOT
#   A capture means: an image file was written, and ground truth was measured
#   within a stated gap of that frame. It does NOT mean the image was
#   interpreted, that anything in it was recognised, or that the robot sees.
#
# WHY THE STAGE HOOK READS THE JOURNAL
#   The composite journal is append-only and fsynced at every event, so a
#   "COMMITTED" line appears exactly when a stage committed. Polling it cannot
#   miss a stage and cannot invent one; polling a log tail or a topic can do
#   either.
#
# Usage:
#   CAPTURE_FRAMES=1 evobot_capture_frames.sh <spec.json> <out_dir> [domain]
#   (without CAPTURE_FRAMES=1: prints CAPTURE_DISABLED and exits 0)

set -o pipefail
SPEC=$1
OUT=${2:?output directory required}
# Low domain: CycloneDDS rejects high ids and every node in the stack dies with
# "error creating node: error not set". 212 exceeded the usable range.
DOMAIN=${3:-46}
W=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
SNAP="$W/src/flexcell/flexcell_skills/flexcell_skills/camera_snapshot.py"
# ci-public-window/scripts is a SIBLING of wt-comp, not a child of it.
CI=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/ci-public-window/scripts
PAIR="$CI/evobot_visual_vs_truth.py"
FRAMES="$OUT/frames"

if [ "${CAPTURE_FRAMES:-0}" != "1" ]; then
  echo "CAPTURE_DISABLED (set CAPTURE_FRAMES=1 to capture)"
  exit 0
fi

# Only one high-load sim at a time: refuse rather than compete with a batch.
if pgrep -f "evobot_batch_v2_gated" > /dev/null 2>&1; then
  echo "REFUSED: a gated batch is running. Queue behind it; capturing"
  echo "alongside would perturb both runs."
  exit 9
fi
if pgrep -f "[g]z sim" > /dev/null 2>&1; then
  echo "REFUSED: a gz sim is already running; only one high-load sim at a time."
  pgrep -af "[g]z sim" | head -3
  exit 9
fi

mkdir -p "$FRAMES" || exit 3
echo "CAPTURE_ENABLED out=$FRAMES"

source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash 2>/dev/null
source /home/ros/flexcell-p14-ws/install/setup.bash 2>/dev/null
export GZ_PARTITION=evobot-cap RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID="$DOMAIN" LIBGL_ALWAYS_SOFTWARE=1
# Same reason as evobot_vis_live_capture.sh: the snapshot tool's truth sampler
# imports flexcell_skills.common, and running a file by path does not put the
# package root on sys.path.
export PYTHONPATH="$W/src/flexcell/flexcell_skills:${PYTHONPATH:-}"

# Object names come from the spec, so the truth sample matches the task.
NAMES=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(' '.join(o['name'] for o in d['objects']))" "$SPEC" 2>/dev/null)
echo "truth objects: $NAMES"

FAILED_CAPTURES=0
CAPTURE_COUNT=0

capture () {
  local label=$1
  local min_stamp=${2:-0}
  local index
  index=$(printf "%02d" "$CAPTURE_COUNT")
  CAPTURE_COUNT=$((CAPTURE_COUNT+1))
  local target="$FRAMES/${index}_${label}"
  echo "--- capture $label -> $target.png"
  # --truth-objects makes the snapshot tool sample ground truth itself,
  # immediately after the frame, so the pairing gap is measured rather than
  # reconstructed later.
  python3 "$SNAP" --out "$target.png" --label "$label" --timeout 20 \
      --min-stamp-ns "$min_stamp" --truth-objects $NAMES \
      >> "$OUT/capture.log" 2>&1
  local rc=$?
  echo "    rc=$rc"
  if [ $rc -ne 0 ]; then
    FAILED_CAPTURES=$((FAILED_CAPTURES+1))
    # A refusal is a finding, not a nuisance: surface it immediately.
    tail -2 "$OUT/capture.log" | sed "s/^/    /"
  fi
  return $rc
}

# ------------------------------------------------------------- task start
# The caller guarantees the stack is up before invoking this script, and no
# motion has been commanded yet, so min_stamp is 0 (any frame is "before").
capture task_start

# ------------------------------------- run the baseline, unmodified, beside us
echo "=== delegating to evobot_run_b.sh (unmodified) ==="
"$W/ci-public-window/scripts/evobot_run_b.sh" "$SPEC" "$OUT" &
RUN_PID=$!

# ------------------------------------------------- stage boundaries + end
# task_fsm_server writes composites under <log_dir>/composites, and the
# profile sets log_dir to <out>/sim/skills (sim_profile.py).
JOURNAL_DIR="$OUT/sim/skills/composites"
SEEN=0
while kill -0 $RUN_PID 2>/dev/null; do
  if [ -d "$JOURNAL_DIR" ]; then
    NOW=$(cat "$JOURNAL_DIR"/*.jsonl 2>/dev/null | grep -c '"event": "COMMITTED"' || true)
    NOW=${NOW:-0}
    while [ "$NOW" -gt "$SEEN" ]; do
      SEEN=$((SEEN+1))
      capture "stage_$SEEN"
    done
  fi
  sleep 1
done
wait $RUN_PID
RUN_RC=$?
echo "baseline rc=$RUN_RC"

capture task_end

# ------------------------------------------------------------ on failure
# The baseline already writes verdict.json and does not re-judge here.
if [ -f "$OUT/verdict.json" ]; then
  if ! python3 -c "import json,sys; sys.exit(0 if json.load(open(sys.argv[1]))['passed'] else 1)" "$OUT/verdict.json"; then
    capture failure
  fi
fi

# ------------------------------------------------------------------ pairing
# Each sidecar carries the truth sampled at capture time, so pairing needs
# no live stack and cannot invent a sample it did not take.
python3 "$PAIR" --frames "$FRAMES" --out "$OUT/visual_vs_truth.json" \
    --max-gap 2.0 --force >> "$OUT/capture.log" 2>&1
PAIR_RC=$?

FRAME_COUNT=$(ls -1 "$FRAMES"/*.png 2>/dev/null | wc -l)
echo "=== capture summary ==="
echo "frames=$FRAME_COUNT failed_captures=$FAILED_CAPTURES pairing_rc=$PAIR_RC baseline_rc=$RUN_RC"
echo EVOBOT_CAPTURE_DONE

# A run that silently produced no frames must not be reported as a run that
# captured them. Either condition is a failure of this script.
if [ "$FAILED_CAPTURES" -gt 0 ]; then exit 4; fi
if [ "$FRAME_COUNT" -eq 0 ]; then echo "NO_FRAMES_CAPTURED"; exit 4; fi
if [ "$PAIR_RC" -ne 0 ]; then exit 5; fi
exit 0
