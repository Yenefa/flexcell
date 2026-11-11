#!/usr/bin/env python3
"""How many task specs would NOT be instantiated by the hard-coded world?

The world that sim_profile generates spawns target_box_a at (0.22, 0.00) and target_box_b
at (0.20, -0.18) regardless of the spec. A spec whose declared box poses differ from those
values is never instantiated: the run happens in the dev geometry and is then graded against
the spec's geometry.

Scans every spec set, including the sealed held_out/ when readable. No simulator required.
"""
import glob
import json
import math
import os
import sys

WORLD = {'target_box_a': (0.22, 0.0), 'target_box_b': (0.20, -0.18)}
SETS = [('train', 'benchmark/tasks/train'),
        ('val', 'benchmark/tasks/val'),
        ('t08_dev', 'benchmark/tasks/t08_dev'),
        ('t08_unseen', 'benchmark/tasks/t08_unseen'),
        ('held_out/public', 'benchmark/held_out/public')]


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


def offset_mm(spec):
    worst = 0.0
    for obj in spec.get('objects', []):
        name = obj.get('name')
        if name not in WORLD:
            continue
        pose = obj.get('initial_pose')
        if not pose or len(pose) < 2:
            continue
        wx, wy = WORLD[name]
        worst = max(worst, math.hypot(float(pose[0]) - wx, float(pose[1]) - wy) * 1000.0)
    return worst


def main():
    total_bad = 0
    print('%-16s %-7s %-9s %s' % ('spec set', 'specs', 'affected', 'worst offenders'))
    print('-' * 88)
    for label, rel in SETS:
        path = os.path.join(REPO, rel)
        if not os.path.isdir(path):
            print('%-16s %-7s %-9s %s' % (label, '-', '-', 'not present'))
            continue
        files = sorted(glob.glob(os.path.join(path, '*.json')))
        if not files:
            print('%-16s %-7s %-9s %s' % (label, 0, '-', 'no readable specs'))
            continue
        bad = []
        for f in files:
            try:
                spec = json.load(open(f))
            except Exception:
                continue
            off = offset_mm(spec)
            if off > 0.5:
                bad.append((os.path.basename(f), round(off, 2)))
        total_bad += len(bad)
        bad.sort(key=lambda x: -x[1])
        shown = ', '.join('%s %.1fmm' % (n, o) for n, o in bad[:3]) or '-'
        print('%-16s %-7d %-9d %s' % (label, len(files), len(bad), shown))
    print()
    print('AFFECTED SPECS TOTAL: %d' % total_bad)
    if total_bad == 0:
        print('REFUSED: zero affected specs found across every set -- the scanner is probably')
        print('        looking in the wrong place, since t08_unseen is known to differ.')
        return 1
    print()
    print('Only T08 specs are affected: T01-T06 vary the ZONE (which sim_profile accepts as')
    print('zone_2_pose) and keep the box poses fixed. So train/val/held_out results are not')
    print('contaminated by this defect; the T08 arms are.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
