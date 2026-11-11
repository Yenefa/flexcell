#!/usr/bin/env python3
"""Count training instances whose placement clauses are already satisfied at t=0.

Reads benchmark/tasks/train/*.json only. No simulator, no model calls.
A clause is free when the target object's initial XY is within the zone radius of the
zone centre -- i.e. the evaluator would score it as passed before the robot moves.
"""
import glob
import json
import math
import os
import sys

# Resolve the repo root by walking up until benchmark/tasks/train exists.
# A hardcoded relative hop silently found nothing once, and 'nothing' printed as
# 'train instances: 0' -- which reads like a clean result. Fail loudly instead.
def find_repo_root(start):
    cur = os.path.abspath(start)
    while True:
        candidate = os.path.join(cur, 'benchmark', 'tasks', 'train')
        if os.path.isdir(candidate):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            raise SystemExit('REFUSED: benchmark/tasks/train not found above %s' % start)
        cur = parent


REPO = find_repo_root(os.path.dirname(os.path.abspath(__file__)))
TASKS = os.path.join(REPO, 'benchmark', 'tasks', 'train')


def scan(task_path):
    spec = json.load(open(task_path))
    zones = {z['name']: z['pose'] for z in spec.get('zones', [])}
    radii = {z['name']: z['radius'] for z in spec.get('zones', [])}
    placement = spec.get('expected_goal', {}).get('placement') or {}
    start = {o['name']: o['initial_pose'] for o in spec.get('objects', [])}
    free, need = [], []
    for name, zone in placement.items():
        if name not in start or zone not in zones:
            continue
        p, z, r = start[name], zones[zone], radii[zone]
        d = math.hypot(p[0] - z[0], p[1] - z[1])
        (free if d <= r else need).append(
            {'object': name, 'zone': zone, 'distance_m': round(d, 5),
             'radius_m': r, 'margin_m': round(r - d, 5)})
    return spec['task_id'], placement, free, need


def main():
    paths = sorted(glob.glob(os.path.join(TASKS, '*.json')))
    if not paths:
        raise SystemExit('REFUSED: no task specs under %s' % TASKS)
    total = vacuous = partial = 0
    rows = []
    for path in paths:
        task_id, placement, free, need = scan(path)
        if not placement:
            continue
        total += 1
        if free and not need:
            vacuous += 1
            rows.append((task_id, 'VACUOUS', free))
        elif free:
            partial += 1
            rows.append((task_id, 'PARTIAL', free))
    print('scanned %d task specs under %s' % (len(paths), TASKS))
    print('train instances with a placement clause: %d' % total)
    print('fully vacuous (every placement clause satisfied at t0): %d' % vacuous)
    print('partially vacuous (>=1 free clause): %d' % partial)
    print()
    print('%-24s %-9s %s' % ('task', 'class', 'free clauses (object, zone, distance, radius, margin)'))
    for task_id, klass, free in rows:
        print('%-24s %-9s %s' % (task_id, klass,
                                 [(f['object'], f['zone'], f['distance_m'],
                                   f['radius_m'], f['margin_m']) for f in free]))
    if total == 0:
        raise SystemExit('REFUSED: scanned %d specs but none had a placement clause' % len(paths))
    return 0


if __name__ == '__main__':
    sys.exit(main())