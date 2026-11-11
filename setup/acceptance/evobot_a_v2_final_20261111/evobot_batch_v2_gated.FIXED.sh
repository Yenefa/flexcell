#!/usr/bin/env bash
# Baseline A v2 measurement: the same 72 instances, measured so that position is not a variable.

# WHY THIS EXISTS
# The first full batch ran T01 x12, T02 x12, ... T06 x12 in order. Pass rate by execution
# quartile came out 100% / 94% / 50% / 0%, so template identity and execution position were
# perfectly confounded and the per-template numbers meant nothing. Set_pose rejections in
# stack.log tracked the verdict exactly, and the same T06 instances pass 3/3 when run first.
#
# WHAT CHANGES, AND NOTHING ELSE
#  1. RANDOMISED ORDER (fixed seed, written to file before the run) -- every template sees the
#     whole range of machine states instead of each template owning one band.
#  2. LOAD GATE before each instance -- wait until 1-min loadavg is back down and no previous
#     stack survives. The loadavg is recorded before and after every instance so the confound is
#     observable afterwards rather than assumed away.
#  3. CLASSIFIER now also treats a broken observation as INVALID_INFRA. The previous classifier
#     only looked for DDS errors, so a 'pose stream is not flowing' stall would have been graded
#     as a robot failure. That was found in the position control, not in this batch.
# The frozen definition is untouched: same plan builder, same evaluator, same runner.

set -u
S=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/ci-public-window/scripts
W=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
OUTROOT=$1
SEED=${2:-20261111}
LOAD_CEIL=${LOAD_CEIL:-3.0}
LOAD_TIMEOUT=${LOAD_TIMEOUT:-900}

mkdir -p "$OUTROOT"
ORDER="$OUTROOT/order.txt"
ROWS="$OUTROOT/rows.tsv"
printf 'instance\tstatus\tdomain\tload_before\tload_after\trc\n' > "$ROWS"

if [ ! -f "$ORDER" ]; then
  ls "$W/benchmark/tasks/train/"*.json | sort > "$OUTROOT/specs_sorted.txt"
  python3 - "$OUTROOT/specs_sorted.txt" "$ORDER" "$SEED" <<'PY'
import random, sys
src, dst, seed = sys.argv[1], sys.argv[2], int(sys.argv[3])
lines = [l.strip() for l in open(src) if l.strip()]
random.Random(seed).shuffle(lines)
open(dst, 'w').write('\n'.join(lines) + '\n')
print('randomised %d specs with seed %d' % (len(lines), seed))
PY
fi

load1() { cut -d' ' -f1 /proc/loadavg; }

# Wait for the machine to be quiet: low loadavg AND no surviving stack from the last instance.
# A timeout is an infrastructure fault, not a robot failure, so it is reported as such.
wait_quiet() {
  local waited=0
  while :; do
    local l; l=$(load1)
    local busy=0
    pgrep -f 'gz sim' >/dev/null 2>&1 && busy=1
    pgrep -f 'ros2 launch' >/dev/null 2>&1 && busy=1
    if [ "$busy" = '0' ] && python3 -c "import sys; sys.exit(0 if float('$l') < float('$LOAD_CEIL') else 1)"; then
      return 0
    fi
    if [ "$waited" -ge "$LOAD_TIMEOUT" ]; then echo "LOAD_GATE_TIMEOUT load=$l"; return 1; fi
    sleep 10; waited=$((waited+10))
  done
}

i=0
while IFS= read -r spec; do
  [ -n "$spec" ] || continue
  i=$((i+1))
  name=$(basename "$spec" .json)
  DOMAIN=$((40 + (i % 100)))
  out="$OUTROOT/$name"
  echo "=== [$i] $name (domain $DOMAIN) ==="
  if ! wait_quiet; then
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$name" INVALID_INFRA "$DOMAIN" "$(load1)" "$(load1)" 99 >> "$ROWS"
    echo "  INVALID_INFRA (load gate timed out)"
    continue
  fi
  # REAP BEFORE THE GATE, NOT INSTEAD OF IT.
  #
  # Killing 'ros2 launch' reparents its children to this shell, where they survive.
  # Measured across this batch: parameter_bridge and robot_state_publisher accumulated
  # one pair per completed instance -- 68 + 68 alive by instance 68 -- and load_after
  # climbed 2.48 -> 19.89. The orphan gate watched only 'flexcell_skills/' and so
  # reported OK throughout. It was telling the truth about a smaller set than it
  # appeared to cover.
  #
  # Only runs when no simulator is up, so a live instance is never touched.
  if [ "$(pgrep -c -f 'gz sim' 2>/dev/null || echo 0)" -eq 0 ]; then
    pkill -9 -f 'parameter_bridge' 2>/dev/null || true
    pkill -9 -f 'robot_state_publisher' 2>/dev/null || true
  fi

  # orphan gate: a node left over from a previous instance will starve this one's carry servo.
  # This is the leak that made pass rate fall with execution position; assert it is gone before
  # spending two minutes on a run that would be invalid.
  if ! bash "$S/evobot_orphan_check.sh" > "$OUTROOT/.orphan_$i.log" 2>&1; then
    echo "  ORPHAN_LEAK before instance $i -- see .orphan_$i.log"
    cat "$OUTROOT/.orphan_$i.log" | sed 's/^/    /'
  fi
  LB=$(load1)
  EVOBOT_ROS_DOMAIN=$DOMAIN bash "$S/evobot_run_b.sh" "$spec" "$out" > "$out.log" 2>&1
  rc=$?
  LA=$(load1)
  if grep -qi 'free participant index\|failed to create domain' "$out/task.out" 2>/dev/null; then
    status=INVALID_INFRA
  elif grep -qi 'pose stream is not flowing' "$out/task.out" "$out/stack.log" 2>/dev/null; then
    status=INVALID_INFRA
  elif python3 -c "import json,sys;g=json.load(open('$out/ground_truth.json'));sys.exit(0 if (g.get('errors') or {}) else 1)" 2>/dev/null; then
    status=INVALID_INFRA
  elif [ -f "$out/verdict.json" ]; then
    status=GRADED
  else
    status=NO_VERDICT
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$name" "$status" "$DOMAIN" "$LB" "$LA" "$rc" | tee -a "$ROWS"
done < "$ORDER"
echo BATCH_RUNS_DONE
echo BASELINE_A_V2_DONE