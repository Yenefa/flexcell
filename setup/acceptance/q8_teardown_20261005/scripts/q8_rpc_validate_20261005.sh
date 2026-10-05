#!/usr/bin/env bash
set -eo pipefail
repo=/home/ros/agentic_workcell_ws
root="$repo/setup/acceptance/q8_teardown_20261005"
source "$repo/setup/104_mainline_env.sh"
case "${1:?action}" in
  test)
    python3 -m pytest -o addopts='' /mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/code-clone/src/flexcell/flexcell_skills/test/test_admin_pose_rpc.py -q --tb=short 2>&1 | tee "$root/test_rpc_contract_${2:?label}.log"
    ;;
  tests)
    python3 -m pytest -o addopts='' "$repo/src/flexcell/flexcell_skills/test" -q --disable-warnings --tb=short 2>&1 | tee "$root/tests_rpc_full.log"
    ;;
  reset)
    mkdir -p "$root/reset_rpc_after"
    python3 /mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/pm-work/q8_reset_probe_20261005.py "$root/reset_rpc_after" 2>&1 | tee "$root/reset_rpc_after/reset20.log"
    ;;
esac
