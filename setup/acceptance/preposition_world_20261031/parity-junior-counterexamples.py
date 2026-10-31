"""Prove bounded report-validation gaps without editing any original receipt."""
import copy
import json
from pathlib import Path
import sys

stage=Path('/home/ros/agentic_workcell_ws/build/preposition-world-stage')
sys.path.insert(0,str(stage/'scripts'))
from parity_report import compare

root=Path('/home/ros/agentic_workcell_ws/artifacts/preposition-world-20261031/parity-counterexamples')
root.mkdir(exist_ok=False)
source=stage/'setup/acceptance/legacy_parity_20261031'
original=[json.loads((source/backend/'window.json').read_text()) for backend in ('teleport','velocity_servo')]
cases={
    'duplicate_backend':'second window claims teleport too',
    'mixed_skill_backend':'second window claims legacy while first is mtc',
    'stopped_window':'second top-level status is STOPPED despite stored passing episodes',
    'missing_success_metric':'normal PASS has no final_position_error_m',
    'unexpected_normal_failure':'normal case falsely labelled EXPECTED_FAILURE',
}
report=[]
for label,change in cases.items():
    windows=copy.deepcopy(original)
    target=windows[1]
    if label=='duplicate_backend': target['backend']='teleport'
    elif label=='mixed_skill_backend': target['skill_backend']='legacy'
    elif label=='stopped_window': target['status']='STOPPED'
    elif label=='missing_success_metric': target['episodes'][0]['result']['task'].pop('final_position_error_m',None)
    else:
        result=target['episodes'][0]['result']
        result['status']='EXPECTED_FAILURE'
        result['task'].update(outcome='OUTCOME_FAILED',outcome_val=1,error_code='ERR_INTERNAL')
    paths=[]
    for backend,value in zip(('teleport','velocity_servo'),windows):
        directory=root/label/backend
        directory.mkdir(parents=True)
        path=directory/'window.json'
        path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
        paths.append(path)
    try:
        result=compare(paths)
        actual=result['status']
    except ValueError as exc:
        actual=str(exc)
    report.append(dict(case=label,change=change,expected='REJECT',actual=actual))
(root/'counterexamples.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
