from pathlib import Path
import json,subprocess,sys,time
logs=Path('/home/ros/fc_sync_logs/grasp_diagnostic_school_20261008')
workspace=Path('/home/ros/agentic_workcell_ws')
root=logs/'run_v2'
assert not root.exists()
script=workspace/'setup/136_grasp_diagnostic.py'
def command(name,args):
    started=time.perf_counter_ns()
    p=subprocess.run([sys.executable,str(script),*args],capture_output=True,text=True,timeout=900)
    value={'return_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'elapsed_ms':(time.perf_counter_ns()-started)/1e6,'arguments':args}
    with (logs/(name+'.json')).open('x') as f: json.dump(value,f,indent=2);f.write('\n')
    print(name,'rc=',p.returncode,flush=True)
    return p,json.loads(p.stdout)
deployment=sorted(Path('/home/ros/.local/share/flexcell/mainline/runtime').glob('*/deployment.json'))[-1]
protected=['/home/ros/.ros/flexcell/episodes','/home/ros/fc_sync_logs/local_fsm_active_20261008','/home/ros/.config/flexcell/deepseek_budget_20261001.json','/home/ros/.config/flexcell/jev_calibration_clef_q8_20261005.json','/home/ros/fc_sync_logs/qualification_private_20261008/inputs']
protected += [str(logs/'run'),str(logs/'v1_source')]
args=['register','--root',str(root),'--deployment',str(deployment),'--revision','b5cac91c44a57b35fa6470e82994f5248e6ed40d']
for path in protected:args+=['--protect',path]
p,result=command('registration_v2',args)
assert p.returncode==0 and result['state']=='REGISTERED',result
sha=result['plan_sha256']
args=['run','--root',str(root),'--expected-sha256',sha]
p,result=command('default_readonly_v2',args)
assert p.returncode==0 and result['state']=='REGISTERED' and not (root/'execution').exists(),result
p,result=command('execution_v2',args+['--execute'])
print('EXECUTION_STATE',result.get('state'),'PICKS',result.get('pick_goals'),flush=True)
print('TRIALS',[(r['object'],r['outcome'],r['measured']) for r in result.get('trials',[])],flush=True)
print('STOP_REASON',result.get('stop_reason'),flush=True)
raise SystemExit(p.returncode)
