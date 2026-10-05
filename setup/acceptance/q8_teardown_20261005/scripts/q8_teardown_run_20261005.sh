#!/usr/bin/env bash
set -eo pipefail
repo=/home/ros/agentic_workcell_ws
evidence="$repo/setup/acceptance/q8_teardown_20261005"
mkdir -p "$evidence"
source "$repo/setup/104_mainline_env.sh"
case "${1:?action}" in
  report)
    python3 /mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/pm-work/q8_report_20261005.py "$evidence/summary.json" "$evidence"
    ;;
  readiness)
    python3 /mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/pm-work/q8_probe_20261005.py "$evidence" 2>&1 | tee "$evidence/readiness.log"
    ;;
  tests)
    python3 -m pytest -o addopts='' "$repo/src/flexcell/flexcell_skills/test" -q --disable-warnings --tb=short 2>&1 | tee "$evidence/tests_full.log"
    ;;
  reset)
    python3 /mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/pm-work/q8_reset_probe_20261005.py "$evidence" 2>&1 | tee "$evidence/reset20.log"
    ;;
  regression)
    bash "$repo/setup/32_day2_acceptance.sh" happy_a regression 2>&1 | tee "$evidence/day2_regression.log"
    ;;
  switch)
    bash "$repo/setup/102_mainline_runtime.sh" switch hybrid "${2:?threshold}" 2>&1 | tee "$evidence/switch_${2}_$(date +%H%M%S).log"
    ;;
  health)
    python3 "$repo/setup/flexcell_admin.py" health 2>&1 | tee "$evidence/health_${2:-after}.log"
    cat /proc/sys/kernel/core_pattern
    ;;
  smoke|baseline)
    stage=$1
    threshold=${2:?threshold}
    count=${3:?count}
    deployment=$(find "$HOME/.local/share/flexcell/mainline/runtime" -name deployment.json -printf '%T@ %p\n' | sort -nr | head -1 | cut -d' ' -f2-)
    test -n "$deployment"
    cp "$deployment" "$evidence/deployment_${threshold}_$(date +%H%M%S).json"
    extra=()
    if [ "$stage" = baseline ]; then extra=(--smoke-summary "${4:?smoke summary}"); fi
    PYTHONUNBUFFERED=1 python3 "$repo/setup/94_scenario_runner.py" --policy hybrid --batch "S1:${count}" \
      --stage "$stage" --deployment "$deployment" "${extra[@]}" 2>&1 | tee "$evidence/${stage}_${threshold}_${count}_$(date +%H%M%S).log"
    ;;
  test)
    python3 -m pytest -o addopts='' /mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/code-clone/src/flexcell/flexcell_skills/test/test_pose_worker_shutdown.py -q --tb=short 2>&1 | tee "$evidence/test_${2:?label}.log"
    ;;
  capture)
    ulimit -c unlimited
    cat /proc/sys/kernel/core_pattern
    ulimit -a
    python3 /mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/pm-work/q8_teardown_probe_20261005.py "$evidence/${2:-before2}.json" --count 200 2>&1 | tee "$evidence/${2:-before2}.log"
    ;;
  probe)
    python3 /mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/pm-work/q8_teardown_probe_20261005.py "$evidence/${2:?label}.json" --count "${3:-100}" --hold "${4:-.5}" 2>&1 | tee "$evidence/${2}.log"
    ;;
  *) exit 64 ;;
esac
