#!/usr/bin/env python3
"""Prove the six unseen trials ran the DEV world, not their declared initial poses.

Reads world.sdf spawn poses, the unseen specs, and ground truth.
REFUSES loudly if any pose cannot be parsed -- an earlier regex version silently found nothing
and printed 'offsets are negligible', which would have retracted the wrong conclusion.
No simulator, no model calls.
"""
import json
import math
import os
import re
import sys


def find_repo_root(start):
    cur = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(cur, 'benchmark', 'tasks')):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            raise SystemExit('REFUSED: repo root not found above %s' % start)
        cur = parent


REPO = find_repo_root(os.path.dirname(os.path.abspath(__file__)))
EVID = os.path.join(REPO, 'setup', 'acceptance', 'evobot_t08_evidence_loop_20261112', 'evidence')
SEEDS = ['seed3000', 'seed3001', 'seed3002']
ARMS = ['U', 'U_shot']


def spawn_pose(world_path, model):
    """Return (x, y) of the first <pose> inside <model name=model>, or raise."""
    lines = open(world_path).read().splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.search(r'<model\s+name="%s"\s*>' % re.escape(model), line):
            start = i
            break
    if start is None:
        raise SystemExit('REFUSED: model %s not found in %s' % (model, world_path))
    for line in lines[start:start + 8]:
        m = re.search(r'<pose>\s*([-0-9.eE+]+)\s+([-0-9.eE+]+)', line)
        if m:
            return float(m.group(1)), float(m.group(2))
    raise SystemExit('REFUSED: no <pose> within 8 lines of model %s in %s' % (model, world_path))


def main():
    rows = []
    for seed in SEEDS:
        spec_path = os.path.join(REPO, 'benchmark', 'tasks', 't08_unseen', 'T08-push-%s.json' % seed)
        if not os.path.exists(spec_path):
            raise SystemExit('REFUSED: missing unseen spec %s' % spec_path)
        spec = json.load(open(spec_path))
        spec_xy = {o['name']: (o['initial_pose'][0], o['initial_pose'][1]) for o in spec['objects']}
        for arm in ARMS:
            trial = os.path.join(EVID, arm, seed, 't1')
            world = os.path.join(trial, 'sim', 'world.sdf')
            if not os.path.exists(world):
                raise SystemExit('REFUSED: missing world %s' % world)
            a_xy = spawn_pose(world, 'target_box_a')
            b_xy = spawn_pose(world, 'target_box_b')
            gb_p = os.path.join(trial, 'gt_before.json')
            ga_p = os.path.join(trial, 'gt_after.json')
            b_move = a_move = None
            if os.path.exists(gb_p) and os.path.exists(ga_p):
                gb = json.load(open(gb_p))['objects']
                ga = json.load(open(ga_p))['objects']
                a0, a1 = gb['target_box_a'], ga['target_box_a']
                b0, b1 = gb['target_box_b'], ga['target_box_b']
                a_move = math.hypot(a1[0] - a0[0], a1[1] - a0[1]) * 1000
                b_move = math.hypot(b1[0] - b0[0], b1[1] - b0[1])
            rows.append((seed, arm, spec_xy, a_xy, b_xy, a_move, b_move))

    print('%-9s %-7s %-20s %-20s %-11s %-11s' %
          ('seed', 'arm', 'spec A xy', 'world A xy', 'offset_mm', 'B moved_m'))
    print('-' * 84)
    worst = 0.0
    b_max = 0.0
    for seed, arm, spec_xy, a_xy, b_xy, a_move, b_move in rows:
        sx, sy = spec_xy['target_box_a']
        off = math.hypot(sx - a_xy[0], sy - a_xy[1]) * 1000
        worst = max(worst, off)
        b_max = max(b_max, b_move or 0.0)
        print('%-9s %-7s %-20s %-20s %11.3f %11.6f' %
              (seed, arm, '(%.3f, %.3f)' % (sx, sy), '(%.3f, %.3f)' % a_xy, off, b_move or 0.0))

    print()
    print('largest spec-vs-world offset : %.3f mm' % worst)
    print('largest blue-block movement  : %.6f m' % b_max)
    print()
    if worst < 1.0:
        print('VERDICT: worlds matched the unseen specs; the original finding would stand.')
        return 1
    print('VERDICT: the worlds did NOT match the unseen specs -> six trials are INVALID_INFRA.')
    if b_max < 1e-6:
        print('         The blue block never moved, so unmoved:target_box_b failures were the')
        print('         spec-vs-world spawn offset, NOT robot motion.')
    print('         No generalisation measurement exists; "0/6 unseen" is retracted.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
