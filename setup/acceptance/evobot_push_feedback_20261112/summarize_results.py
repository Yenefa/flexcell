#!/usr/bin/env python3
"""Regenerate the bounded-batch report from retained raw files."""
import argparse
import json
from pathlib import Path

from analyze_runs import analyze, read, rows


def summarize(root):
    names = ['pilot1', 'pilot2', 'A1', 'B1', 'B2', 'A2', 'A3', 'B3']
    results = {name: analyze(root/name) for name in names}
    batch = read(root/'batch_status.json')
    assert batch['status'] == 'COMPLETE'
    assert [r['label'] for r in batch['completed']] == ['A1', 'B1', 'B2', 'A2', 'A3', 'B3']
    assert all(r['infrastructure_valid'] for r in batch['completed'])
    worlds = {r['provenance']['world_sha256'] for r in results.values()}
    assert len(worlds) == 1
    arms = {}
    for arm, labels in [('control', ['A1', 'A2', 'A3']), ('feedback', ['B1', 'B2', 'B3'])]:
        runs = []
        for label in labels:
            result = results[label]
            pushes = rows(root/label/'sim/skills/push.jsonl')
            strokes = [dict(outcome=p['outcome'], error_code=p['error_code'], detail=p['detail'],
                            requested_m=p.get('requested_distance_m'),
                            measured_pre_return_signed_m=p.get('displacement_along_direction_m'))
                       for p in pushes]
            runs.append(dict(label=label, final_signed_forward_mm=1000*result['final_signed_forward_m'],
                             full_acceptance=result['full_acceptance'], terminal_passed=result['terminal_passed'],
                             failed_gates=[k for k,v in result['gate_pass'].items() if not v],
                             attempts=len(pushes), primitive_stroke_results=strokes,
                             minimum_return_forward_mm=1000*result['minimum_return_forward_m'],
                             peak_lift_mm=1000*result['peak_lift_m'],
                             max_protected_excursion_m=result['max_protected_excursion_m'],
                             consecutive_5ms=result['consecutive_5ms'],
                             native_steps_per_object=result['physics_samples_per_object'],
                             controller_final_to_final_truth_mm=(1000*result['controller_final_to_final_truth_forward_m']
                                if result['controller_final_to_final_truth_forward_m'] is not None else None)))
        arms[arm] = dict(valid_runs=len(runs), complete_task_passes=sum(r['full_acceptance'] for r in runs),
                         primitive_stroke_passes=sum(s['outcome']=='0' and s['error_code']==0
                                                    for r in runs for s in r['primitive_stroke_results']),
                         attempts=sum(r['attempts'] for r in runs), runs=runs)
    regressions = list((root/'regression').glob('*/result.json'))
    assert len(regressions) == 1
    regression = read(regressions[0])
    identity = read(regressions[0].parent/'identity.stdout')
    return dict(base='4746a637', experiment='isolated v2 combined feedback / bounded shots / high return',
                task='T08-push-seed2000', fixed_batch=arms,
                infrastructure_failures=0, pilots_separate=True,
                pilot_terminal_signed_mm={k:1000*results[k]['final_signed_forward_m'] for k in ('pilot1','pilot2')},
                pilot_full_acceptance={k:results[k]['full_acceptance'] for k in ('pilot1','pilot2')},
                world_sha256=next(iter(worlds)),
                fixed_batch_wall_seconds=(batch['finished_utc_ns']-batch['started_utc_ns'])/1e9,
                regression=dict(status=regression['status'], task=regression.get('task'),
                                identity_mismatches=identity['mismatches'],
                                imported_package=identity['imported_package'],
                                model_calls=regression.get('model_calls'),
                                previous_two_release_failures='RETAINED_IN_PRIOR_ARCHIVE; NOT_RESOLVED_BY_ONE_PASS'),
                protocol_checks=read(root/'ros_feedback_checks/checks.json'),
                unit_checks=dict(v2_passed=95, raw_log='tests_v2.log'),
                independent_agent_claim_accuracy='NOT_MEASURED',
                formal_baseline='NOT_PROMOTED; CALIBRATION_UNSUPPORTED',
                runtime_autonomous_L4='NOT_ACQUIRED', unseen_instances='NOT_RUN',
                interpretation='Raw counts on one exposed dev instance; no statistical superiority, generalization, or precise stroke-control claim')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root', type=Path)
    args = p.parse_args()
    print(json.dumps(summarize(args.root), indent=2, allow_nan=False))
