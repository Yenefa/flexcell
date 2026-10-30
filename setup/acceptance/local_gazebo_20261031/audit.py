"""Post-run, read-only audit of completed local windows and raw physical records."""
import hashlib
import json
import math
from pathlib import Path
import subprocess

root = Path('/home/ros/agentic_workcell_ws/artifacts/local-pr75-20261031')
def load(path): return json.loads(path.read_text())
def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.is_file() else []
core = load(root/'core-window/window.json')
assert core['status'] == 'FUNCTIONAL_WINDOW_PASS', core
assert len(core['episodes']) == 5 and core['no_replacements'] is True
report = {'source_revision':'c2583aec1e507386f5733285fe5399003709b4d0',
          'local_physical_execution': True, 'core_status':core['status'], 'core_cases':[],
          'qualification':'LOCAL_FUNCTIONAL_DIAGNOSTIC_ONLY', 'default_admission':'NO_GO'}
all_places = 0
for episode in core['episodes']:
    run = Path(episode['run'])
    r = load(run/'result.json')
    assert r['expectation_met'] is True and r['physical_tasks_dispatched'] == 1
    assert r['status'] == ('EXPECTED_FAILURE' if episode['case']=='budget_exhaustion' else 'PASS')
    assert r['identity']['mismatches'] == [] if 'identity' in r else True
    health = load(run/'health_after.stdout')
    assert health['ok'] is True and health['hard_fail'] == []
    assert health['checks']['task_state'] == 'IDLE' and health['checks']['carry_engaged'] is False
    traces = rows(run/'data/physics.jsonl')
    selected = [f for f in traces if r['task_start_monotonic_ns'] <= f['monotonic_ns'] <= r['task_end_monotonic_ns']]
    assert len(selected) >= 2
    assert all(a['monotonic_ns'] < b['monotonic_ns'] and a['sim_ns'] < b['sim_ns'] for a,b in zip(selected, selected[1:]))
    last = selected[-1]
    age_ms = (r['task_end_monotonic_ns']-last['monotonic_ns'])/1e6
    assert 0 <= age_ms <= 500
    case = {'case':episode['case'], 'object':episode['object'], 'status':r['status'],
            'run':str(run), 'task':r['task'], 'physics_samples_during_task':len(selected),
            'latest_physics_age_ms':age_ms, 'raw_placement_errors_mm':{}, 'post_health_checks':len(health['checks'])}
    if episode['case'] != 'budget_exhaustion':
        places = rows(run/'skills/place.jsonl')
        successful = [p for p in places if p['outcome']=='0' and p['released'] is True]
        assert len(successful) == (2 if episode['case']=='dual_object' else 1)
        all_places += len(successful)
        if episode['case']=='dual_object':
            import yaml
            params = yaml.safe_load((run/'params.yaml').read_text())['task_fsm_server']['ros__parameters']
            goals = {params['object_a']:[params['zone_1_x'],params['zone_1_y'],params['zone_1_z']],
                     params['object_b']:[params['zone_2_x'],params['zone_2_y'],params['zone_2_z']]}
        else:
            goals = {episode['object']:r['goal_pose']}
        for name, goal in goals.items():
            actual = last['objects'][name]['pose'][:3]
            error = math.dist(actual,goal)
            assert math.isfinite(error) and error < .06
            case['raw_placement_errors_mm'][name] = error*1000
    else:
        assert r['task']['error_code'] == 'ERR_RECOVERY_EXHAUSTED'
    report['core_cases'].append(case)
report['baseline_successful_object_placements'] = all_places
joint = load(root/'joint-window/window.json')
assert joint['status']=='STOPPED' and len(joint['episodes'])==1
entry = joint['episodes'][0]
run = Path(entry['run'])
r = load(run/'result.json')
assert r['physical_tasks_dispatched']==1
pick = rows(run/'skills/pick.jsonl')
place = rows(run/'skills/place.jsonl')
assert len(pick)==1 and pick[0]['outcome']=='0'
assert len(place)==1 and place[0]['outcome']=='1' and place[0]['released'] is False
assert place[0]['mtc_stages']==[]
assert 'hover (0/1)' in place[0]['planning_detail']
assert 'GOAL_STATE_INVALID' in (run/'stack.log').read_text()
assert r['native_identity_verified_before_dispatch'] is True
raw_steps = rows(run/'physics_steps.jsonl')
assert all(b['sim_ns']-a['sim_ns']==2_000_000 for a,b in zip(raw_steps,raw_steps[1:]))
# Preserve startup and teardown. Use the harness's predeclared task-call time
# interval to identify task attachment, instead of joining startup attachment
# samples to a different, later native ownership session.
attached = [f for f in raw_steps if f['objects']['target_box_a']['joint_component']
            and r['task_start_monotonic_ns'] <= f['monotonic_ns'] <= r['task_end_monotonic_ns']]
assert len(attached)>2
assert all(b['sim_ns']-a['sim_ns']==2_000_000 for a,b in zip(attached,attached[1:]))
report['joint_diagnostic'] = {'status':r['status'], 'run':str(run), 'task':r['task'],
 'pick_success':True, 'pick_rise_mm':pick[0]['box_rise_m']*1000,
 'place_failure_stage':'hover', 'moveit_error':'GOAL_STATE_INVALID', 'place_trajectories_dispatched':0,
 'intentional_place_release':False, 'attached_raw_steps':len(attached),
 'attached_raw_duration_s':(attached[-1]['sim_ns']-attached[0]['sim_ns'])/1e9,
 'all_raw_steps':len(raw_steps), 'all_raw_step_gaps':0,
 'pre_task_attached_raw_steps':sum(f['objects']['target_box_a']['joint_component']
    and f['monotonic_ns']<r['task_start_monotonic_ns'] for f in raw_steps),
 'post_task_attached_raw_steps':sum(f['objects']['target_box_a']['joint_component']
    and f['monotonic_ns']>r['task_end_monotonic_ns'] for f in raw_steps),
 'native_identity_verified_before_dispatch':True,
 'exact_causal_attribution':'UNKNOWN; same failure stage as original CI, production adapter unchanged'}
owned = subprocess.run(['pgrep','-af','[g]z sim|[m]ove_group|[m]tc_planner|[c]arry_server'],text=True,capture_output=True)
report['remaining_simulation_processes'] = owned.stdout.strip()
assert owned.returncode==1, owned.stdout
report['files'] = {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in root.rglob('*') if p.is_file() and p.name != 'local-audit.json'}
(root/'local-audit.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='files'},indent=2))
