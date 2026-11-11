#!/usr/bin/env python3
"""Generate T08 push task instances.

WHY THIS TASK QUALIFIES AS A NEW CAPABILITY (P1 requirement: say why before testing)
  Pick-and-place cannot satisfy it. The box must END UP displaced along a commanded direction
  WITHOUT being lifted: the evaluator requires horizontal displacement inside a band AND a
  vertical displacement near zero. A grasp-and-carry fails the vertical bound, and doing nothing
  fails the displacement bound. The capability that is missing is sustained contact pushing, which
  no existing skill provides -- RunComposite could only express pick-and-place.

DEV vs HELD APART FROM THE START
  Instances 2000-2002 are the development set: they may be used to tune the skill.
  Instances 3000-3002 are written now but must NOT be run until the skill implementation is frozen.
  Putting them in the same file forces the split to be visible rather than remembered. The mission
  forbids reintroducing a task used for development as independent held-out data, and the cheapest
  way to violate that is to forget which is which.

THE 30 mm MINIMUM IS NOT NEGOTIABLE HERE
  It was frozen in the Step 0 pre-registration before any run. Step 0 measured 23.02 mm and was
  ruled NOT_FEASIBLE against this threshold. Lowering it now would convert a real capability gap
  into a manufactured success.
"""
import hashlib
import json
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[1]

BOX = [0.035, 0.035, 0.035]
REST_Z = 0.0175


def instance(seed, box_a_xy, box_b_xy, zone_xy, direction, split):
    spec = {
        'task_id': 'T08-push-seed%d' % seed,
        'template_id': 'T08_push_manipulation',
        'random_seed': seed,
        'instruction': ('Push the red block into the marked zone without picking it up. '
                        'Do not move the blue block.'),
        'objects': [
            {'name': 'target_box_a', 'size': BOX, 'color': 'red',
             'initial_pose': [box_a_xy[0], box_a_xy[1], REST_Z, 0.0]},
            {'name': 'target_box_b', 'size': BOX, 'color': 'blue',
             'initial_pose': [box_b_xy[0], box_b_xy[1], REST_Z, 0.0]},
        ],
        'zones': [{'name': 'zone_push', 'pose': [zone_xy[0], zone_xy[1], REST_Z],
                   'radius': 0.06}],
        'constraints': {'order': [], 'must_not_move': ['target_box_b']},
        'expected_goal': {
            'push': {
                'target_box_a': {
                    'min_displacement_m': 0.030,
                    'max_displacement_m': 0.150,
                    'max_vertical_m': 0.020,
                    'direction': direction,
                    'min_direction_cosine': 0.9,
                    'zone': 'zone_push',
                }
            },
            'unmoved': ['target_box_b'],
        },
        'evaluator_version': '0.3.0',
        'execution_budget': {'max_steps': 40, 'max_wall_s': 600.0},
        'split': split,
    }
    body = json.dumps(spec, sort_keys=True, separators=(',', ':'))
    spec['instance_sha256'] = hashlib.sha256(body.encode('utf-8')).hexdigest()
    return spec


DEV = [
    (2000, (0.22, 0.0), (0.20, -0.18), (0.16, 0.0), [-1.0, 0.0]),
    (2001, (0.20, 0.06), (0.20, -0.22), (0.14, 0.06), [-1.0, 0.0]),
    (2002, (0.24, -0.05), (0.20, -0.20), (0.18, -0.05), [-1.0, 0.0]),
]

# UNSEEN. Generated now so the protocol is fixed, not run until the skill is frozen.
HELD = [
    (3000, (0.21, 0.03), (0.20, -0.21), (0.15, 0.03), [-1.0, 0.0]),
    (3001, (0.23, -0.07), (0.20, -0.19), (0.17, -0.07), [-1.0, 0.0]),
    (3002, (0.19, 0.02), (0.20, -0.23), (0.13, 0.02), [-1.0, 0.0]),
]


def write(rows, split, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    for seed, a, b, z, d in rows:
        spec = instance(seed, a, b, z, d, split)
        p = outdir / (spec['task_id'] + '.json')
        p.write_text(json.dumps(spec, indent=2) + '\n', encoding='utf-8')
        print('wrote', p.relative_to(WT))


def main():
    write(DEV, 'train', WT / 'benchmark' / 'tasks' / 't08_dev')
    write(HELD, 't08_unseen', WT / 'benchmark' / 'tasks' / 't08_unseen')
    print('3 dev instances (may be used to tune) + 3 unseen (must not be run until frozen)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
