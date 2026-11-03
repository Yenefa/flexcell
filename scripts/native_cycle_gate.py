"""Independent raw evidence for five stationary-arm native attachment cycles."""
from collections import Counter
import json
import math
from pathlib import Path
import statistics

from contact_gate import entity, observation, require
from integrated_contact_gate import freefall, rows, STEP, BOXES
from flexcell_skills.joint_follow import relative_pose


def limits(declaration):
    require(type(declaration['schema_version']) is int and declaration['schema_version'] == 1 and
            declaration['min_preflight_rtf'] == .3 and
            declaration['objects'] == ['target_box_a', 'target_box_a', 'target_box_b', 'target_box_b', 'target_box_a'] and
            declaration['max_cycles'] == 5 and declaration['step_ns'] == STEP and
            declaration['hold_ns'] == 10_100_000_000 and declaration['min_attached_ns'] == 10_000_000_000 and
            declaration['preposition_poses'] == dict(target_box_a=[.35,.18,.22,0.,0.,0.,1.],
                                                    target_box_b=[.35,-.18,.22,0.,0.,0.,1.]) and
            declaration['reference_bind_max_ns'] == 20_000_000 and
            declaration['reference_target_limit_m'] == .005 and declaration['translation_limit_m'] == .002 and
            declaration['rotation_limit_rad'] == math.pi/180 and declaration['max_clock_skew_ns'] == 50_000_000 and
            declaration['release_interval_ns'] == 40_000_000 and declaration['settle_ns'] == 1_000_000_000,
            'native cycle declaration or thresholds changed')


# Supervisor deadline for the per-cycle worker. The deadline is a hang detector,
# so it can never be tighter than what the declaration itself permits: five
# cycles of 1.05 s settle-in + hold + 1 s settle at ``min_preflight_rtf`` are
# already 202.5 s of physics before any gating. Run 41407787100 showed the old
# fixed 330 s could not cover a conforming run: 196 s of protocol plus five raw
# audits of 14.4-35.5 s. The audit allowance is therefore declared here, next to
# the thresholds it must not silently move.
CYCLE_SETTLE_IN_NS = 1_050_000_000
AUDIT_ALLOWANCE_S = 25.
CLIENT_ALLOWANCE_S = 30.


def worker_deadline_s(declaration):
    """Deadline that always covers the declaration's own throughput floor."""
    cycle_s = (CYCLE_SETTLE_IN_NS + declaration['hold_ns'] + declaration['settle_ns']) / 1e9
    floor = declaration['max_cycles'] * cycle_s / declaration['min_preflight_rtf']
    return math.ceil(floor + declaration['max_cycles'] * AUDIT_ALLOWANCE_S + CLIENT_ALLOWANCE_S)


def pose_error(parent, child, reference):
    position, rotation = relative_pose(parent, child)
    p, q = reference
    return math.dist(position, p), 2*math.acos(min(1., abs(sum(a*b for a, b in zip(rotation, q)))))


def verify_cycle(physics, contacts, cycle, events, declaration):
    limits(declaration)
    name, session, index = cycle['object'], cycle['session'], cycle['index']
    target = declaration['preposition_poses'][name]
    require(name == declaration['objects'][index] and len(session) == 32 and
            all(c in '0123456789abcdef' for c in session), 'invalid cycle identity')
    calls = [r for r in events if r['cycle'] == index]
    require(all(r['transport_ok'] is True and r['reply_mono_ns'] >= r['request_mono_ns'] > 0 for r in calls),
            'native call has an unknown reply or invalid timestamps')
    by_label = {r['label']: r for r in calls if r['label'] != 'heartbeat'}
    require(len(by_label) == sum(r['label'] != 'heartbeat' for r in calls), 'duplicate control operation')
    prepose, engage, release = [by_label[k] for k in ('preposition', 'engage', 'release')]
    require(sum(r['operation'] == 'set_pose' for r in calls) == 1 and prepose['reply'] is True and
            prepose['object'] == name and prepose['pose'] == target and
            engage['reply'] is True and release['reply'] is True and
            engage['session'] == release['session'] == session, 'preposition/binding/release identity differs')
    require(engage['operation'] == 'engage' and engage['object'] == name and release['operation'] == 'release',
            'wrong binding operation or target')
    passive = next(n for n in BOXES if n != name)
    other_engage,other_pin = by_label['reject_other_engage'],by_label['reject_other_pin']
    require(other_engage['operation'] == 'engage' and other_pin['operation'] == 'pin' and
            other_engage['object'] == other_pin['object'] == passive and other_pin['session'] == session and
            len(other_engage['session']) == 32 and other_engage['session'] != session and
            all(c in '0123456789abcdef' for c in other_engage['session']), 'invalid cross-object control identity')
    for label in ('reject_other_engage', 'reject_other_pin', 'reject_retired_engage'):
        require(by_label[label]['reply'] is False, 'declared ownership rejection failed: '+label)
    if index:
        require(by_label['reject_old_release']['reply'] is False and by_label['reject_old_pin']['reply'] is False,
                'old session modified the current owner')
        require(by_label['reject_old_release']['session'] == by_label['reject_old_pin']['session'] == cycle['previous_session'],
                'wrong old-session probe identity')
    require(by_label['reject_retired_engage']['session'] == session and
            by_label['reject_retired_engage']['object'] == name, 'retired probe identity differs')
    for label in ('after_release','final_status'):
        state = by_label[label]['reply']
        require(state['ready'] is True and state['engaged'] is False and state['session'] == '' and
                state['component_present'] == [False,False], 'retired probe was not reconciled while detached')
    probe = physics[cycle['retired_probe_sim_ns']]
    require(all(probe['objects'][n]['joint_component'] is False for n in BOXES) and
            by_label['after_release']['reply_mono_ns'] <= by_label['reject_retired_engage']['request_mono_ns'] and
            0 <= by_label['reject_retired_engage']['request_mono_ns']-probe['monotonic_ns'] <= 50_000_000 and
            math.dist(by_label['reject_retired_engage']['pose'][:3],probe['objects'][name]['pose'][:3]) < .001,
            'retired probe used a distant or stale target')
    require(all(r['reply'] is True for r in calls if r['label'] == 'heartbeat'), 'active lease renewal rejected')
    ready = by_label['before_preposition']['reply']
    require(ready['ready'] is True and ready['engaged'] is False and ready['session'] == '' and
            ready['component_present'] == [False, False], 'preposition was not explicitly detached')
    require(ready['sim_ns'] <= cycle['reference_sim_ns'], 'preposition status is from the future')
    before = [p for p in physics.values() if by_label['before_preposition']['reply_mono_ns'] <=
              p['monotonic_ns'] <= prepose['request_mono_ns']]
    require(before and all(all(p['objects'][n]['joint_component'] is False for n in BOXES) for p in before),
            'set_pose was not physically detached throughout the preposition precondition')
    reference_ns = cycle['reference_sim_ns']
    reference_row = physics[reference_ns]
    require(prepose['reply_mono_ns'] <= reference_row['monotonic_ns'] <= engage['request_mono_ns'],
            'reference is not between acknowledged set_pose and engage request')
    ref_observation = observation(contacts[reference_ns]['targets'][name])
    require(all(reference_row['objects'][n]['joint_component'] is False for n in BOXES) and
            ref_observation['state'] == 'NO_REPORTED_CONTACTS', 'reference was attached or not measured contact-free')
    require(math.dist(reference_row['objects'][name]['pose'][:3], target[:3]) <= .005,
            'preposition was not observed at its declared target')
    candidates = [p['sim_ns'] for p in physics.values() if p['monotonic_ns'] >= prepose['reply_mono_ns'] and
                  p['monotonic_ns'] <= engage['request_mono_ns'] and p['sim_ns'] in contacts and
                  all(p['objects'][n]['joint_component'] is False for n in BOXES) and
                  math.dist(p['objects'][name]['pose'][:3], target[:3]) <= .005 and
                  observation(contacts[p['sim_ns']]['targets'][name])['state'] == 'NO_REPORTED_CONTACTS']
    require(candidates and reference_ns == min(candidates), 'reference skipped an earlier eligible preposition frame')
    attached = [p for p in physics.values() if p['sim_ns'] >= reference_ns and
                p['monotonic_ns'] <= release['reply_mono_ns'] and p['objects'][name]['joint_component'] is True]
    require(attached, 'no physical attachment')
    first, last = attached[0]['sim_ns'], attached[-1]['sim_ns']
    require(0 < first-reference_ns <= declaration['reference_bind_max_ns'] and
            last-first >= declaration['min_attached_ns'], 'binding gap or attached duration outside declaration')
    detached = [p for p in physics.values() if p['sim_ns'] > last and p['objects'][name]['joint_component'] is False]
    require(detached and release['request_mono_ns'] <= detached[0]['monotonic_ns'] <= release['reply_mono_ns'],
            'physical release did not belong to the explicit release call')
    released = detached[0]['sim_ns']; lower, upper = reference_ns-1_000_000_000, released+500_000_000
    keys = list(range(lower, upper+1, STEP))
    require(all(ns in physics and ns in contacts for ns in keys), 'missing native per-step evidence')
    reference = relative_pose(reference_row['parent_pose'], reference_row['objects'][name]['pose'])
    passive_ref = reference_row['objects'][passive]['pose'][:3]
    peak_position = peak_angle = parent_motion = 0.
    force, states, binding = [], Counter(), None
    previous_p = previous_c = None
    for ns in keys:
        p, c = physics[ns], contacts[ns]
        require(p['step_ns'] == c['step_ns'] == STEP and p['sim_ns'] == c['sim_ns'] == ns and
                abs(p['monotonic_ns']-c['monotonic_ns']) <= declaration['max_clock_skew_ns'], 'raw clock cohort mismatch')
        if previous_p is not None:
            require(p['monotonic_ns'] > previous_p and c['monotonic_ns'] > previous_c, 'reordered native evidence')
        previous_p, previous_c = p['monotonic_ns'], c['monotonic_ns']
        ids = tuple(entity(c['targets'][n]['collision_entity']) for n in (*BOXES, 'ground_plane'))
        require(len(set(ids)) == 3 and (binding is None or ids == binding), 'native collision binding changed or aliased')
        binding = ids
        observed = {n: observation(c['targets'][n]) for n in (*BOXES, 'ground_plane')}
        require(observed['ground_plane']['state'] == 'UNKNOWN', 'missing sensor invented a force observation')
        for n in BOXES:
            require(observed[n]['state'] in ('CONTACTS_WITH_FORCE', 'NO_REPORTED_CONTACTS') and
                    all(abs(a-b) <= 1e-12 for a, b in zip(c['targets'][n]['pose'], p['objects'][n]['pose'])),
                    'contact/motion pose mismatch or missing box force')
            relative_pose(p['parent_pose'], p['objects'][n]['pose'])
        states[observed[name]['state']] += 1
        if ns < reference_ns and observed[passive]['force_magnitude_n'] is not None:
            force.append(observed[passive]['force_magnitude_n'])
        if reference_ns <= ns <= last:
            require(p['objects'][passive]['joint_component'] is False and
                    math.dist(p['objects'][passive]['pose'][:3], passive_ref) < .002,
                    'passive object moved or attached')
            require(observed[name]['state'] == 'NO_REPORTED_CONTACTS', 'contact during noncontact cycle')
            position, angle = pose_error(p['parent_pose'], p['objects'][name]['pose'], reference)
            require(position < .002 and angle < math.pi/180, 'preposition-reference SE3 drift exceeded limits')
            require(p['objects'][name]['joint_component'] is (ns >= first), 'attachment was discontinuous')
            peak_position, peak_angle = max(peak_position, position), max(peak_angle, angle)
            parent_motion = max(parent_motion, math.dist(p['parent_pose'][:3], reference_row['parent_pose'][:3]))
        if released <= ns <= released+declaration['release_interval_ns']:
            require(observed[name]['state'] == 'NO_REPORTED_CONTACTS', 'contact in fixed release interval')
    require(len(force) >= 476 and .392 <= statistics.fmean(force) <= .588, 'passive weight control failed')
    flight = freefall([physics[ns] for ns in range(released, released+40_000_001, STEP)], name, 40_000_000)
    return dict(status='NATIVE_CYCLE_PASS', index=index, object=name, session=session, reference_sim_ns=reference_ns,
                first_attached_ns=first, last_attached_ns=last, release_sim_ns=released,
                reference_bind_gap_ns=first-reference_ns, attached_duration_s=(last-first)/1e9,
                peak_translation_m=peak_position, peak_rotation_rad=peak_angle,
                parent_max_translation_m=parent_motion, passive_force_samples=len(force),
                passive_mean_force_n=statistics.fmean(force), joined_steps=len(keys), states=dict(states), freefall=flight)


def verify_run(out, declaration):
    out = Path(out); limits(declaration)
    result = json.loads((out/'worker.json').read_text())
    deadline = result.get('worker_deadline_s')
    if deadline is not None:
        require(deadline >= worker_deadline_s(declaration), 'worker deadline below the declaration floor')
    require(result['status'] == 'PASS' and len(result['cycles']) == 5, 'five cycles did not complete')
    events = rows(out/'native-events.jsonl')
    physics_rows, contact_rows = rows(out/'physics_steps.jsonl'), rows(out/'contact_steps.jsonl')
    require(len({p['sim_ns'] for p in physics_rows}) == len(physics_rows) and
            len({c['sim_ns'] for c in contact_rows}) == len(contact_rows), 'duplicate raw physics clock')
    for c in contact_rows:
        require(c['source'] == 'ECM_POST_PHYSICS' and c['schema_version'] == 1, 'unknown contact source')
        for t in c['targets'].values(): observation(t)
    for p in physics_rows:
        for n in BOXES: relative_pose(p['parent_pose'],p['objects'][n]['pose'])
    physics = {p['sim_ns']: p for p in physics_rows}; contacts = {c['sim_ns']: c for c in contact_rows}
    require(len({c['session'] for c in result['cycles']}) == 5, 'cycle session reused')
    require(all(c['index'] == i and c['previous_session'] == (result['cycles'][i-1]['session'] if i else '')
                for i,c in enumerate(result['cycles'])), 'cycle order or retired-session chain differs')
    facts = [verify_cycle(physics,contacts,c,events,declaration) for c in result['cycles']]
    require(all(a['release_sim_ns'] < b['reference_sim_ns'] for a,b in zip(facts,facts[1:])), 'cycle intervals overlap')
    return dict(status='FIVE_NATIVE_CYCLES_PASS', cycles=facts, robot_motion_tasks=0,
                qualification_cycles=5, moving_parent_follow_qualified=False, default_admission='NO_GO')
