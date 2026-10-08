from pathlib import Path
import sys,json,shutil,datetime
workspace=Path('/home/ros/agentic_workcell_ws');logs=Path('/home/ros/fc_sync_logs/grasp_diagnostic_school_20261008');sys.path.insert(0,str(workspace/'setup/transferbench'))
import grasp_diagnostic as g
import qualification_prepare as q
plan=q.loads((logs/'run_v2/plan.json').read_bytes())
for rel,digest in plan['source_sha256'].items():
 path=logs/'v2_source'/rel
 if not path.exists():
  path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(workspace/rel,path)
 assert q.sha(path)==digest,rel
old=q.loads((logs/'run/plan.json').read_bytes())
for rel,digest in old['source_sha256'].items():
 path=logs/'v1_source'/rel
 if not path.exists():path=logs/'v2_source'/rel
 assert q.sha(path)==digest,rel
for version in ('run','run_v2'):
 p=q.loads((logs/version/'plan.json').read_bytes())
 assert all(q.same_typed(g.files(Path(path)),pin) for path,pin in p['protected'].items())
 assert q.sha(Path(p['deployment']))==p['deployment_sha256']
readiness=g.module(workspace/'setup/131_prebatch_readiness.py')
deployment=Path(plan['deployment']);d=q.loads(deployment.read_bytes());verified=readiness.verify_deployment(d,workspace)
assert verified['runtime_fingerprint']==plan['runtime_fingerprint']
raws=list((logs/'run_v2/execution').glob('*/pick_raw'))
assert len(raws)==2
assert all((raw/'decisions.jsonl').stat().st_size==0 for raw in raws)
assert not any('injected' in r for raw in raws for r in [q.loads(s) for s in (raw/'pick.jsonl').read_text().splitlines()])
runtime=logs/'runtime_snapshot';runtime.mkdir()
for name in ('deployment.json','fleet.log','gazebo.log','moveit.log','move_to_pose.log'):
 with (runtime/name).open('xb') as f:f.write((deployment.parent/name).read_bytes())
g.write(logs/'final_identity_check.json',{'ok':True,'runtime':verified,'production_code_and_install_unchanged':True,'registered_source_snapshots_verified':True,'both_plans_protected_files_unchanged':True,'pick_windows_policy_decision_records':0,'injected_pick_records':0,'executed_instrument_revision':plan['revision'],'latest_tool_revision':'73054433b067e1669cdb2641ce54404bcf8f41a7','latest_tool_hardening_live':'NOT_RUN; no replacement trials','runtime_snapshot_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'n_ge_50':'FROZEN'})
receipt=workspace/'setup/acceptance/grasp_diagnostic_school_20261008'
assert not receipt.exists();shutil.copytree(logs,receipt/'evidence',ignore=shutil.ignore_patterns('__pycache__'))
print('ARTIFACTS',sum(p.is_file() for p in receipt.rglob('*')),'BYTES',sum(p.stat().st_size for p in receipt.rglob('*') if p.is_file()))
