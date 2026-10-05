#!/usr/bin/env bash
set -eo pipefail
repo=/home/ros/agentic_workcell_ws
evidence="$repo/setup/acceptance/q8_pilot_20261005"
mkdir -p "$evidence"
source "$repo/setup/104_mainline_env.sh"
case "${1:-}" in
  tests)
    python3 -m pytest -o addopts='' "$repo/src/flexcell/flexcell_skills/test" -q --disable-warnings --tb=short 2>&1 | tee "$evidence/unit_tests_final.log"
    ;;
  report)
    python3 /mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/pm-work/q8_report_20261005.py "$evidence/summary.json"
    ;;
  regression)
    cases=(regression)
    if [ "${2:-}" = validated ]; then cases=(happy_a regression); fi
    bash "$repo/setup/32_day2_acceptance.sh" "${cases[@]}" 2>&1 | tee "$evidence/day2_regression_$(date +%H%M%S).log"
    ;;
  worker-probe)
    python3 /mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/pm-work/q8_worker_probe_20261005.py "$evidence/worker_probe.json" 2>&1 | tee "$evidence/worker_probe.log"
    ;;
  gate-test)
    python3 -m pytest -o addopts='' /mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/code-clone/src/flexcell/flexcell_skills/test/test_acceptance_gate.py -q --tb=short 2>&1 | tee "$evidence/acceptance_gate_${2:-test}.log"
    ;;
  calibrate)
    python3 "$repo/setup/119_policy_eval.py" calibrate --backend clef \
      --episodes "$repo/setup/acceptance/hardening_20261002/recorded_inputs" \
      --out "$evidence/calibration.json" 2>&1 | tee "$evidence/calibration.log"
    ;;
  probe)
    python3 /mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/pm-work/q8_probe_20261005.py "$evidence" 2>&1 | tee "$evidence/probe.log"
    ;;
  start)
    bash "$repo/setup/102_mainline_runtime.sh" cold hybrid "${2:?threshold}" 2>&1 | tee "$evidence/start_${2}.log"
    ;;
  switch)
    bash "$repo/setup/102_mainline_runtime.sh" switch hybrid "${2:?threshold}" 2>&1 | tee "$evidence/switch_${2}.log"
    ;;
  health)
    python3 "$repo/setup/flexcell_admin.py" health 2>&1 | tee "$evidence/health_${2:-initial}.log"
    ;;
  smoke|baseline)
    stage=$1
    threshold=${2:?threshold}
    count=${3:?count}
    deployment=$(find "$HOME/.local/share/flexcell/mainline/runtime" -name deployment.json -printf '%T@ %p\n' | sort -nr | head -1 | cut -d' ' -f2-)
    test -n "$deployment"
    cp "$deployment" "$evidence/deployment_${threshold}.json"
    extra=()
    if [ "$stage" = baseline ]; then extra=(--smoke-summary "${4:?smoke summary}"); fi
    PYTHONUNBUFFERED=1 python3 "$repo/setup/94_scenario_runner.py" --policy hybrid --batch "S1:${count}" \
      --stage "$stage" --deployment "$deployment" "${extra[@]}" 2>&1 | tee "$evidence/${stage}_${threshold}_${count}_$(date +%H%M%S).log"
    ;;
  *) echo 'usage: tests|calibrate|probe|start tau|switch tau|health label|smoke tau n|baseline tau n summary' >&2; exit 64 ;;
esac
