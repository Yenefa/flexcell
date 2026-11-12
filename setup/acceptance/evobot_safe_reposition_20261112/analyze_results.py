"""Read-only recomputation from the archived control, candidate and failures."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--archive', type=Path, default=Path(__file__).with_name('raw_runs.zip'))
parser.add_argument('--out', type=Path)
args = parser.parse_args()
with zipfile.ZipFile(args.archive) as z:
    def read(path):
        return json.loads(z.read(path))

    def lines(path):
        return [json.loads(line) for line in z.read(path).decode().splitlines() if line.strip()]

    geometry = read('geometry.json')
    result = dict(kind='SAFE_REPOSITION_DEVELOPMENT_PAIR', arms={}, regressions={},
                  sample_scope='one physical control and one physical candidate; one zero-push infrastructure failure',
                  claim_assessment='NOT_MEASURED: probe did not supply an Agent success claim',
                  formal_baseline_promoted=False)
    for arm in ('control', 'candidate_retry1'):
        initial = read(arm + '/gt_before.json')['objects']
        final = read(arm + '/gt_after.json')['objects']
        verdict = read(arm + '/verdict.json')
        bundle = read(arm + '/evidence_bundle.json')
        provenance = read(arm + '/provenance.json')
        physics = lines(arm + '/physics.jsonl')
        records = lines(arm + '/sim/skills/push.jsonl')
        stamps = [r['sim_ns'] for r in physics]
        entry = dict(
            net_displacement_along_minus_x_mm=1000*(initial['target_box_a'][0] - final['target_box_a'][0]),
            blue_net_displacement_m=math.dist(initial['target_box_b'][:3], final['target_box_b'][:3]),
            passed=verdict['passed'], terminal_passed=verdict['terminal_passed'],
            evidence_status=verdict['evidence']['evidence_status'],
            gates={g['gate']: g['ok'] for g in verdict['evidence']['gates']},
            native_physics_steps=len(physics),
            consecutive_5ms_steps=all(b-a == 5_000_000 for a, b in zip(stamps, stamps[1:])),
            trajectory_dropped={name: value['dropped_samples'] for name, value in bundle['objects'].items()},
            peak_red_lift_m=max(s[5] for s in bundle['objects']['target_box_a']['samples'])-initial['target_box_a'][2],
            frozen_gripper_gate=next(g for g in verdict['evidence']['gates'] if g['gate'] == 'gripper'),
            world_sha256=provenance['world_sha256'],
            push_source_sha256=provenance['sources']['flexcell_skills.push_server']['sha256'],
            core_push_sha256=provenance['sources']['flexcell_skills.contracts.push']['sha256'],
            individual_push_outcomes=[r['outcome'] for r in records],
            individual_push_details=[r['detail'] for r in records],
            driver_report=read(arm + '/trial/recovery.json')['verdict'])
        if arm == 'candidate_retry1':
            routes, clearances = [], []
            for attempt, record in enumerate(records, 1):
                for phase in ('APPROACH', 'RETREATING'):
                    events = [e for e in record['events'] if e.get('phase') == phase]
                    before = next(e['position'] for e in events if e['event'] == 'REPOSITION_OBJECT_BEFORE')
                    after = next(e['position'] for e in events if e['event'] == 'REPOSITION_OBJECT_AFTER')
                    waypoints = [e for e in events if e['event'] == 'REPOSITION_WAYPOINT_RESULT']
                    routes.append(dict(attempt=attempt, phase=phase,
                                       red_reverse_x_mm=1000*(after[0]-before[0]),
                                       stages=[e['stage'] for e in waypoints]))
                    clearances.extend(e['actual_after'][2] for e in waypoints if e['stage'] in ('LIFT', 'TRANSFER'))
            entry.update(routes=routes, measured_clearance_endpoints=len(clearances),
                         minimum_actual_clearance_z_m=min(clearances),
                         required_measured_clearance_z_m=geometry['minimum_measured_transit_z_m'],
                         return_backslide_within_5mm=all(r['red_reverse_x_mm'] <= 5 for r in routes if r['phase'] == 'RETREATING'),
                         waypoint_order_valid=all(r['stages'] == ['LIFT', 'TRANSFER', 'LOWER'] for r in routes),
                         all_measured_clearances_confirmed=all(v >= geometry['minimum_measured_transit_z_m'] for v in clearances))
        result['arms'][arm] = entry

    result['same_materialized_world'] = result['arms']['control']['world_sha256'] == result['arms']['candidate_retry1']['world_sha256']
    result['frozen_core_same_in_both_arms'] = result['arms']['control']['core_push_sha256'] == result['arms']['candidate_retry1']['core_push_sha256']
    result['acquisition_failure'] = read('candidate/run_status.json')
    result['acquisition_failure']['physical_pushes_dispatched'] = 0
    result['acquisition_failure']['classification'] = 'INVALID_INFRA'
    for label in ('legacy_regression', 'legacy_original_control'):
        matches = [n for n in z.namelist() if n.startswith(label + '/') and n.endswith('/result.json')]
        assert len(matches) == 1, (label, matches)
        path = matches[0]
        smoke = read(path)
        prefix = path.rsplit('/', 1)[0]
        place = lines(prefix + '/skills/place.jsonl')[-1]
        identity = read(prefix + '/identity.stdout')
        result['regressions'][label] = dict(
            status=smoke['status'], physical_tasks_dispatched=smoke['physical_tasks_dispatched'],
            task=smoke['task'], source_identity_mismatches=identity['mismatches'],
            carry_release_confirmed=place.get('carry_release_confirmed'),
            released=place.get('released'), gripper_open=place.get('gripper_open'))
    result['regression_gate'] = 'NOT_CLEARED: original and candidate-overlay normal tasks both failed at gripper release'

    manifest = json.loads(Path(__file__).with_name('raw_runs_sha256.json').read_text())
    for name, digest in manifest.items():
        assert hashlib.sha256(z.read(name)).hexdigest() == digest, name
    result['archive_manifest_verified_files'] = len(manifest)
    assert result['same_materialized_world'] and result['frozen_core_same_in_both_arms']
    output = json.dumps(result, indent=2) + '\n'
    if args.out:
        with args.out.open('x') as stream:
            stream.write(output)
    else:
        print(output)
