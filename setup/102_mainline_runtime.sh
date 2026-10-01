#!/usr/bin/env bash
# Switch the owned fleet, or cold-start the owned stack, preserving old logs.
set -euo pipefail
action=${1:-switch}
policy=${2:-hybrid}
threshold=${3:-0.7}
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
runtime=${FLEXCELL_WS:-/home/ros/agentic_workcell_ws}
base=${FLEXCELL_MAINLINE_ROOT:-$HOME/.local/share/flexcell/mainline}
export FLEXCELL_INSTALL=${FLEXCELL_INSTALL:-$base/install}
case "$action" in cold|switch) ;; *) echo 'usage: 102_mainline_runtime.sh cold|switch fsm|jev|llm|hybrid [threshold]' >&2; exit 2;; esac
source "$repo/setup/104_mainline_env.sh"
pids=/tmp/flexcell_lifecycle/pids
logs=$base/runtime/$(date +%Y%m%d_%H%M%S)
mkdir -p "$logs" "$pids"
stop_owned() {
    local name=$1 pid pgid cmd
    [ -f "$pids/$name.pid" ] || return 0
    pid=$(cat "$pids/$name.pid")
    [[ "$pid" =~ ^[0-9]+$ ]] && [ "$pid" -gt 1 ] || { echo 'invalid owned PID'; exit 1; }
    kill -0 "$pid" 2>/dev/null || return 0
    pgid=$(ps -o pgid= -p "$pid" | tr -d ' ')
    cmd=$(ps -o args= -p "$pid")
    [ "$pgid" = "$pid" ] && [[ "$cmd" == *ros2*launch* ]] || { echo "ownership mismatch $name pid=$pid"; exit 1; }
    kill -TERM -- "-$pgid"
    for _ in $(seq 1 30); do kill -0 -- "-$pgid" 2>/dev/null || break; sleep 0.2; done
    if kill -0 -- "-$pgid" 2>/dev/null; then kill -KILL -- "-$pgid"; fi
    echo "STOPPED $name group=$pgid"
}
launch_owned() {
    local name=$1; shift
    setsid nohup "$@" >"$logs/$name.log" 2>&1 </dev/null &
    echo $! >"$pids/$name.pid"
    echo "STARTED $name pid=$! log=$logs/$name.log"
}
if [ -d /tmp/flexcell_lifecycle/logs ]; then cp -a /tmp/flexcell_lifecycle/logs "$logs/previous-stack"; fi
stop_owned fleet
if [ "$action" = cold ]; then
    stop_owned move_to_pose
    stop_owned moveit
    stop_owned gazebo
    timeout 15 ros2 daemon stop >/dev/null 2>&1 || true
    launch_owned gazebo ros2 launch open_manipulator_bringup open_manipulator_x_gazebo.launch.py world:="${FLEXCELL_WORLD:-$repo/worlds/flexcell_world}"
    ready=false
    for _ in $(seq 1 15); do
        if timeout 8 gz model --list 2>/dev/null | grep -q target_box_b; then ready=true; break; fi
        sleep 2
    done
    $ready || { echo 'Gazebo failed to start'; exit 1; }
    launch_owned moveit ros2 launch open_manipulator_moveit_config open_manipulator_x_moveit.launch.py use_sim:=true start_rviz:=false
    launch_owned move_to_pose ros2 launch flexcell_skills move_to_pose.launch.py
fi
fingerprint=$(python3 - "$logs/deployment.json" "$repo" "$policy" "$threshold" "$FLEXCELL_INSTALL" <<'PY'
import hashlib,importlib.util,json,os,pathlib,subprocess,sys
from flexcell_skills.contracts.benchmark_protocol import load_protocol
path,repo,policy,threshold,install=sys.argv[1:]
spec,digest=load_protocol()
profile_path=os.environ.get('FLEXCELL_DDS_PROFILE')
sources={str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest()
         for p in pathlib.Path(repo).glob('src/flexcell/flexcell_skills/flexcell_skills/**/*.py')}
native_sources={str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in pathlib.Path(repo).glob('src/flexcell/flexcell_gazebo/**/*') if p.is_file()}
native_plugin=pathlib.Path(install)/'flexcell_gazebo/lib/libflexcell_carry_dynamics.so'
carry_backend=os.environ.get('FLEXCELL_CARRY_BACKEND','teleport')
installed_root=pathlib.Path(importlib.util.find_spec('flexcell_skills').origin).parent
installed_sources={str(p.relative_to(installed_root)):hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in installed_root.rglob('*.py')}
if carry_backend == 'velocity_servo' and not native_plugin.is_file():
    raise SystemExit('velocity carry plugin is not installed')
profile=dict(policy=policy,threshold=float(threshold),protocol_sha256=digest,
             interface_sources_sha256={str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest()
                                       for p in pathlib.Path(repo).glob('src/flexcell/flexcell_interfaces/**/*') if p.is_file()},
             installed_source_sha256=installed_sources,
             simulation_backend={'carry':carry_backend,'native_sources':native_sources,
                                 'plugin_sha256':hashlib.sha256(native_plugin.read_bytes()).hexdigest() if carry_backend=='velocity_servo' else None},
             params_sha256=hashlib.sha256((pathlib.Path(repo)/'src/flexcell/flexcell_skills/config/week1.yaml').read_bytes()).hexdigest(),
             harness_sha256={name:hashlib.sha256((pathlib.Path(repo)/name).read_bytes()).hexdigest()
                             for name in ('setup/94_scenario_runner.py','setup/flexcell_admin.py','setup/108_wait_policy.py',
                                          'src/flexcell/flexcell_skills/test/w1_client.py')},
             source_sha256=sources,models=json.load(open(pathlib.Path(repo)/'setup/local_inference_assets.json')),
             active_backends={
                 'fast':{'endpoint':os.environ['FLEXCELL_JEV_ENDPOINT'], 'model':os.environ['FLEXCELL_JEV_MODEL']},
                 'slow':{'endpoint':os.environ['FLEXCELL_LLM_ENDPOINT'], 'model':os.environ['FLEXCELL_LLM_MODEL'],
                         'backend':os.environ.get('FLEXCELL_LLM_BACKEND','local-task-reasoner'),
                         'response_format':os.environ.get('FLEXCELL_LLM_RESPONSE_FORMAT','json_schema'),
                         'thinking':os.environ.get('FLEXCELL_LLM_THINKING','backend-default'),
                         'max_tokens':int(os.environ.get('FLEXCELL_LLM_MAX_TOKENS','160')),
                         'budget_limit_cny':5 if os.environ.get('FLEXCELL_LLM_BUDGET_FILE') else None,
                         'credential_configured':bool(os.environ.get('FLEXCELL_LLM_API_KEY_FILE'))}},
             policy_timeouts_s={'fast':2,'slow':float(os.environ.get('FLEXCELL_LLM_TIMEOUT_S','5'))},server_context_tokens=8192,
             ros_domain_id=int(os.environ['ROS_DOMAIN_ID']),
             rmw_implementation=os.environ['RMW_IMPLEMENTATION'],
             world_sha256=hashlib.sha256(pathlib.Path(os.environ.get('FLEXCELL_WORLD',repo+'/worlds/flexcell_world')+'.sdf').read_bytes()).hexdigest(),
             dds_profile_sha256=hashlib.sha256(pathlib.Path(profile_path).read_bytes()).hexdigest() if profile_path else 'builtin')
fingerprint=hashlib.sha256(json.dumps(profile,sort_keys=True).encode()).hexdigest()
json.dump(dict(profile, runtime_fingerprint=fingerprint,install=install,
               head=subprocess.check_output(['git','-C',repo,'rev-parse','HEAD'],text=True).strip()),open(path,'w'),indent=2)
print(fingerprint)
PY
)
export FLEXCELL_RUNTIME_FINGERPRINT=$fingerprint
launch_owned fleet bash "$repo/setup/98_run_policy.sh" "$policy" "$threshold"
timeout 65 python3 "$repo/setup/108_wait_policy.py" "$policy"
echo "DEPLOYED policy=$policy protocol=v2 logs=$logs"
