#!/usr/bin/env python3
"""Read-only correction of the retained status-6 rejection; never resubmit."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path('/home/ros/agentic_workcell_ws/src/flexcell/flexcell_skills')))
from flexcell_skills.contracts.receipt_json import loads


def audit(command,events,raw_sizes,deployment,aborted):
    if type(command['return_code']) is not int or command['return_code']!=2:raise ValueError('only the retained known predicate exit 2 is eligible; no signal/unknown accepted')
    marker='RESULT ';stdout=command['stdout']
    if not stdout.startswith(marker):raise ValueError('expected exact structured result')
    r=loads(stdout[len(marker):])
    if not all(type(r.get(k)) is int for k in ['action_status','outcome_val','error_code_val']):raise ValueError('typed result required')
    if r['action_status']!=aborted or r['outcome_val']!=1 or r['error_code_val']!=60 or r['component_run_ids']!=[]:raise ValueError('expected aborted invalid-plan result')
    if len(events)!=1:raise ValueError('any prior event/dispatch rejects correction')
    e=events[0]
    if e.get('event')!='TERMINAL' or type(e.get('seq')) is not int or e['seq']!=0 or type(e.get('outcome')) is not int or e['outcome']!=1 or type(e.get('error_code')) is not int or e['error_code']!=60 or e.get('run_id')!=r['run_id'] or e.get('goal_uuid')!=r['goal_uuid'] or e.get('runtime_fingerprint')!=deployment['runtime_fingerprint']:raise ValueError('parent/client mismatch')
    watched=['move_to_pose.jsonl','decisions.jsonl','skill_transport.jsonl','controller_transport.jsonl','pick.jsonl','place.jsonl','verify.jsonl','observe.jsonl']
    if any(raw_sizes.get(name)!=0 for name in watched):raise ValueError('missing or nonempty dispatch delta')
    return dict(ok=True,record_kind='POSTHOC_NEGATIVE_CONTROL_STATUS_CORRECTION',expected_action_status=aborted,actual_action_status=r['action_status'],task_outcome='FAILED',typed_error_code=60,guard_condition_confirmed=True,zero_dispatch=True,native_episodes=0,original_client_return_code=2,original_driver_harness_failure='RETAINED',original_trial_label='FAILED; unchanged',run_id=r['run_id'],runtime_fingerprint=deployment['runtime_fingerprint'],no_resubmission=True)


def main():
    from action_msgs.msg import GoalStatus
    root=Path(__file__).resolve().parents[1];control=root/'execution/invalid-chain-control'
    report=audit(loads((control/'client.json').read_text()),[loads(s) for s in (control/'parent.jsonl').read_text().splitlines()],{p.name:p.stat().st_size for p in (control/'raw').glob('*.jsonl')},loads((root/'plan/deployment.json').read_text()),GoalStatus.STATUS_ABORTED)
    report['ros_constants']=dict(STATUS_SUCCEEDED=GoalStatus.STATUS_SUCCEEDED,STATUS_CANCELED=GoalStatus.STATUS_CANCELED,STATUS_ABORTED=GoalStatus.STATUS_ABORTED)
    with (root/'validation/control_audit_v2.json').open('x') as f:json.dump(report,f,indent=2)
    print(json.dumps(report));return 0


if __name__=='__main__':raise SystemExit(main())
