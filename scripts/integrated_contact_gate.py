"""Join same-process per-step contact and motion evidence; never infer force zero."""
from collections import Counter
import json
import math
from pathlib import Path
import statistics

from contact_gate import entity, observation, require

BOXES = ('target_box_a', 'target_box_b')
STEP = 2_000_000


def rows(path):
    with Path(path).open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def freefall(frames, object_id, duration_ns):
    require(duration_ns == 40_000_000, 'unrecognized freefall declaration')
    require(len(frames) == duration_ns // STEP + 1, 'incomplete fixed freefall interval')
    require(all(b['sim_ns'] - a['sim_ns'] == STEP for a, b in zip(frames, frames[1:])),
            'missing freefall step')
    require(all(row['objects'][object_id]['joint_component'] is False for row in frames),
            'joint still present during freefall')
    z = [row['objects'][object_id]['pose'][2] for row in frames]
    require(all(type(v) in (float, int) and math.isfinite(v) for v in z), 'nonfinite freefall pose')
    dt = STEP / 1e9
    gravity = statistics.fmean((c - 2*b + a) / dt**2 for a, b, c in zip(z, z[1:], z[2:]))
    times = [(row['sim_ns'] - frames[0]['sim_ns']) / 1e9 for row in frames]
    velocity = statistics.fmean((v - z[0] - .5*gravity*t*t)/t for t, v in zip(times[1:], z[1:]))
    residual = max(abs(v - (z[0] + velocity*t + .5*gravity*t*t)) for t, v in zip(times, z))
    require(-11.76 <= gravity <= -7.84, 'released body acceleration differs from declared gravity')
    require(residual <= .0001, 'released body is not ballistic within 0.1 mm residual')
    return dict(samples=len(frames), duration_s=duration_ns/1e9, acceleration_m_s2=gravity,
                fitted_initial_velocity_m_s=velocity, max_residual_m=residual, initial_z_m=z[0])


def verify_evidence(physics, contacts, object_id, lo, hi, declaration):
    require(object_id in BOXES, 'unknown integrated object')
    require(declaration['contact_trace'] is True and declaration['physics_step_s'] == .002 and
            declaration['release_clearance_m'] == .05, 'integrated fixture declaration changed')
    limits = declaration['contact_gate']
    require(limits == dict(prebind_ns=1_000_000_000, postrelease_ns=500_000_000,
                          freefall_ns=40_000_000, max_clock_skew_ns=50_000_000,
                          min_weight_samples=476, force_mean_min_n=.392, force_mean_max_n=.588),
            'integrated contact thresholds changed')
    detached = [r for r in physics if r['sim_ns'] > hi and
                r['objects'][object_id].get('joint_component') is False]
    require(detached and detached[0]['sim_ns'] <= hi + 500_000_000, 'no timely physical release')
    release = detached[0]['sim_ns']
    lower, upper = lo - limits['prebind_ns'], release + limits['postrelease_ns']
    require(lower >= 0, 'insufficient prebinding interval')
    joined = [r for r in physics if lower <= r['sim_ns'] <= upper]
    selected = [r for r in contacts if lower <= r['sim_ns'] <= upper]
    count = (upper - lower) // STEP + 1
    for values in (joined, selected):
        require(len(values) == count and values[0]['sim_ns'] == lower and
                values[-1]['sim_ns'] == upper, 'incomplete contact/motion join interval')
        require(all(type(r['sim_ns']) is int and type(r['step_ns']) is int and r['step_ns'] == STEP and
                    type(r['monotonic_ns']) is int and r['monotonic_ns'] > 0 for r in values),
                'invalid integrated simulation clock')
        require(all(b['sim_ns'] - a['sim_ns'] == STEP and b['monotonic_ns'] > a['monotonic_ns']
                    for a, b in zip(values, values[1:])), 'missing or unordered integrated step')
    # Parse every contact snapshot, including those outside the selected interval.
    parsed = {}
    expected = set(BOXES) | {'ground_plane'}
    for row in contacts:
        require(type(row.get('schema_version')) is int and row['schema_version'] == 1 and
                row.get('source') == 'ECM_POST_PHYSICS' and set(row['targets']) == expected,
                'unexpected integrated contact source or targets')
        observed = {name: observation(row['targets'][name]) for name in expected}
        require(row['sim_ns'] not in parsed, 'duplicate contact simulation tick')
        parsed[row['sim_ns']] = observed
    counts = {name: Counter() for name in expected}
    bindings, max_skew, weight = None, 0, []
    passive = next(name for name in BOXES if name != object_id)
    for physical, contact in zip(joined, selected):
        ns = physical['sim_ns']
        require(contact['sim_ns'] == ns, 'contact and motion simulation times disagree')
        skew = abs(physical['monotonic_ns'] - contact['monotonic_ns'])
        require(skew <= limits['max_clock_skew_ns'], 'contact and motion belong to different wall-clock cohorts')
        max_skew = max(max_skew, skew)
        current = tuple(entity(contact['targets'][name]['collision_entity']) for name in sorted(expected))
        require(len(set(current)) == 3, 'integrated collision bindings aliased')
        if bindings is None: bindings = current
        require(current == bindings, 'integrated collision identity changed')
        observed = parsed[ns]
        for name, value in observed.items(): counts[name][value['state']] += 1
        require(observed['ground_plane']['state'] == 'UNKNOWN', 'missing-sensor control invented an observation')
        for name in BOXES:
            require(observed[name]['state'] in ('CONTACTS_WITH_FORCE', 'NO_REPORTED_CONTACTS'),
                    'box contact or force observation unavailable')
            pose = contact['targets'][name]['pose']
            reference = physical['objects'][name]['pose']
            require(len(reference) == 7 and all(type(v) in (float, int) and math.isfinite(v) for v in reference)
                    and all(abs(a-b) <= 1e-12 for a, b in zip(pose, reference)),
                    'contact and motion body poses disagree')
        if lower <= ns < lo:
            force = observed[passive]['force_magnitude_n']
            if force is not None: weight.append(force)
        if release <= ns <= release + limits['freefall_ns']:
            require(observed[object_id]['state'] == 'NO_REPORTED_CONTACTS',
                    'released body contacted another collision in the fixed freefall interval')
    require(len(weight) >= limits['min_weight_samples'], 'passive weight force coverage below declaration')
    mean = statistics.fmean(weight)
    require(limits['force_mean_min_n'] <= mean <= limits['force_mean_max_n'],
            'same-round passive weight differs from m*g')
    flight = freefall([r for r in joined if release <= r['sim_ns'] <= release + limits['freefall_ns']],
                      object_id, limits['freefall_ns'])
    return dict(status='INTEGRATED_CONTACT_RELEASE_PASS', object=object_id, joined_steps=len(joined),
                first_sim_ns=lower, last_sim_ns=upper, release_sim_ns=release,
                max_clock_skew_ns=max_skew, passive_control=passive, weight_samples=len(weight),
                mean_weight_force_n=mean, freefall=flight,
                states={name: dict(value) for name, value in counts.items()},
                signed_target_force_calibrated=False, preposition_reference_qualified=False,
                default_admission='NO_GO',
                interpretation='Same-round joint/motion/contact integration; not contact-grasp or D3 admission')


def verify_run(run, object_id, declaration):
    run = Path(run)
    carry = rows(run / 'skills/carry.jsonl')
    finals = [r for r in carry if r.get('event') == 'follow_final']
    require(len(finals) == 1 and finals[0]['object'] == object_id, 'ambiguous integrated carry session')
    final = finals[0]
    result = verify_evidence(rows(run / 'physics_steps.jsonl'), rows(run / 'contact_steps.jsonl'),
                             object_id, final['follow']['first_sim_ns'], final['follow']['last_sim_ns'], declaration)
    result['session'] = final['session']
    return result
