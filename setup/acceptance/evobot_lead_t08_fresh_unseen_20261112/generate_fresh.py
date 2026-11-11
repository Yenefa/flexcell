#!/usr/bin/env python3
"""Generate FRESH unseen T08 instances, then freeze them before any run.

WHY FRESH ONES ARE REQUIRED
    Round 8 measured one push at contact_height_m = 0.0175 on the DEV instance seed2000 and it
    satisfied all four sub-clauses of the push criterion. That is Simulation Tested at n = 1 on a
    tuning instance - it is not evidence of generalisation.

    The original unseen seeds 3000-3002 cannot be reused for a claim either: they were already run
    during the evidence loop, and the mission forbids reintroducing a task used for development as
    independent held-out data. So a generalisation statement needs instances that did not exist
    before the configuration was fixed.

WHAT THIS DOES
    1. Emits six new instances (seeds 4000-4005) with the SAME structure, thresholds and evaluator
       version as the frozen generator, varying only the geometry - exactly as generate_t08.py does.
    2. Writes a sha256 manifest so the instances are frozen by hash BEFORE the first run.
    3. Refuses to overwrite an existing manifest: a set that has been run must not be silently
       regenerated to look better.

    It does not modify benchmark/generate_t08.py, the existing dev or unseen specs, or any threshold.
"""
import hashlib
import json
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
# V2: the first attempt varied the BLOCK position and was thrown away before any run, because
# /home/ros/flexcell-p14/scripts/sim_profile.py always spawns target_box_a at (0.22, 0.0) - it
# can place zone_2 but not an arbitrary box pose. Six instances whose world did not match their
# spec would have graded against the wrong zone. So this set varies the ZONE only and keeps the
# block where the simulator actually puts it, and the claim it supports is correspondingly narrower.
OUT = WT / 'benchmark' / 'tasks' / 't08_fresh_zone_20261112'
MANIFEST = OUT / 'freeze_manifest.json'

BOX = [0.035, 0.035, 0.035]
REST_Z = 0.0175

# Block stays at the simulator's spawn pose (0.22, 0.0). The zone moves, so required travel varies.
# Required travel = (0.22 - zone_x) - 0.06, and it must also clear the frozen 0.030 m minimum.
ROWS = [
    (5000, (0.22, 0.0), (0.20, -0.18), (0.14, 0.0), [-1.0, 0.0]),   # needs >= 0.020 -> 0.030 binds
    (5001, (0.22, 0.0), (0.20, -0.18), (0.13, 0.0), [-1.0, 0.0]),   # needs >= 0.030
    (5002, (0.22, 0.0), (0.20, -0.18), (0.12, 0.0), [-1.0, 0.0]),   # needs >= 0.040
    (5003, (0.22, 0.0), (0.20, -0.18), (0.11, 0.0), [-1.0, 0.0]),   # needs >= 0.050
    (5004, (0.22, 0.0), (0.20, -0.18), (0.10, 0.0), [-1.0, 0.0]),   # needs >= 0.060
    (5005, (0.22, 0.0), (0.20, -0.18), (0.09, 0.0), [-1.0, 0.0]),   # needs >= 0.070
]

WHY = ('frozen by sha256 before the first run, so instances cannot be swapped for ones that '
       'score better after seeing results')


def instance(seed, box_a, box_b, zone, direction):
    spec = {
        'task_id': 'T08-push-seed%d' % seed,
        'template_id': 'T08_push_manipulation',
        'random_seed': seed,
        'instruction': ('Push the red block into the marked zone without picking it up. '
                        'Do not move the blue block.'),
        'objects': [
            {'name': 'target_box_a', 'size': BOX, 'color': 'red',
             'initial_pose': [box_a[0], box_a[1], REST_Z, 0.0]},
            {'name': 'target_box_b', 'size': BOX, 'color': 'blue',
             'initial_pose': [box_b[0], box_b[1], REST_Z, 0.0]},
        ],
        'zones': [{'name': 'zone_push', 'pose': [zone[0], zone[1], REST_Z], 'radius': 0.06}],
        'constraints': {'order': [], 'must_not_move': ['target_box_b']},
        'expected_goal': {
            'push': {'target_box_a': {
                'min_displacement_m': 0.030,
                'max_displacement_m': 0.150,
                'max_vertical_m': 0.020,
                'direction': direction,
                'min_direction_cosine': 0.9,
                'zone': 'zone_push'}},
            'unmoved': ['target_box_b'],
        },
        'evaluator_version': '0.3.0',
        'execution_budget': {'max_steps': 40, 'max_wall_s': 600.0},
        'split': 't08_fresh_20261112',
    }
    body = json.dumps(spec, sort_keys=True, separators=(',', ':'))
    spec['instance_sha256'] = hashlib.sha256(body.encode('utf-8')).hexdigest()
    return spec


def main():
    if MANIFEST.exists():
        print('REFUSED: %s already exists.' % MANIFEST.relative_to(WT))
        print('  This instance set has been frozen. Regenerating it after a run would replace')
        print('  instances that were measured with ones that might score better. If a new set is')
        print('  genuinely needed, use new seeds and a new directory.')
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for seed, a, b, z, d in ROWS:
        spec = instance(seed, a, b, z, d)
        p = OUT / (spec['task_id'] + '.json')
        p.write_text(json.dumps(spec, indent=2) + '\n', encoding='utf-8')
        manifest[spec['task_id']] = spec['instance_sha256']
        print('wrote %-46s sha=%s' % (p.name, spec['instance_sha256'][:16]))
    doc = {'record_kind': 'T08_FRESH_INSTANCE_FREEZE', 'why': WHY, 'instances': manifest}
    MANIFEST.write_text(json.dumps(doc, indent=2) + '\n', encoding='utf-8')
    print()
    print('frozen: %d instances -> %s' % (len(manifest), MANIFEST.relative_to(WT)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
