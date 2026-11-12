#!/usr/bin/env python3
"""Read-only reproduction of the geometry-pair and initialization outcomes."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'evobot_push_feedback_20261112'))
from analyze_runs import analyze,rows


def summarize(root):
    pair = json.loads((root/'pair_status.json').read_text())
    assert pair['status']=='COMPLETE'
    assert [r['label'] for r in pair['completed']]==['G0','G1']
    runs = {}
    for name in ['G0','G1']:
        result = analyze(root/name)
        pushes = rows(root/name/'sim/skills/push.jsonl')
        runs[name] = dict(ee_height_m=result['provenance']['ee_height_m'],
                         final_signed_forward_mm=1000*result['final_signed_forward_m'],
                         full_acceptance=result['full_acceptance'],terminal_passed=result['terminal_passed'],
                         independent_gates=result['gate_pass'],evidence_status=result['evidence_status'],
                         primitive_stroke_passes=sum(p['outcome']=='0' and p['error_code']==0 for p in pushes),
                         attempts=len(pushes),primitive_outcomes=[dict(outcome=p['outcome'],error_code=p['error_code'],
                             detail=p['detail'],measured_pre_return_signed_m=p.get('displacement_along_direction_m')) for p in pushes],
                         trajectory_consecutive_5ms=result['consecutive_5ms'],
                         world_sha256=result['provenance']['world_sha256'])
    assert runs['G0']['world_sha256']==runs['G1']['world_sha256']
    init = json.loads((root/'initialization_probe/result.json').read_text())
    return dict(base='d87f1701',geometry_pair=runs,geometry_configuration_decision='55mm_REJECTED',
                default_ee_height_m=.020,geometry_pair_infrastructure_failures=0,
                speed_pair='NOT_RUN: retained contact data favored geometry hypothesis',
                initialization_probe=init,initialization_is_robot_task_capability=False,
                existing_unit_checks_passed=95,coordinate_checks_passed=5,initializer_checks_passed=8,
                ros_protocol_checks=json.loads((root/'ros_feedback_checks/checks.json').read_text()),
                superseded_proposal_generator_check=json.loads((root/'proposal_protocol_audit.json').read_text()),
                newly_acquired_robot_task_capability='NONE_CLAIMED_THIS_TURN',
                unseen_instances='NOT_RUN',ordinary_pick_place_regression='NOT_REPEATED_THIS_TURN; prior outcomes retained',
                independent_agent_claim_accuracy='NOT_MEASURED',known_false_rejection='NONE_CONFIRMED_IN_THIS_PAIR',
                formal_baseline='NOT_PROMOTED; CALIBRATION_UNSUPPORTED',runtime_autonomous_L4='NOT_ACQUIRED')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path)
    print(json.dumps(summarize(p.parse_args().root),indent=2,allow_nan=False))
