from pathlib import Path
import sys,json,subprocess,time
workspace=Path('/home/ros/agentic_workcell_ws');logs=Path('/home/ros/fc_sync_logs/grasp_diagnostic_school_20261008')
sys.path.insert(0,str(workspace/'setup/transferbench'))
import grasp_diagnostic as g
import qualification_prepare as q
root=logs/'run_v2';sha=q.sha(root/'plan.json')
before=g.files(root)
def command(name,script,args):
 start=time.perf_counter_ns();p=subprocess.run([sys.executable,str(workspace/script),*args],capture_output=True,text=True,timeout=120)
 value={'return_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'elapsed_ms':(time.perf_counter_ns()-start)/1e6,'arguments':args}
 g.write(logs/(name+'.json'),value);print(name,p.returncode,flush=True)
 return p,json.loads(p.stdout)
args=['run','--root',str(root),'--expected-sha256',sha]
p,read=command('post_readonly','setup/136_grasp_diagnostic.py',args)
assert p.returncode==0 and read['state']=='COMPLETE'
p,refused=command('repeat_refused','setup/136_grasp_diagnostic.py',args+['--execute'])
assert p.returncode==2 and refused['ok'] is False and g.files(root)==before
plan=q.loads((root/'plan.json').read_bytes())
protected={path:q.same_typed(g.files(Path(path)),pin) for path,pin in plan['protected'].items()}
assert all(protected.values())
cal='/home/ros/.config/flexcell/jev_calibration_clef_q8_20261005.json';budget='/home/ros/.config/flexcell/deepseek_budget_20261001.json'
private=workspace/'setup/acceptance/qualification_private_20261008/commitment.json'
p,private_report=command('private_verify','setup/134_qualification_private.py',['verify','--commitment',str(private),'--expected-sha256',q.sha(private),'--workspace',str(workspace),'--history','/home/ros/.ros/flexcell/episodes','--calibration',cal,'--budget',budget])
assert p.returncode==0 and private_report['ok'] is True
p,guard=command('hybrid_guard_status','setup/135_bounded_hybrid_resume.py',['status','--guard','/home/ros/fc_sync_logs/local_fsm_active_20261008/hybrid_resume_guard.json','--expected-sha256','0f8c9ea79dec8686c37c0d465b4cc70692c28b99f2c3235f8cb53f63429f5179'])
assert p.returncode==0 and guard['state']=='PAUSED' and guard['native_episode_count']==5
exposure_files=sorted((root/'execution').glob('*/exposure_*.json'))
layouts=[q.loads(v.read_bytes())['initial_objects'] for v in exposure_files]
# No private coordinates/seed leave this comparison. Publish counts and source pins only.
private_cases=q.loads(Path('/home/ros/fc_sync_logs/qualification_private_20261008/inputs/cases.json').read_bytes())
collisions=sum(any(q.near(c['initial_objects'],v) for v in layouts) for c in private_cases)
assert collisions==0
exposures={'record_kind':'DIRECT_SKILL_EXPOSURE_EXCLUSION_CHECK','private_candidate_count':len(private_cases),'diagnostic_observation_count':len(layouts),'unique_observed_layouts':len({q.digest(v) for v in layouts}),'overlapping_private_cases':collisions,'comparison':'both object positions within 1mm','observation_files':{str(v.relative_to(logs)):q.sha(v) for v in exposure_files},'independent_custody':'NOT_ESTABLISHED','unknown_unrecorded_exposure':'UNKNOWN','private_data_published':False,'future_qualification_must_exclude_these_observations':True,'ready_for_large_test':False,'n_ge_50':'FROZEN'}
g.write(logs/'exposure_exclusion.json',exposures)
summary={'record_kind':'DIRECT_GRASP_DIAGNOSTIC_POSTCHECK','ok':True,'protected_unchanged':protected,'repeat_refused_rc':2,'run_tree_unchanged_after_readonly_and_repeat':g.files(root)==before,'historical_episode_count':len(list((Path.home()/'.ros/flexcell/episodes').glob('*.json'))),'new_task_episodes':0,'new_budget_calls':0,'policy_inference_calls':0,'paused_collector_completed_slots':guard['completed_slots'],'paused_collector_native_episodes':guard['native_episode_count'],'private_commitment_verified':private_report['ok'],'private_overlap_cases':collisions,'qualification_sampling_authorized':False,'ready_for_large_test':False,'n_ge_50':'FROZEN'}
g.write(logs/'postcheck.json',summary)
print('POSTCHECK',summary,flush=True)
