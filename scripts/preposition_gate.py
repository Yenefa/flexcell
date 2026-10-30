"""Contact-free pre-attach SE(3) reference, then one constraint for the carry.

The joint qualification used to take the first *attached* sample as its
reference, which hides any pose jump caused by binding itself. This gate takes
the reference from a declared, detached, at-rest interval before the joint
appears, refuses that interval unless the target body's own contact sensor
reports no contact with the arm, and then enforces the same transform over
every 2 ms attached step.

Contact-freedom is only claimed where raw per-step contact data exists; a
missing component stays UNKNOWN and stops the gate. The ground is expected to
carry the body's weight and is not a parent/child contact.
"""
import json
import math
from pathlib import Path

from contact_gate import observation, require

from flexcell_skills.joint_follow import relative_pose, rotation_angle

STEP = 2_000_000


def rows(path):
    with Path(path).open() as stream:
        return [json.loads(line) for line in stream if line.strip()]

FROZEN = dict(
    hold_ns=100_000_000,
    parent_model='open_manipulator_x',
    spread_translation_m=.001,
    spread_rotation_rad=.0015,
    jump_translation_m=.002,
    jump_rotation_rad=math.pi / 180,
    follow_translation_m=.002,
    follow_rotation_rad=math.pi / 180,
    runtime_reference_agreement_m=.0005,
)


def _mean_transform(transforms):
    positions = [item[0] for item in transforms]
    quaternions = [item[1] for item in transforms]
    mean = [math.fsum(p[i] for p in positions) / len(positions) for i in range(3)]
    q = [math.fsum(v[i] for v in quaternions) / len(quaternions) for i in range(4)]
    norm = math.sqrt(sum(x * x for x in q))
    require(.999 <= norm <= 1.001, 'averaged pre-attach quaternion is not normalized')
    return mean + [x / norm for x in q]


def _spread(transforms):
    positions = [item[0] for item in transforms]
    quaternions = [item[1] for item in transforms]
    return (max(math.dist(a, b) for a in positions for b in positions),
            max(rotation_angle(a, b) for a in quaternions for b in quaternions))


def _steps(physics):
    by_time = {}
    for row in physics:
        require(row['sim_ns'] not in by_time, 'duplicate physics simulation tick')
        by_time[row['sim_ns']] = row
    return by_time


def _attachment_bounds(by_time, object_id, first_sample_ns, last_sample_ns):
    """Recover the true 2 ms attachment interval behind two 50 Hz samples."""
    require(first_sample_ns in by_time and last_sample_ns in by_time,
            'a sampled attachment instant is missing from the per-step log')
    def attached(ns):
        return by_time[ns]['objects'][object_id]['joint_component'] is True
    start = first_sample_ns
    while start - STEP in by_time and attached(start - STEP):
        start -= STEP
    require(first_sample_ns - start <= 20_000_000,
            'the attachment boundary is not within one sampled period')
    end = last_sample_ns
    while end + STEP in by_time and attached(end + STEP):
        end += STEP
    require(end - last_sample_ns <= 20_000_000,
            'the release boundary is not within one sampled period')
    require(attached(start) and attached(end), 'the sampled interval is not attached')
    return start, end


def _pre_attach_hold(physics, contacts, object_id, attach_ns, limits):
    lower = attach_ns - limits['hold_ns']
    require(lower > 0, 'no simulation time before attachment')
    hold = [row for row in physics if lower <= row['sim_ns'] < attach_ns]
    count = limits['hold_ns'] // STEP
    require(len(hold) == count and hold[0]['sim_ns'] == lower and
            hold[-1]['sim_ns'] == attach_ns - STEP, 'pre-attach hold interval is incomplete')
    require(all(b['sim_ns'] - a['sim_ns'] == STEP for a, b in zip(hold, hold[1:])),
            'pre-attach hold has a missing physics step')
    require(all(row['step_ns'] == STEP for row in hold), 'pre-attach hold is not 2 ms stepped')
    require(all(row['objects'][object_id]['joint_component'] is False for row in hold),
            'the body was not detached during the declared pre-attach hold')
    observed = {}
    for row in contacts:
        require(row['sim_ns'] not in observed, 'duplicate contact simulation tick')
        observed[row['sim_ns']] = row
    counterparts = set()
    for row in hold + [next((r for r in physics if r['sim_ns'] == attach_ns), None)]:
        require(row is not None, 'no physics sample at the attachment instant')
        contact = observed.get(row['sim_ns'])
        require(contact is not None, 'no contact sample for a pre-attach physics step')
        target = contact['targets'].get(object_id)
        require(target is not None, 'target body is not contact-instrumented')
        result = observation(target)
        require(result['state'] in ('NO_REPORTED_CONTACTS', 'CONTACTS_WITH_FORCE'),
                'target contact state is unavailable during the pre-attach hold')
        for entry in (target.get('contacts') or {}).get('contact', []):
            counterpart = str((entry.get('collision2') or {}).get('name', ''))
            counterparts.add(counterpart)
            require(not counterpart.startswith(limits['parent_model'] + '::'),
                    'arm/body contact observed before attachment: ' + counterpart)
    transforms = [relative_pose(row['parent_pose'], row['objects'][object_id]['pose']) for row in hold]
    spread_m, spread_rad = _spread(transforms)
    require(spread_m <= limits['spread_translation_m'] and spread_rad <= limits['spread_rotation_rad'],
            'the pre-attach hold is not at rest within the declared spread')
    return dict(first_sim_ns=lower, last_sim_ns=attach_ns - STEP, samples=len(hold),
                spread_translation_m=spread_m, spread_rotation_rad=spread_rad,
                counterparts=sorted(counterparts)), _mean_transform(transforms)


def _attached_enforcement(physics, object_id, attach_ns, last_ns, reference, limits):
    attached = [row for row in physics if attach_ns <= row['sim_ns'] <= last_ns]
    require(len(attached) == (last_ns - attach_ns) // STEP + 1,
            'the attached physics interval is incomplete')
    require(all(row['step_ns'] == STEP for row in attached), 'attached interval is not 2 ms stepped')
    require(all(row['objects'][object_id]['joint_component'] is True for row in attached),
            'attachment was missing inside the declared joint interval')
    peak_m = peak_rad = 0.
    for row in attached:
        position, orientation = relative_pose(row['parent_pose'], row['objects'][object_id]['pose'])
        drift_m = math.dist(position, reference[:3])
        drift_rad = rotation_angle(orientation, reference[3:])
        peak_m, peak_rad = max(peak_m, drift_m), max(peak_rad, drift_rad)
        require(drift_m < limits['follow_translation_m'] and drift_rad < limits['follow_rotation_rad'],
                'attached transform drifted from the pre-attach reference')
    jump = relative_pose(attached[0]['parent_pose'], attached[0]['objects'][object_id]['pose'])
    jump_m = math.dist(jump[0], reference[:3])
    jump_rad = rotation_angle(jump[1], reference[3:])
    require(jump_m <= limits['jump_translation_m'] and jump_rad <= limits['jump_rotation_rad'],
            'binding moved the measured pre-attach transform')
    return dict(steps=len(attached), attach_jump_translation_m=jump_m,
                attach_jump_rotation_rad=jump_rad, max_translation_m=peak_m, max_rotation_rad=peak_rad), reference


def _runtime_reference(follow, reference, limits):
    require(follow.get('reference_source') == 'preposition',
            'the runtime session was not anchored on a pre-attach reference')
    evidence = follow.get('preposition') or {}
    runtime = evidence.get('reference')
    require(isinstance(runtime, list) and len(runtime) == 7, 'no runtime pre-attach reference recorded')
    require(evidence.get('samples', 0) >= 5 and evidence.get('window_ns', 0) >= 80_000_000,
            'the runtime pre-attach hold was shorter than declared')
    require(0 <= evidence.get('spread_m', 1) <= limits['spread_translation_m'] and
            0 <= evidence.get('spread_rad', 1) <= limits['spread_rotation_rad'],
            'the runtime pre-attach hold was not at rest')
    agreement = math.dist(runtime[:3], reference[:3])
    require(agreement <= limits['runtime_reference_agreement_m'],
            'runtime and raw-log pre-attach references disagree')
    require(follow.get('attach_jump_translation_m') is not None and
            follow.get('attach_jump_rotation_rad') is not None,
            'the runtime did not measure the attach jump')
    return dict(samples=evidence['samples'], window_ns=evidence['window_ns'],
                spread_translation_m=evidence['spread_m'], spread_rotation_rad=evidence['spread_rad'],
                agreement_m=agreement, contact_freedom=evidence.get('contact_freedom', 'UNRECORDED'))


def verify_run(run, object_id, declaration):
    run = Path(run)
    limits = declaration.get('preposition_gate')
    require(limits == FROZEN, 'preposition thresholds changed or undeclared')
    carry = rows(run / 'skills/carry.jsonl')
    finals = [row for row in carry if row.get('event') == 'follow_final']
    require(len(finals) == 1 and finals[0].get('object') == object_id,
            'ambiguous carried session for the pre-attach reference')
    follow = finals[0]['follow']
    attach_ns = follow['first_sim_ns']
    last_ns = follow['last_sim_ns']
    require(isinstance(attach_ns, int) and isinstance(last_ns, int) and 0 < attach_ns < last_ns,
            'invalid attached interval')
    require(attach_ns % STEP == 0 and last_ns % STEP == 0,
            'attached boundaries do not align to physics steps')
    physics = rows(run / 'physics_steps.jsonl')
    contacts = rows(run / 'contact_steps.jsonl')
    attach_ns, release_ns = _attachment_bounds(_steps(physics), object_id, attach_ns, last_ns)
    hold, reference = _pre_attach_hold(physics, contacts, object_id, attach_ns, limits)
    enforced, reference = _attached_enforcement(physics, object_id, attach_ns, release_ns, reference, limits)
    runtime = _runtime_reference(follow, reference, limits)
    return dict(status='PREPOSITION_REFERENCE_PASS', object=object_id, session=finals[0]['session'],
                preposition_reference=reference, hold=hold, attached=enforced, runtime=runtime,
                signed_target_force_calibrated=False, contact_freedom='RAW_CONTACT_SENSOR_PRE_ATTACH_ONLY',
                default_admission='NO_GO',
                interpretation='Pre-attach, contact-free SE(3) reference enforced over the carry; '
                               'not a success rate, contact-grasp or D3 admission')
