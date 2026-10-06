import importlib.util,json,hashlib,shutil,sys
from pathlib import Path
WS=Path('/home/ros/agentic_workcell_ws');ROOT=WS/'setup/acceptance/composite_api_20261007';LOG=Path('/home/ros/fc_sync_logs/composite_api_20261007')
sys.path.insert(0,str(WS/'setup/transferbench'))
import t1_pilot as base
import t3_swap_pilot as old
from adjudicate_t1 import latency
from flexcell_skills.contracts.routing_audit import audit_routing_episode
correction=json.loads((LOG/'audit_correction_commit.json').read_text());added=deleted=config_added=config_deleted=0
for line in (LOG/'code_numstat.txt').read_text().splitlines():
 a,d,p=line.split('\t',2)
 if p.endswith('.md'):continue
 if p.endswith('.json'):config_added+=int(a);config_deleted+=int(d)
 else:added+=int(a);deleted+=int(d)
change=dict(record_kind='GIT_SOURCE_CHANGE_SNAPSHOT',base_revision='77e59e5e85769b5c5f0b5667b6e2e4028f57bc4a',target_revision=correction['correction_commit'],
 code_added=added,code_deleted=deleted,config_added=config_added,config_deleted=config_deleted,rules_added=None,states_added=None,
 scope='production source, interfaces, CLI, audits and tests; docs excluded; receipt-local pilot/report tooling work additional and incompletely measured')
base.write(ROOT/'validation/source_change.json',change)
base.COST.append(ROOT/'cost.jsonl',dict(event_id='shared-composite-api-source-snapshot',kind='change_snapshot',arm='hybrid',
 **{k:change[k] for k in ['base_revision','target_revision','code_added','code_deleted','config_added','config_deleted','rules_added','states_added']},
 evidence=[base.COST.pin(ROOT/'validation/source_change.json')]))
ledger=base.COST.read_ledger(ROOT/'cost.jsonl');cost=base.COST.summarize(ledger)
summary=old.load(ROOT/'execution_summary.json');deployment=old.load(ROOT/'plan/deployment.json');audit=old.load(ROOT/'validation/audit_attempt02.json')
assert audit['ok'] and summary['composite_result']['outcome_val']==0 and summary['source_result']['outcome']=='SUCCEEDED'
source=old.load(ROOT/'execution/S1/episode.json');source_client=old.load(ROOT/'execution/S1/client.json');source_result=base.result_from_output(source_client['stdout'])
assert base.success_predicate(source,source_result,source_client['return_code'])
assert audit_routing_episode(source,deployment)['ok'] and source['run_id']==summary['source_result']['run_id']
assert source_client['return_code']==0 and old.load(ROOT/'execution/composite/client.json')['return_code']==0
native=[old.load(p) for p in (ROOT/'execution/composite/episodes').glob('*.json')]
assert len(native)==3 and len(set([e['run_id'] for e in native]+[source['run_id']]))==4
for episode in native+[source]:assert episode['runtime_fingerprint']==deployment['runtime_fingerprint']
trials=[r['payload'] for r in ledger[1:] if r['payload']['kind']=='trial'];assert len(trials)==4
assert {e['run_id'] for e in native+[source]}=={e['trial_id'] for e in trials}
controllers=[];unknown=[]
for folder in [ROOT/'execution/composite/raw',ROOT/'execution/S1/raw']:
 for p in folder.glob('*transport.jsonl'):
  for line in p.read_text().splitlines():
   if line.strip():
    row=base.COST.decode(line);event=row.get('event','')
    if event=='controller_goal_terminal':controllers.append(row['status'])
    if 'quarantin' in event or event in ('goal_send_timeout','goal_response_unknown','goal_response_error'):unknown.append(row)
assert len(controllers)==30 and set(controllers)=={4} and not unknown
report=dict(record_kind='POSTHOC_SERIALIZATION_CORRECTION',schema_version=2,ok=True,
 original_pilot_return_code=1,original_pilot_harness_status='RETAINED_AUDIT_FAILURE',original_auditor_preserved=True,
 correction='normalize journal final_state by frozen EpisodeRecorder._sanitize before exact equality; original finite nonnegative <=.06m predicates unchanged',
 logical_composite_attempts=1,source_regression_attempts=1,native_episodes=4,no_resampling=True,
 composite=audit,source=dict(outcome='SUCCEEDED',run_id=source['run_id'],audit=audit_routing_episode(source,deployment)),
 controller_goal_terminals=len(controllers),controller_statuses=controllers,quarantines=len(unknown),
 policy_decide_latency={'target':latency(native),'source':latency([source])},
 costs=cost,source_change=change,partial_development=old.load(LOG/'development_interval.json'),
 source_continuation_elapsed_minutes=summary['source_continuation_elapsed_minutes'],complete_human_or_agent_effort='NOT_RUN',
 actual_api_invoice='UNKNOWN',gpu_cost='UNKNOWN',AC90='NOT_RUN',n_ge_50='FROZEN',physical_safety='NOT_RUN',network_stability='NOT_ACCEPTED')
base.write(ROOT/'report.json',report)
for p in LOG.glob('*'):
 if p.is_file() and p.name not in ['finalize_report.py']:
  target=ROOT/'validation'/p.name
  if not target.exists():shutil.copyfile(p,target)
  else:assert target.read_bytes()==p.read_bytes(),p
for rel in ['setup/127_composite_audit.py','setup/transferbench/test_composite_audit.py','docs/COMPOSITE_TASKS.md']:
 target=ROOT/'source_posthoc'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(WS/rel,target)
for name in ['preflight.sh','pilot.sh','continue_source.sh','audit.sh']:
 shutil.copyfile(LOG/name,ROOT/'scripts'/name)
runtime=Path('/home/ros/.local/share/flexcell/mainline/runtime/20261007_001918')
shutil.copyfile(runtime/'fleet.log',ROOT/'validation/fleet.log')
print(json.dumps({'ok':True,'native_episodes':4,'controller_terminals':30,'target_routing':audit['routing'],'source_routing':report['source']['audit'],
 'latency':report['policy_decide_latency'],'source_change':change}))
