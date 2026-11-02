"""Read-only post-run checks. Keep failed windows and every raw frame."""
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

root = Path('/home/ros/agentic_workcell_ws/artifacts/joint-point-runtime-20261031')
repo = Path('/home/ros/agentic_workcell_ws')
sys.path.insert(0, str(repo/'scripts'))
def load(path): return json.loads(path.read_text())
def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.is_file() else []

identity = load(root/'identity-before.json')
report = dict(source_revision=identity['source_revision'], local_physical_execution=True,
              qualification='LOCAL_FUNCTIONAL_VALIDATION_ONLY', default_admission='NO_GO', core_cases=[])
core = load(root/'core-window/window.json')
assert core['status']=='FUNCTIONAL_WINDOW_PASS' and len(core['episodes'])==5 and core['no_replacements']
report.update(core_status=core['status'], core_window_id=core['window_id'])
for episode in core['episodes']:
    run = Path(episode['run'])
    result = load(run/'result.json')
    expected = 'EXPECTED_FAILURE' if episode['case']=='budget_exhaustion' else 'PASS'
    assert result['status']==expected and result['expectation_met'] and result['physical_tasks_dispatched']==1
    health = load(run/'health_after.stdout')
    assert health['ok'] and health['hard_fail']==[] and health['checks']['task_state']=='IDLE'
    assert health['checks']['carry_engaged'] is False
    frames = [r for r in rows(run/'data/physics.jsonl') if
              result['task_start_monotonic_ns'] <= r['monotonic_ns'] <= result['task_end_monotonic_ns']]
    assert len(frames)>2 and all(b['sim_ns']>a['sim_ns'] for a,b in zip(frames,frames[1:]))
    age = (result['task_end_monotonic_ns']-frames[-1]['monotonic_ns'])/1e6
    assert 0<=age<=500
    item = dict(case=episode['case'], run=str(run), status=expected, task=result['task'],
                raw_placement_errors_mm={}, post_health_checks=len(health['checks']), latest_physics_age_ms=age)
    if expected=='PASS':
        placements = rows(run/'skills/place.jsonl')
        assert len(placements)==(2 if episode['case']=='dual_object' else 1)
        assert all(p['outcome']=='0' and p['released'] for p in placements)
        goals = {episode['object']:result['goal_pose']}
        if episode['case']=='dual_object':
            import yaml
            params = yaml.safe_load((run/'params.yaml').read_text())['task_fsm_server']['ros__parameters']
            goals = {params['object_a']:[params[f'zone_1_{axis}'] for axis in 'xyz'],
                     params['object_b']:[params[f'zone_2_{axis}'] for axis in 'xyz']}
        for name, goal in goals.items():
            error = math.dist(frames[-1]['objects'][name]['pose'][:3],goal)
            assert math.isfinite(error) and error<.06
            item['raw_placement_errors_mm'][name]=error*1000
    else:
        picks=rows(run/'skills/pick.jsonl')
        assert result['task']['error_code']=='ERR_RECOVERY_EXHAUSTED'
        assert sum(p.get('injected') is True for p in picks)==2
    report['core_cases'].append(item)

joint = load(root/'joint-window/window.json')
assert len(joint['episodes'])==1 and joint['no_replacements']
entry=joint['episodes'][0]
run=Path(entry['run'])
result=load(run/'result.json')
assert result['physical_tasks_dispatched']==1 and result['native_identity_verified_before_dispatch'] is True
raw=rows(run/'physics_steps.jsonl')
assert all(b['sim_ns']-a['sim_ns']==2_000_000 and b['monotonic_ns']>a['monotonic_ns'] for a,b in zip(raw,raw[1:]))
report['joint'] = dict(window_id=joint['window_id'], window_status=joint['status'], run=str(run),
                       status=result['status'], task=result.get('task'), error=joint.get('error'),
                       pick=rows(run/'skills/pick.jsonl'), place=rows(run/'skills/place.jsonl'),
                       all_raw_steps=len(raw), all_raw_step_gaps=0)
if joint['status']=='FUNCTIONAL_WINDOW_PASS':
    from joint_follow_gate import verify_run as follow
    from integrated_contact_gate import verify_run as contact
    from planner_snapshot_gate import verify_run as planner
    report['joint']['follow']=follow(run,'target_box_a',min_duration_s=10.,physics_step_ns=2_000_000)
    report['joint']['contact']=contact(run,'target_box_a',load(root/'joint-window/declaration.json'))
    report['joint']['planner']=planner(run,'target_box_a')
    health=load(run/'health_after.stdout')
    assert health['ok'] and not health['hard_fail'] and health['checks']['task_state']=='IDLE'
    assert health['checks']['carry_engaged'] is False
    report['joint']['post_health_checks']=len(health['checks'])
    task_frames=[r for r in raw if result['task_start_monotonic_ns']<=r['monotonic_ns']<=result['task_end_monotonic_ns']]
    report['joint']['raw_final_error_mm']=math.dist(task_frames[-1]['objects']['target_box_a']['pose'][:3],result['goal_pose'])*1000
    assert report['joint']['raw_final_error_mm']<60.
owned=subprocess.run(['pgrep','-af','[r]ecord_sim_data|[r]os2 bag record|[p]ick_server|[p]lace_server|[t]ask_fsm_server|[g]z sim|[m]ove_group|[m]tc_planner|[c]arry_server'],text=True,capture_output=True)
assert owned.returncode==1,owned.stdout
report['remaining_runtime_processes']=0
report['files']={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in root.rglob('*') if p.is_file() and p.name!='local-audit.json'}
(root/'local-audit.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='files'},indent=2))
