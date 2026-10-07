"""Seal a separate FSM evidence snapshot while keeping the live journal parked."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys

WS=Path('/home/ros/agentic_workcell_ws')
ROOT=WS/'setup/acceptance/local_fsm_20261008'
LOG=Path('/home/ros/fc_sync_logs/local_fsm_20261007')
ACTIVE=Path('/home/ros/fc_sync_logs/local_fsm_active_20261008/run')
sys.path.insert(0,str(WS/'setup/transferbench'))
import bounded_runner as engine
import qualification_prepare as q
import t1_pilot as base
from adjudicate_t1 import latency

state=engine.status(ACTIVE,WS)
plan,rows,_,committed,ids=engine.read(ACTIVE,WS)
q.require(state['state']=='PAUSED' and state['completed_slots']==3
    and state['native_episode_count']==5 and state['native_dispatch_quota_used']==5
    and state['outcomes']==['SUCCEEDED']*3,'only actual successful local prefix may use this producer')
q.require([row['slot'] for row in rows if row['event']=='CLAIMED']==[0,1,2],
    'hybrid claimed or local slot repeated')
q.require((ROOT/'snapshot/registered_plan.json').read_bytes()==(ACTIVE/'plan.json').read_bytes()
    and (ROOT/'snapshot/registered_events.jsonl').read_bytes()==(ACTIVE/'events.jsonl').read_bytes(),
    'immutable snapshot differs from paused journal')
q.require(q.sha(Path(plan['budget_path']))==plan['registration_budget']['source_sha256'],
    'budget changed; do not call this a model-free receipt')
current=q.history_snapshot(Path(plan['history_path']))['files']
for rel,pin in plan['history_files'].items():
    q.require(q.same_typed(current[rel],pin),'prior episode changed')
post=q.loads((ROOT/'validation/readiness_postflight_report.json').read_bytes())
q.require(post['read_only_preflight_ok'] is True
    and post['checks']['live_readonly']['active_policy']=='fsm'
    and post['checks']['live_readonly']['model_routes_required'] is False,
    'postflight does not confirm actual local policy')
tasks,all_episodes,new_names,decisions,terminals=[],[],set(),[],[]
for job in plan['jobs'][:3]:
    folder=ROOT/'execution'/job['slot_id']
    result=q.loads((folder/'result.json').read_bytes())
    engine.verify_attempt(folder,next(row['artifact_sha256'] for row in committed if row['slot']==job['slot']))
    q.require(result['outcome']=='SUCCEEDED' and type(result['client_return_code']) is int
        and result['client_return_code']==0,'client process failed or signaled')
    client=q.loads((folder/'client_result.json').read_bytes())
    q.require(type(client['action_status']) is int and client['action_status']==4
        and type(client['outcome_val']) is int and client['outcome_val']==0,'typed native terminal required')
    episodes=[]
    for path in sorted((folder/'episodes').glob('*.json')):
        ep=q.loads(path.read_bytes())
        q.require(ep['policy']['name']=='fsm'
            and ep['runtime_fingerprint']==result['runtime_fingerprint'],'model or fingerprint mixed')
        q.require(current[path.name]['sha256']==q.sha(path),'persisted episode differs from copied evidence')
        q.require(not any((step['policy_output'].get('policy_trace') or {}).get('proposals')
            for step in ep['steps']),'model proposals in FSM-only receipt')
        new_names.add(path.name);episodes.append(ep)
    q.require(len(episodes)==job['native_episode_limit'],'missing native components')
    for path in (folder/'raw').glob('*.jsonl'):
        for line in path.read_text().splitlines():
            if not line.strip():continue
            event=q.loads(line)
            if path.name=='decisions.jsonl':
                q.require(event['policy']=='fsm' and event['run_id'] in ids,'foreign or model decision')
                decisions.append(event)
            if 'transport' in path.name:
                q.require('quarantin' not in str(event.get('event',''))
                    and event.get('event') not in ('goal_send_timeout','goal_response_unknown','goal_response_error'),
                    'unconfirmed transport ownership')
                if event.get('event')=='controller_goal_terminal':
                    q.require(type(event['status']) is int and event['status']==4,'controller failed or canceled')
                    terminals.append(event)
    metric=latency(episodes)
    if any(step.get('decide_latency_ms')==0 for ep in episodes for step in ep['steps']
           if step['policy_input'].get('world_state_canonical') is not None):
        metric=dict(status='NOT_RUN',reason='zero measurement cannot establish fractional latency')
    tasks.append(dict(axis=job['axis'],case_id=job['case_id'],arm='fsm',outcome=result['outcome'],
        native_episode_ids=result['native_episode_ids'],native_episode_count=len(episodes),
        client_return_code=result['client_return_code'],action_status=client['action_status'],
        outcome_val=client['outcome_val'],decision_latency=metric))
    all_episodes.extend(episodes)
q.require(set(current)-set(plan['history_files'])==new_names
    and {e['run_id'] for e in all_episodes}==set(ids),'new history not exactly owned five episodes')
q.require(decisions and terminals,'actual decision/controller evidence required')
first=q.loads((ROOT/'validation/first_fsm_status.json').read_bytes())
q.require(first['state']=='PAUSED' and first['completed_slots']==1,'live pause boundary not recorded')
q.require((ROOT/'validation/local_final_status.json').is_file(),'independent resume driver not recorded')
code=q.loads((LOG/'code_commit.json').read_bytes())
for name in ['code_commit.json','owned_files.json','tests_targeted_attempt01.log','tests_all_attempt01.log',
             'prettier_source_attempt01.log','prettier_evidence_attempt01.log','run_local.sh','postflight.sh']:
    target=ROOT/'validation'/name
    q.require(not target.exists(),'validation already exists')
    shutil.copy2(LOG/name,target)
q.require('44 passed' in (ROOT/'validation/tests_targeted_attempt01.log').read_text()
    and '121 passed' in (ROOT/'validation/tests_all_attempt01.log').read_text(),'actual test logs required')
git=['/mnt/c/Program Files/Git/cmd/git.exe','-C','C:/dev/flexcell']
for rel in code['files']:
    raw=subprocess.check_output(git+['show',code['head']+':'+rel])
    if not rel.startswith('docs/'):
        q.require((WS/rel).read_bytes()==raw,'executed code differs from commit')
    target=ROOT/'source'/rel;target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as stream:stream.write(raw)
report=dict(record_kind='LOCAL_FSM_DEVELOPMENT_PREFIX',implementation_revision=code['head'],
    actual_runtime_fingerprint=all_episodes[0]['runtime_fingerprint'],arm='fsm',
    local_prefix_processed=True,local_prefix_all_succeeded=True,logical_tasks=3,native_episodes=5,
    tasks=tasks,policy_decisions=len(decisions),inference_calls=0,new_budget_reservations=0,
    persistent_budget_unchanged=True,previous_history_files=len(plan['history_files']),
    previous_history_unchanged=True,current_history_files=len(current),
    controller_goal_terminals=len(terminals),controller_terminal_statuses=[4],unknown_transport_events=0,
    live_pause_resume='MEASURED_COMMITTED_BOUNDARY',postflight_read_only_ok=True,
    collector_status=state,collector_active_root=str(ACTIVE),collector_snapshot_separate=True,
    remaining_logical_tasks=3,remaining_native_episode_cap=5,full_six_slot_development_complete=False,
    qualification_sampling_authorized=False,ready_for_large_test=False,n_ge_50='FROZEN',AC90='NOT_RUN',
    public_development_exposure=['T1-001','T3-001'],independent_holdout='NOT_ESTABLISHED',
    B_grasp_root_cause='UNKNOWN',network_stability='NOT_ACCEPTED',gpu_and_actual_api_fees='UNKNOWN',
    tests={'targeted':44,'all_offline_instruments':121},no_failure_replacement=True,
    partial_wall_time_is_complete_labor=False,sealed_utc=datetime.now(timezone.utc).isoformat())
engine.write(ROOT/'report.json',report)
manifest={str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=q.sha(p))
    for p in sorted(ROOT.rglob('*')) if p.is_file() and p!=ROOT/'SHA256SUMS.json'}
engine.write(ROOT/'SHA256SUMS.json',manifest)
for rel,pin in manifest.items():
    path=q.regular(ROOT,rel)
    q.require(q.sha(path)==pin['sha256'] and path.stat().st_size==pin['bytes'],'seal mismatch')
print(json.dumps({k:report[k] for k in ['local_prefix_all_succeeded','logical_tasks','native_episodes',
    'policy_decisions','inference_calls','controller_goal_terminals','remaining_logical_tasks','n_ge_50']}))
