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
ps -eo pid,cmd --no-headers 2>/dev/null | grep 'flexcell_skills/' | grep -v grep | judge "$CUR"
exit $?
