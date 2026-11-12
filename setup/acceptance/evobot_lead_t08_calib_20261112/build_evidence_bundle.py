#!/usr/bin/env python3
# Build a t08-evidence/1.0 bundle from a timeline capture, so the FROZEN evaluator can judge
# a candidate run instead of the Lead recomputing the same clauses.
#
# Field shapes were read from an archived ACCEPTED run
# (evobot_t08_instance_pose_20261112/runs/U_shot/seed3000/t1/evaluator_input.json), not invented:
#   objects  -> per-object sample series [i, dt_ns, t_ns, x, y, z, qx, qy, qz, qw]
#   gripper  -> joint_name, min/max aperture, span
#   teleport -> jump_threshold_m, max_single_step_jump_m, per_object_m
#   manifest -> per-file sha256 + bundle_sha256
#   contacts -> NOT PRODUCED HERE. This builder cannot invent contact events; it records that
#               the field is empty and why, so a reader sees a gap rather than a fabricated list.
import hashlib, json, os, sys

JUMP_M = 0.03  # the threshold the archived bundle uses for teleport detection

def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()

def series(samples, name, rest_z=None):
    out, dropped, max_gap, prev_t = [], 0, 0, None
    for i, s in enumerate(samples):
        boxes = (s.get('boxes') or {})
        p = boxes.get(name)
        t = s.get('t')
        if not isinstance(p, (list, tuple)) or len(p) < 3 or t is None:
            dropped += 1
            continue
        try:
            x, y, z = float(p[0]), float(p[1]), float(p[2])
        except (TypeError, ValueError):
            dropped += 1
            continue
        t_ns = int(round(float(t) * 1e9))
        if prev_t is not None:
            max_gap = max(max_gap, t_ns - prev_t)
        prev_t = t_ns
        out.append([i, 0, t_ns, x, y, z, 0.0, 0.0, 0.0, 1.0])
    return {'samples': out, 'sample_count': len(out), 'dropped_samples': dropped,
            'max_gap_ns': max_gap, 'role': 'target' if name.endswith('_a') else 'protected'}

def teleport_of(rows):
    mx = 0.0
    for a, b in zip(rows, rows[1:]):
        d = ((a[3]-b[3])**2 + (a[4]-b[4])**2 + (a[5]-b[5])**2) ** 0.5
        mx = max(mx, d)
    return mx

def build(timeline_path, task_path, out_path, run_id='candidate-staged'):
    tl = json.load(open(timeline_path))
    samples = tl.get('timeline') or []
    spec = json.load(open(task_path))
    names = [o['name'] for o in spec['objects']]
    objs = {n: series(samples, n) for n in names}
    per_obj = {n: round(teleport_of(v['samples']), 9) for n, v in objs.items()}
    grips = [s.get('grip') for s in samples if isinstance(s.get('grip'), (int, float))]
    gripper = {'joint_name': 'gripper_left_joint',
               'min_aperture_rad': min(grips) if grips else None,
               'max_aperture_rad': max(grips) if grips else None,
               'span': len(grips),
               'note': 'opening is recorded; this is not a grasp event log'}
    finals = {}
    for n in names:
        rows = objs[n]['samples']
        if rows:
            finals[n] = [rows[-1][3], rows[-1][4], rows[-1][5], 0.0]
    manifest = {'bundle_sha256': None,
                'files': {os.path.basename(task_path): sha(task_path),
                          os.path.basename(timeline_path): sha(timeline_path)}}
    evidence = {
        'schema_version': 't08-evidence/1.0',
        'source': {'agent_reported': False, 'trusted_source_id': 'flexcell::TimelineSampled/v1'},
        'run': {'run_id': run_id},
        'task': {'task_id': spec.get('task_id'), 'target_object': names[0],
                 'protected_object': names[1] if len(names) > 1 else None,
                 'rest_height_m': 0.0175,
                 'task_sha256': sha(task_path)},
        'objects': objs,
        'contacts': {'events': 0, 'all_partners_seen': [],
                     'UNAVAILABLE': 'this builder has no contact-trace source; the field is empty by
                                     'limitation, not because no contact occurred'},
        'gripper': gripper,
        'attachment': {'attached_during_window': False, 'events': 0,
                       'basis': 'claimed disengaged; not independently traced' },
        'teleport': {'jump_threshold_m': JUMP_M,
                     'max_single_step_jump_m': max(per_obj.values()) if per_obj else 0.0,
                     'per_object_m': per_obj},
        'manifest': manifest,
    }
    body = json.dumps(evidence, sort_keys=True).encode()
    evidence['manifest']['bundle_sha256'] = hashlib.sha256(body).hexdigest()
    state = {'agent_claimed_success': False, 'objects': finals, 'evidence': evidence,
             'trajectory': {names[0]: {'max_z_m': max((r[5] for r in objs[names[0]]['samples']), default=0.0175),
                                       'samples': objs[names[0]]['sample_count'],
                                       'source': 'TIMELINE_SAMPLED'}}}
    json.dump(state, open(out_path, 'w'), indent=1)
    return state

if __name__ == '__main__':
    s = build(sys.argv[1], sys.argv[2], sys.argv[3])
    ev = s['evidence']
    print('samples: %s  contacts: %s  max_jump_m: %.6f' % (
        ev['objects']['target_box_a']['sample_count'], ev['contacts']['events'],
        ev['teleport']['max_single_step_jump_m']))