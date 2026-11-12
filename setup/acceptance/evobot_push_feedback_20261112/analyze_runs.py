#!/usr/bin/env python3
"""Read retained run directories; keep controller snapshots and final truth separate."""
import argparse
import bisect
import json
import math
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def analyze(path):
    before, after = (read(path / name)['objects'] for name in ('gt_before.json', 'gt_after.json'))
    verdict = read(path / 'verdict.json')
    physics = rows(path / 'physics.jsonl')
    stamps = [p['monotonic_ns'] for p in physics]
    assert stamps == sorted(stamps), 'native clock must be ordered'
    gates = {g['gate']: g for g in verdict['evidence']['gates']}
    events = rows(path / 'trial/events.jsonl') if (path / 'trial/events.jsonl').exists() else []
    decisions = [e for e in events if e['kind'] == 'DECISION']
    pushes = rows(path / 'sim/skills/push.jsonl') if (path / 'sim/skills/push.jsonl').exists() else []

    def sample(stamp):
        i = bisect.bisect_left(stamps, stamp)
        i = min(range(max(0, i-1), min(len(stamps), i+1)), key=lambda j: abs(stamps[j]-stamp))
        return physics[i]['objects']['target_box_a']['pose'][:3], abs(stamps[i]-stamp) / 1e6

    routes, intervals, holds = [], [], []
    for push in pushes:
        starts, requests = {}, {}
        for e in push['events']:
            phase, stage = e.get('phase'), e.get('stage')
            if e['event'] == 'REPOSITION_OBJECT_BEFORE':
                starts[phase] = e
            elif e['event'] == 'REPOSITION_OBJECT_AFTER':
                start = starts.pop(phase)
                valid = start['position'] is not None and e['position'] is not None
                routes.append(dict(request_id=push['request_id'], phase=phase, valid=valid,
                                   forward_m=start['position'][0]-e['position'][0] if valid else None,
                                   before=start['position'], after=e['position']))
            elif e['event'] == 'REPOSITION_WAYPOINT_REQUEST':
                requests[(phase, stage)] = e
            elif e['event'] in ('REPOSITION_WAYPOINT_RESULT', 'REPOSITION_WAYPOINT_FAILED'):
                start = requests.pop((phase, stage))
                a, ea = sample(start['monotonic_ns'])
                b, eb = sample(e['monotonic_ns'])
                intervals.append(dict(request_id=push['request_id'], phase=phase, stage=stage,
                                      outcome=e['event'], forward_m=a[0]-b[0], before=a, after=b,
                                      native_alignment_error_ms=max(ea, eb),
                                      actual_ee_after=e.get('actual_after')))
            elif e['event'] == 'REPOSITION_HIGH_HOLD':
                holds.append(e)
        for phase, start in starts.items():
            routes.append(dict(request_id=push['request_id'], phase=phase, valid=False,
                               forward_m=None, before=start['position'], after=None))

    forward = before['target_box_a'][0]-after['target_box_a'][0]
    returns = [r for r in routes if r['phase'] == 'RETREATING']
    minimum_return = min((r['forward_m'] for r in returns if r['valid']), default=None)
    feedback = read(path / 'trial/feedback.json') if (path / 'trial/feedback.json').exists() else None
    monitored = {name: max(math.dist(p['objects'][name]['pose'][:3], before[name][:3])
                           for p in physics) for name in before}
    physics_continuous = all(b['sim_ns']-a['sim_ns'] == 5000000 for a, b in zip(physics, physics[1:]))
    tail = [p['objects']['target_box_a']['pose'][:3] for p in physics
            if p['sim_ns'] >= physics[-1]['sim_ns']-500000000]
    tail_range = [max(p[i] for p in tail)-min(p[i] for p in tail) for i in range(3)]
    mechanism = dict(
        final_forward_at_least_5mm=forward >= .005,
        every_return_loses_at_most_5mm=bool(returns) and all(r['valid'] for r in returns)
            and minimum_return >= -.005,
        protected_unmoved=gates['protected_unmoved']['ok'],
        no_attachment=gates['no_attachment']['ok'],
        no_lift=gates['no_lift']['ok'], table_support=gates['table_support']['ok'],
        valid_trajectory=gates['trajectory']['ok'] and physics_continuous,
        valid_post_state=feedback is not None and feedback['status'] not in ('STATE_UNAVAILABLE', 'CANCELED'))
    return dict(run=path.name, provenance=read(path / 'provenance.json'),
                final_signed_forward_m=forward,
                final_target=after['target_box_a'], controller=feedback,
                controller_decisions=decisions,
                controller_final_to_final_truth_forward_m=(forward-decisions[-1]['net_along_m'])
                    if decisions else None,
                full_acceptance=verdict['passed'], terminal_passed=verdict['terminal_passed'],
                gate_pass={k:v['ok'] for k,v in gates.items()},
                evidence_status=verdict['evidence']['evidence_status'],
                peak_lift_m=max(p['objects']['target_box_a']['pose'][2] for p in physics)-before['target_box_a'][2],
                max_protected_excursion_m=monitored['target_box_b'],
                gripper_gate=gates['gripper'], physics_samples_per_object=len(physics),
                consecutive_5ms=physics_continuous, minimum_return_forward_m=minimum_return,
                last_half_sim_second_xyz_range_m=tail_range,
                final_truth_to_last_native_distance_m=math.dist(after['target_box_a'][:3], tail[-1]),
                routes=routes, waypoint_intervals=intervals, high_holds=holds,
                mechanism_checks=mechanism, mechanism_gate_passed=all(mechanism.values()),
                independent_agent_claim_accuracy='NOT_MEASURED')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root', type=Path)
    p.add_argument('runs', nargs='+')
    args = p.parse_args()
    print(json.dumps({name: analyze(args.root/name) for name in args.runs}, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
