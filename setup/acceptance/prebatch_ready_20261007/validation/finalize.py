from pathlib import Path
import json,sys,time,hashlib,shutil,subprocess
WS=Path('/home/ros/agentic_workcell_ws');ROOT=WS/'setup/acceptance/prebatch_ready_20261007';LOG=Path('/home/ros/fc_sync_logs/prebatch_ready_20261007')
sys.path.insert(0,str(WS/'setup/transferbench'));sys.path.insert(0,str(WS/'src/flexcell/flexcell_skills'))
import t1_pilot as base
from adjudicate_t1 import latency
from flexcell_skills.contracts.routing_audit import audit_routing_episode
summary=json.loads((ROOT/'execution_summary.json').read_text());deployment=json.loads((ROOT/'plan/deployment.json').read_text());audit=json.loads((ROOT/'execution/composite/audit.json').read_text());correction=json.loads((ROOT/'validation/control_audit_v2.json').read_text())
native=[json.loads(p.read_text()) for p in (ROOT/'execution/composite/episodes').glob('*.json')];source=json.loads((ROOT/'execution/S1/episode.json').read_text());source_client=json.loads((ROOT/'execution/S1/client.json').read_text())
assert len(native)==1 and len({e['run_id'] for e in native+[source]})==2
assert audit['ok'] and base.success_predicate(source,base.result_from_output(source_client['stdout']),source_client['return_code'])
assert source_client['return_code']==0 and json.loads((ROOT/'execution/composite/client.json').read_text())['return_code']==0
assert all(e['runtime_fingerprint']==deployment['runtime_fingerprint'] for e in native+[source])
assert correction['guard_condition_confirmed'] and correction['zero_dispatch'] and correction['no_resubmission']
control=json.loads((ROOT/'execution/invalid-chain-control/client_result.json').read_text());assert control['outcome_val']==1 and control['action_status']==6 and control['error_code_val']==60
assert len([p for p in (ROOT/'execution/invalid-chain-control/raw').glob('*.jsonl') if p.stat().st_size])==0
statuses=[];unknown=[]
for folder in [ROOT/'execution/composite/raw',ROOT/'execution/S1/raw']:
 for p in folder.glob('*transport.jsonl'):
  for s in p.read_text().splitlines():
   r=base.COST.decode(s);event=r.get('event','')
   if event=='controller_goal_terminal':statuses.append(r['status'])
   if 'quarantin' in event or event in ('goal_send_timeout','goal_response_unknown','goal_response_error'):unknown.append(r)
assert len(statuses)==18 and set(statuses)=={4} and not unknown
post=json.loads((LOG/'readiness_postflight.json').read_text());assert post['read_only_preflight_ok'] and not post['ready_for_large_test'] and not post['large_tests_started']
manifest=json.loads((ROOT/'plan/manifest.json').read_text());source_proof={}
for rel,expected in manifest['source_sha256'].items():
 assert base.sha(WS/rel)==expected,rel;source_proof[rel]=dict(executed_sha256=expected,current_identical=True)
base.write(ROOT/'validation/executed_source_identical.json',source_proof)
git=['/mnt/c/Program Files/Git/cmd/git.exe','-C','C:/dev/flexcell'];rows=subprocess.check_output(git+['diff','--numstat','bf53df5e3339f9b55ed4a4b897c7e2e863e38952','f10be54fee2a4ae3dd1ef7479e155baee8fd4062'],text=True)
(LOG/'code_numstat.txt').write_text(rows);added=deleted=0
for s in rows.splitlines():
 a,d,rel=s.split('\t',2)
 if not rel.endswith('.md'):added+=int(a);deleted+=int(d)
change=dict(record_kind='GIT_SOURCE_CHANGE_SNAPSHOT',base_revision='bf53df5e3339f9b55ed4a4b897c7e2e863e38952',target_revision='f10be54fee2a4ae3dd1ef7479e155baee8fd4062',code_added=added,code_deleted=deleted,config_added=0,config_deleted=0,rules_added=None,states_added=None,scope='production, client, auditors and initial tests; receipt-local tooling and later regression tests additional and incompletely measured')
base.write(ROOT/'validation/source_change.json',change)
base.COST.append(ROOT/'cost.jsonl',dict(event_id='shared-prebatch-source-snapshot',kind='change_snapshot',arm='hybrid',**{k:change[k] for k in ['base_revision','target_revision','code_added','code_deleted','config_added','config_deleted','rules_added','states_added']},evidence=[base.COST.pin(ROOT/'validation/source_change.json')]))
ledger=base.COST.read_ledger(ROOT/'cost.jsonl');trials=[r['payload'] for r in ledger[1:] if r['payload']['kind']=='trial']
assert len(trials)==3 and len([t for t in trials if t['case_id']=='invalid-chain-control' and t['reported_outcome']=='FAILED'])==1
assert {t['trial_id'] for t in trials}=={native[0]['run_id'],source['run_id'],control['run_id']}
interval=json.loads((LOG/'start_interval.json').read_text());interval.update(end_perf_counter_ns=time.perf_counter_ns());interval['elapsed_minutes']=(interval['end_perf_counter_ns']-interval['start_perf_counter_ns'])/60e9;interval['scope']='partial wall interval includes build, wait, correction and documentation; not complete labor'
base.write(ROOT/'validation/partial_development.json',interval)
report=dict(record_kind='PRE_LARGE_TEST_DEVELOPMENT_CHECKPOINT',ok=True,development_checkpoint='COMPLETE_FOR_DECLARED_SCOPE',read_only_preflight_ok=True,ready_for_large_test=False,large_tests_started=False,native_episodes=2,expected_rejection_controls=1,retained_trial_records=3,original_harness_failure='RETAINED; status5 wrongly used for ABORTED; observed status6; corrected read-only with original goal never resubmitted',runtime_fingerprint=deployment['runtime_fingerprint'],target_routing=audit['routing'][0],source_routing=audit_routing_episode(source,deployment),controller_goal_terminals=len(statuses),controller_statuses=sorted(set(statuses)),unknown_transport_events=0,skills_tests=345,instrument_tests=54,build='PASS',policy_decide_latency=dict(target=latency(native),source=latency([source])),costs=base.COST.summarize(ledger),source_change=change,partial_development=interval,qualification='FROZEN',AC90='NOT_RUN',n_ge_50='FROZEN',network_stability='NOT_ACCEPTED',B_grasp_root_cause='UNKNOWN',physical_safety='NOT_RUN',gpu_and_actual_api_fees='UNKNOWN',no_failure_replacement=True)
base.write(ROOT/'report.json',report)
for p in LOG.iterdir():
 if p.is_file():shutil.copy2(p,ROOT/'validation'/p.name)
shutil.copy2('/home/ros/.local/share/flexcell/mainline/runtime/20261007_125924/fleet.log',ROOT/'validation/fleet.log')
print(json.dumps({k:report[k] for k in ['ok','native_episodes','expected_rejection_controls','target_routing','source_routing','controller_goal_terminals','read_only_preflight_ok','ready_for_large_test']}))
