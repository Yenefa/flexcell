#!/usr/bin/env bash
set -eo pipefail
repo=/home/ros/agentic_workcell_ws
evidence="$repo/setup/acceptance/q8_teardown_20261005"
scripts=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/pm-work
source "$repo/setup/104_mainline_env.sh"
case "${1:?action}" in
  probe)
    test ! -e "$evidence/final_readiness"
    mkdir "$evidence/final_readiness"
    python3 "$scripts/q8_probe_20261005.py" "$evidence/final_readiness" 2>&1 | tee "$evidence/final_readiness/probe.log"
    ;;
  freeze)
    python3 "$scripts/q8_teardown_freeze_20261005.py"
    ;;
  verify)
    python3 "$scripts/q8_teardown_verify_final_20261005.py"
    ;;
  align)
    python3 "$scripts/q8_teardown_align_final_20261005.py" "${2:?commit}"
    ;;
  *) exit 64 ;;
esac
