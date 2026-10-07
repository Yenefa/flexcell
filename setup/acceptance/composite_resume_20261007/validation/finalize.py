from pathlib import Path
import hashlib,json,shutil,time
ws=Path('/home/ros/agentic_workcell_ws');root=ws/'setup/acceptance/composite_resume_20261007';logs=Path('/home/ros/fc_sync_logs/composite_resume_20261007')
summary=json.loads((root/'execution_summary.json').read_text());audit=json.loads((root/'execution/composite/audit.json').read_text())
routes=audit['routing'];source=summary['source_result'];report=dict(record_kind='BOUNDED_SIMULATION_RESUME_PILOT',ok=audit['ok'] and source['outcome']=='SUCCEEDED',runtime_fingerprint=audit['runtime_fingerprint'],logical_composite_attempts=1,paused_action_attempts=1,resume_action_attempts=1,duplicate_guard_attempts=1,source_regression_attempts=1,total_native_episodes=4,no_replayed_stage=True,duplicate_dispatch=False,target_routing={k:sum(r[k] for r in routes) for k in ['fast_selected','slow_selected','fast_calls','fast_tokens']},source_routing=source.get('audit'),n_ge_50='FROZEN',AC90='NOT_RUN',physical_safety='NOT_RUN',mid_motion_crash_recovery='NOT_ACCEPTED',network_stability='NOT_ACCEPTED',gpu_fees='UNKNOWN',human_minutes='NOT_RUN',assistant_tokens_fees='NOT_RUN',test_count=330,skills_tests='PASS',interface_skills_build='PASS',no_failure_replacement=True,initial_switch_failure='RETAINED; simulation dependencies absent; no native dispatch',test_fixture_failures='RETAINED; double-coordinate representation and synthetic STARTED hook corrected')
import sys
sys.path.insert(0,str(ws/'setup/transferbench'))
import t1_pilot as base
from adjudicate_t1 import latency
native=[json.loads(p.read_text()) for p in (root/'execution/composite/episodes').glob('*.json')]
source_ep=json.loads((root/'execution/S1/episode.json').read_text());client=json.loads((root/'execution/S1/client.json').read_text())
assert len(native)==3 and len({e['run_id'] for e in native+[source_ep]})==4
assert base.success_predicate(source_ep,base.result_from_output(client['stdout']),client['return_code'])
for e in native+[source_ep]:assert e['runtime_fingerprint']==audit['runtime_fingerprint']
controllers=[];unknown=[]
for folder in [root/'execution/composite/raw',root/'execution/S1/raw']:
 for p in folder.glob('*transport.jsonl'):
  for line in p.read_text().splitlines():
   row=base.COST.decode(line);event=row.get('event','')
   if event=='controller_goal_terminal':controllers.append(row['status'])
   if 'quarantin' in event or event in ('goal_send_timeout','goal_response_unknown','goal_response_error'):unknown.append(row)
assert len(controllers)==30 and set(controllers)=={4} and not unknown
for phase in ['pause','resume']:
 c=json.loads((root/'execution/composite'/(phase+'.json')).read_text());assert c['return_code']==0
added=deleted=0
for line in (logs/'code_numstat.txt').read_text().splitlines():
 a,d,rel=line.split('\t',2)
 if not rel.endswith('.md'):added+=int(a);deleted+=int(d)
change=dict(record_kind='GIT_SOURCE_CHANGE_SNAPSHOT',base_revision='d14c7954049a2eeb799f18e76afe29b706cf992b',target_revision='6624bb7b60bf2895593da5083f2153214afcec9d',code_added=added,code_deleted=deleted,config_added=0,config_deleted=0,rules_added=None,states_added=None,scope='Implementation, interfaces, CLI, auditor and tests; receipt-local instrumentation additional and incompletely measured')
base.write(root/'validation/source_change.json',change)
base.COST.append(root/'cost.jsonl',dict(event_id='shared-composite-resume-source-snapshot',kind='change_snapshot',arm='hybrid',**{k:change[k] for k in ['base_revision','target_revision','code_added','code_deleted','config_added','config_deleted','rules_added','states_added']},evidence=[base.COST.pin(root/'validation/source_change.json')]))
ledger=base.COST.read_ledger(root/'cost.jsonl');trials=[r['payload'] for r in ledger[1:] if r['payload']['kind']=='trial']
assert len(trials)==4 and {r['trial_id'] for r in trials}=={e['run_id'] for e in native+[source_ep]}
report.update(controller_goal_terminals=30,controller_statuses=[4],unknown_transport_events=0,policy_decide_latency=dict(target=latency(native),source=latency([source_ep])),costs=base.COST.summarize(ledger),source_change=change,instrument_tests=42,instrument_test_result='PASS from authority; initial worktree-path binding failure retained')
(root/'validation/final_report.json').write_text(json.dumps(report,indent=2)+'\n')
interval=json.loads((logs/'partial_agent_interval.json').read_text());interval['end_perf_counter_ns']=time.perf_counter_ns();interval['elapsed_minutes']=(interval['end_perf_counter_ns']-interval['start_perf_counter_ns'])/60e9;interval['scope']='Partial wall interval includes build, tests and waiting; not complete engineering labor.';(root/'validation/partial_agent_interval.json').write_text(json.dumps(interval,indent=2)+'\n')
for p in logs.iterdir():
 if p.is_file() and p.suffix in ['.log','.json','.sh','.py']:shutil.copy2(p,root/'validation'/p.name)
# Copy the measured interval after originals, preserving its completed form.
(root/'validation/partial_agent_interval.json').write_text(json.dumps(interval,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False))
