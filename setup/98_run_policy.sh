#!/usr/bin/env bash
# Start the skill fleet with an explicit decision arm and threshold.
# Run with the existing fleet stopped; Gazebo/MoveIt stay running.
set -euo pipefail
policy="${1:-fsm}"
threshold="${2:-0.7}"
case "$policy" in fsm|jev|llm|hybrid) ;; *) echo 'usage: 98_run_policy.sh fsm|jev|llm|hybrid [threshold]' >&2; exit 2 ;; esac
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
runtime="${FLEXCELL_WS:-/home/ros/agentic_workcell_ws}"
install="${FLEXCELL_INSTALL:-$runtime/install}"
set +u
source /opt/ros/jazzy/setup.bash
source "$runtime/install/setup.bash"
source "$install/setup.bash"
set -u
params=$(mktemp /tmp/flexcell-policy-XXXXXX.yaml)
python3 - "$repo/src/flexcell/flexcell_skills/config/week1.yaml" "$params" "$policy" "$threshold" <<'PY'
import math
import os
import sys
import yaml
src, dst, policy, threshold = sys.argv[1:]
threshold = float(threshold)
if not math.isfinite(threshold) or not 0 <= threshold <= 1:
    raise SystemExit('threshold must be finite and in [0,1]')
with open(src) as stream:
    config = yaml.safe_load(stream)
config['task_fsm_server']['ros__parameters'].update(
    decision_policy=policy, hybrid_threshold=threshold)
backend = os.environ.get('FLEXCELL_CARRY_BACKEND', 'teleport')
if backend not in ('teleport', 'velocity_servo'):
    raise SystemExit('unsupported carry backend')
config['carry_server']['ros__parameters']['carry_backend'] = backend
config['pick_server']['ros__parameters']['carry_backend'] = backend
with open(dst, 'w') as stream:
    yaml.safe_dump(config, stream, sort_keys=False)
PY
exec ros2 launch flexcell_skills week1.launch.py params_file:="$params"
