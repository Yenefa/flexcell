#!/usr/bin/env python3
"""Build an evidence bundle from the step logs the Gazebo plugins write.

WHY IT READS PLUGIN LOGS AND NOT A ROS TOPIC
    The plugins run INSIDE the physics loop: PhysicsTrace and ContactTrace write
    one record per physics step, before any transport or scheduling delay. A ROS
    subscription samples whatever happens to arrive, drops what the middleware
    drops, and cannot tell you how much it dropped. For a verdict that must
    prove the object was never lifted, "we sampled it a lot" is not the same as
    "we saw every step", and only the step log can honestly claim the latter.

WHY THE DROPPED-SAMPLE COUNT IS REAL AND NOT DECORATION
    The recorder reads the log once, after the fact, so it cannot drop samples
    itself. What it CAN do is count the sequence gaps the writer left, and
    report them. A run whose log has holes must not silently look complete: the
    verifier rejects on a sequence gap, and this recorder's job is to make that
    gap visible rather than to smooth it away.

WHY THE CONTACT INTERVALS ARE DERIVED, NOT COPIED
    ContactTrace writes a per-step snapshot per watched model. An "interval" is
    a run of consecutive steps in which a given partner collided. Deriving the
    intervals here means the verifier receives a claim it can check against the
    samples, instead of a summary it has to trust.
"""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

try:
    from . import schema
except ImportError:
    import schema


def _read_jsonl(path):
    records = []
    with open(path, encoding='utf-8') as stream:
        for number, line in enumerate(stream, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except ValueError as exc:
                raise SystemExit('%s:%d is not valid JSON: %s' % (path, number, exc))
    return records


def trajectory_from_physics(records, model):
    """Per-step 7-DOF pose for one model, with a strict sequence number.

    PhysicsTrace writes 'objects' as {name: {pose: [x,y,z,qx,qy,qz,qw],
    joint_component: bool}}. A missing model in a record is a real gap: it means
    the entity could not be resolved that step, so the sample is absent and the
    sequence must show it.
    """
    samples = []
    dropped = 0
    previous_sim = None
    max_gap = 0
    for sequence, record in enumerate(records):
        objects = record.get('objects') or {}
        entry = objects.get(model)
        if not isinstance(entry, dict):
            dropped += 1
            continue
        pose = entry.get('pose')
        if not isinstance(pose, list) or len(pose) != 7:
            dropped += 1
            continue
        if not all(isinstance(v, (int, float)) and math.isfinite(float(v))
                   for v in pose):
            dropped += 1
            continue
        sim_ns = int(record.get('sim_ns', 0))
        mono_ns = int(record.get('monotonic_ns', 0))
        if previous_sim is not None:
            max_gap = max(max_gap, sim_ns - previous_sim)
        previous_sim = sim_ns
        samples.append([sequence, sim_ns, mono_ns]
                       + [round(float(v), 9) for v in pose])
    return samples, dropped, max_gap


# Issue #239. An interval is a HALF-OPEN span [start_sim_ns, end_sim_ns): it covers
# every physics step from the first contact step through the last one, and end_sim_ns is the
# instant the LAST step ENDS, not the instant it begins.
#
# WHY THIS MATTERS: ContactTrace writes one snapshot per physics step. A single-frame contact
# is a real event lasting exactly one step. The old derivation wrote start == end for it, and
# schema.py:219 rejects end <= start as an "empty or inverted interval" - so a real single-frame
# contact was being reported as invalid evidence. Two such intervals in CI_L0 left that control
# without a complete independent verdict (#239).
#
# THE DURATION IS NOT INVENTED. Every contact record carries its own step_ns, the real physics
# step duration the plugin wrote. A one-step contact therefore spans [sim_ns, sim_ns + step_ns).
# No event is dropped, no threshold is loosened, and schema.py is NOT modified - the frozen rule
# stays exactly as it was; the recorder now emits the interval the rule was written to describe.
CONTACT_INTERVAL_REPRESENTATION = "half_open_per_physics_step_v2"


def contact_intervals(contact_records, model, pusher_links):
    """Runs of consecutive steps in which the model touched a declared pusher.

    Returns (intervals, component_present_ever, other_partners_seen).

    component_present is tracked separately because ContactTrace distinguishes
    "no contact" from "the contact component was not there". A run whose
    component was never present has no contact evidence at all, which the
    verifier treats as unevaluable rather than as a clean bill of health.

    Each returned interval is a half-open span: end_sim_ns is the END of the last
    contact step, i.e. last_sim_ns + step_ns. The step duration comes from the
    contact record itself, so a single-frame contact has a real, non-zero span.
    """
    intervals = []
    open_interval = None
    present = False
    partners = set()
    for record in contact_records:
        target = (record.get('targets') or {}).get(model)
        if not isinstance(target, dict):
            continue
        if target.get('component_present'):
            present = True
        sim_ns = int(record.get('sim_ns', 0))
        # Real physics-step duration from the plugin's own record (5 ms in the archived
        # runs). Used to give single-frame contacts a non-zero, non-invented span.
        step_ns = int(record.get('step_ns') or 0)
        touching = set()
        payload = target.get('contacts')
        if isinstance(payload, dict):
            for contact in payload.get('contact') or []:
                for key in ('collision1', 'collision2'):
                    name = ((contact.get(key) or {}).get('name') or '')
                    if not name:
                        continue
                    partners.add(name)
                    # The partner that is not the watched model itself.
                    if not name.startswith(model + '::'):
                        touching.add(name)
        hit = sorted(touching & set(pusher_links))
        if hit:
            # end is the END of this step, not its start. Resolving it at close time below
            # keeps the half-open semantics explicit even for a one-step contact.
            step_end = sim_ns + step_ns
            if open_interval is None:
                open_interval = {'start_sim_ns': sim_ns, 'end_sim_ns': step_end,
                                 'other': hit[0], '_last_step_end': step_end}
            else:
                open_interval['end_sim_ns'] = step_end
                open_interval['_last_step_end'] = step_end
        elif open_interval is not None:
            open_interval.pop('_last_step_end', None)
            intervals.append(open_interval)
            open_interval = None
    if open_interval is not None:
        open_interval.pop('_last_step_end', None)
        intervals.append(open_interval)
    return intervals, present, sorted(partners)


def gripper_span(joint_records, joint_name):
    """Aperture over time, from /joint_states records."""
    span = []
    for record in joint_records:
        names = record.get('name') or []
        positions = record.get('position') or []
        if joint_name not in names:
            continue
        index = names.index(joint_name)
        if index >= len(positions):
            continue
        value = positions[index]
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            span.append([int(record.get('monotonic_ns', 0)), float(value)])
    return span


def build(args):
    physics = _read_jsonl(args.physics_log)
    contacts = _read_jsonl(args.contact_log) if args.contact_log else []
    joints = _read_jsonl(args.joint_log) if args.joint_log else []

    target = args.target
    protected = args.protected
    if not physics:
        raise SystemExit('physics step log is empty; there is no evidence to record')

    objects = {}
    for name, role in ((target, 'target'), (protected, 'protected')):
        samples, dropped, gap = trajectory_from_physics(physics, name)
        objects[name] = {
            'role': role,
            'samples': samples,
            'sample_count': len(samples),
            'dropped_samples': dropped,
            'max_gap_ns': max(gap, 1),
        }

    intervals, present, partners = contact_intervals(
        contacts, target, args.pusher_links)

    sims = [int(r.get('sim_ns', 0)) for r in physics]
    monos = [int(r.get('monotonic_ns', 0)) for r in physics]

    # Largest single-step xy jump, per object, from the samples themselves.
    jumps = {}
    for name, entry in objects.items():
        best = 0.0
        positions = [(s[3], s[4]) for s in entry['samples']]
        for index in range(1, len(positions)):
            best = max(best, math.hypot(positions[index][0] - positions[index - 1][0],
                                        positions[index][1] - positions[index - 1][1]))
        jumps[name] = round(best, 9)

    task_sha = schema.sha256_file(args.task)
    bundle = {
        'schema_version': schema.SCHEMA_VERSION,
        'task': {
            'task_id': args.task_id,
            'task_sha256': task_sha,
            'target_object': target,
            'protected_object': protected,
            'rest_height_m': float(args.rest_height),
        },
        'run': {
            'run_id': args.run_id,
            'execution_window': {
                'start_sim_ns': min(sims),
                'end_sim_ns': max(sims),
                'start_mono_ns': min(monos),
                'end_mono_ns': max(monos),
            },
        },
        'source': {
            'trusted_source_id': 'flexcell::PhysicsTrace/v1',
            'agent_reported': False,
        },
        'objects': objects,
        'contacts': {
            'trusted_source_id': 'flexcell::ContactTrace/v1',
            'pusher_links': list(args.pusher_links),
            'component_present': bool(present),
            # Issue #239: version the interval semantics so a re-evaluation of historical
            # bundles can be labelled as such and never silently overwrites the original
            # verdict. A bundle without this field is a v1 recording and keeps its old
            # verdict; only a re-run through this recorder produces v2 intervals.
            'interval_representation': CONTACT_INTERVAL_REPRESENTATION,
            'intervals': intervals,
            'all_partners_seen': partners,
        },
        'gripper': {
            'joint_name': args.gripper_joint,
            'min_aperture_rad': (min(v for _t, v in gripper_span(joints, args.gripper_joint))
                                 if gripper_span(joints, args.gripper_joint) else 0.0),
            'max_aperture_rad': (max(v for _t, v in gripper_span(joints, args.gripper_joint))
                                 if gripper_span(joints, args.gripper_joint) else 0.0),
            'span': gripper_span(joints, args.gripper_joint),
        },
        'attachment': {
            # PhysicsTrace records joint_component per object per step; any true
            # value means the arm was physically attached to the object.
            'attached_during_window': any(
                (r.get('objects') or {}).get(name, {}).get('joint_component')
                for r in physics for name in (target, protected)),
            'events': sum(1 for r in physics
                          for name in (target, protected)
                          if (r.get('objects') or {}).get(name, {}).get('joint_component')),
        },
        'teleport': {
            'max_single_step_jump_m': max(jumps.values()) if jumps else 0.0,
            'jump_threshold_m': 0.030,
            'per_object_m': jumps,
        },
        'manifest': {'files': {}},
    }
    for path in (args.physics_log, args.contact_log, args.joint_log, args.task):
        if path and Path(path).is_file():
            bundle['manifest']['files'][Path(path).name] = schema.sha256_file(path)
    bundle['manifest']['bundle_sha256'] = schema.bundle_sha256(bundle)
    return bundle


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--physics-log', required=True)
    parser.add_argument('--contact-log', default=None)
    parser.add_argument('--joint-log', default=None)
    parser.add_argument('--task', required=True)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--protected', required=True)
    parser.add_argument('--rest-height', type=float, required=True)
    parser.add_argument('--pusher-links', nargs='+', required=True)
    parser.add_argument('--gripper-joint', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args(argv)

    bundle = build(args)
    problems = schema.validate(bundle)
    Path(args.out).write_text(
        json.dumps(bundle, indent=2, sort_keys=True, allow_nan=False) + '\n',
        encoding='utf-8')
    print(json.dumps({
        'ok': not problems,
        'out': args.out,
        'samples': {name: entry['sample_count']
                    for name, entry in bundle['objects'].items()},
        'dropped': {name: entry['dropped_samples']
                    for name, entry in bundle['objects'].items()},
        'contact_intervals': len(bundle['contacts']['intervals']),
        'component_present': bundle['contacts']['component_present'],
        'problems': problems,
    }))
    return 0 if not problems else 1


if __name__ == '__main__':
    sys.exit(main())
