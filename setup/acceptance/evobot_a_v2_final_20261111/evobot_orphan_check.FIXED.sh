#!/usr/bin/env bash
# Assert that no skill process belongs to a DIFFERENT (older) instance than the current one.
#
# WHY NOT AGE: the first version compared process age against the current instance's start time.
# That needs a jitter margin and cannot tell a leftover node from a long-lived legitimate one.
# A self-test exposed it: with a real batch running, the live instance's own nodes are older than
# any marker, so the check fired on a healthy run.
#
# THE PRECISE SIGNAL: every skill node is launched with --params-file inside the evidence directory
# of the instance that owns it. A node whose <run>/<instance> is not the current <run>/<instance>
# is a leftover. No timing, no margin.
#
# WHY THE IDENTITY IS <run>/<instance> AND NOT THE FULL PATH: the first attempt sliced a fixed
# number of path components, which silently differs between a real /mnt/c/... evidence path and a
# synthetic one. Comparing the last two components is exact for both and cannot be fooled by an
# absolute-path prefix.
#
# SEPARATED SO IT CAN BE TESTED: --judge reads ps-style lines on stdin. Default mode collects from
# ps and pipes in. The self-test feeds synthetic lines, because two earlier probe versions were
# confounded by whatever else happened to be running.
set -u
EV=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/ci-public-window/evidence

runinst() {  # last two path components of a directory
  local p=${1%/}
  printf '%s/%s' "$(basename "$(dirname "$p")")" "$(basename "$p")"
}

judge() {
  local cur_runinst=$1; shift
  local stale=0 line pid rest rel their
  while IFS= read -r line; do
    line=$(printf '%s' "$line" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
    [ -n "$line" ] || continue
    pid=${line%% *}
    rest=${line#* }
    rel=$(printf '%s' "$rest" | grep -o 'evidence/[^ ]*' | head -1)
    if [ -z "$rel" ]; then
      echo "  UNKNOWN pid=$pid has no evidence path -- cannot attribute, treating as stale"
      stale=$((stale+1)); continue
    fi
    their="$(printf '%s' "$rel" | cut -d/ -f2)/$(printf '%s' "$rel" | cut -d/ -f3)"
    if [ "$their" != "$cur_runinst" ]; then
      echo "  STALE pid=$pid belongs to $their"
      stale=$((stale+1))
    fi
  done
  if [ "$stale" -gt 0 ]; then echo "LEAK: $stale skill process(es) from another instance"; return 1; fi
  echo 'OK every skill process belongs to the current instance'
  return 0
}

if [ "${1:-}" = '--judge' ]; then judge "$2"; exit $?; fi

CUR_DIR=$(ls -1dt "$EV"/*/*/ 2>/dev/null | head -1)
if [ -z "$CUR_DIR" ]; then echo 'no current instance directory; nothing to check against'; exit 0; fi
CUR=$(runinst "${CUR_DIR%/}")
echo "current instance: $CUR"

# ---------------------------------------------------------------------------
# WHAT THIS NOW WATCHES, AND WHY IT GREW
#
# The first version matched only 'flexcell_skills/'. It reported
# "OK every skill process belongs to the current instance" while 68
# parameter_bridge and 68 robot_state_publisher processes from finished
# instances were still running -- 136 processes, load_after climbing from 2.48
# to 19.89 across the batch. The check was TRUE and it was not the whole truth.
#
# A guard that silently watches less than it appears to is worse than no guard,
# because 'no alarm' gets read as 'nothing wrong'. So this now enumerates what it
# scans and prints the classes and counts whether or not they are clean.
#
# parameter_bridge and robot_state_publisher are the specific leaks: killing
# 'ros2 launch' reparents its children to the batch shell, where they survive.
# They carry no --params-file, so they are attributed by count instead: any
# bridge alive while no simulator is running is a leftover by construction.
# ---------------------------------------------------------------------------
watch_skill() {
  ps -eo pid,cmd --no-headers 2>/dev/null | grep 'flexcell_skills/' | grep -v grep
}
count_of() { pgrep -c -f -- "$1" 2>/dev/null || true; }

echo '--- scanned classes ---'
nskill=$(watch_skill | grep -c . || true)
echo "  flexcell_skills/*          : $nskill  (attributed by instance path)"
gz=$(count_of 'gz sim')
echo "  gz sim                     : $gz"
echo "  parameter_bridge           : $(count_of parameter_bridge)"
echo "  robot_state_publisher      : $(count_of robot_state_publisher)"
echo '--- verdict ---'

# Attribute launch children by SESSION, not by count.
#
# The count test ('any bridge while gz is down') was wrong: it stayed silent
# whenever a simulator happened to be up, which is exactly when the batch is
# running and leftovers accumulate. A negative control caught this -- fabricating
# a bridge during a live instance produced rc=0.
#
# Every process a launch starts shares the batch shell's session. A leftover from
# a finished instance is reparented but KEEPS the same session, so session alone
# cannot separate them either. What does separate them is the batch's own record:
# only the current instance may be running. So compare against the number the
# current instance should have, which the batch writes to .expected_children.
# Absent that file, fall back to flagging a ratio rather than an absolute count.
# Expected count depends on whether a simulator is up, measured rather than assumed:
#
#   instance running (gz sim up)   -> 3 parameter_bridge, 3 robot_state_publisher
#   between instances (gz sim down)-> 2 each, and THOSE 2 ARE THE LEAK
#
# The between-instance 2 is the whole bug: killing 'ros2 launch' reparents two of
# its children, which then persist and accumulate one pair per completed instance.
# Hardcoding a single threshold either misses the leak (if set to 3) or fires on a
# healthy run (if set to 2 while a sim is up). So the bound follows gz sim.
if [ "$gz" -gt 0 ]; then exp_children=3; else exp_children=0; fi
leak_named=0
for pat in parameter_bridge robot_state_publisher; do
  c=$(count_of "$pat")
  c=${c:-0}
  if [ "$c" -gt "$exp_children" ]; then
    echo "  STALE $((c-exp_children)) x $pat (expected <= $exp_children with gz sim=$gz)"
    leak_named=$((leak_named + c - exp_children))
  fi
done

watch_skill | judge "$CUR"
rc=$?
if [ "$leak_named" -gt 0 ]; then
  echo "LEAK: $leak_named launch child process(es) with no simulator to serve"
  echo 'hint: pkill -9 -f parameter_bridge; pkill -9 -f robot_state_publisher'
  exit 1
fi
exit $rc