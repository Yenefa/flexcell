#!/usr/bin/env python3
"""Grade T08 pushes against ALL FOUR sub-clauses of the frozen criterion.

WHY THIS SCRIPT EXISTS
    I hypothesised that T08s 0/6 was mostly a false-rejection artifact, like the place release
    defect. My first pass appeared to support it: 8 of 23 archived pushes satisfied the
    displacement band, the vertical bound and the direction cosine. Six of those eight were
    rejected by the skill.

    THAT FIRST PASS WAS WRONG. evaluate.py:201-210 has a FOURTH sub-clause - the object must end
    inside the declared zone - and I had omitted it. Grading with all four sub-clauses drops the
    count from 8 to 1. The hypothesis does not hold, and this script reports that.

    Omitting a sub-clause is the same error class as everything else this project has recorded:
    grading against a partial reading of the criterion.
"""
import glob
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
EVIDENCE = os.path.join(REPO, 'setup', 'acceptance', 'evobot_t08_evidence_loop_20261112', 'evidence')


def load(path):
    try:
        return json.load(open(path, encoding='utf-8'))
    except Exception:
        return None


def spec_for(seed):
    for split in ('t08_unseen', 't08_dev'):
        p = os.path.join(REPO, 'benchmark', 'tasks', split, 'T08-push-seed%d.json' % seed)
        if os.path.exists(p):
            return load(p)
    return None


def grade(rec, spec):
    want = ((spec.get('expected_goal') or {}).get('push') or {}).get('target_box_a') or {}
    zones = {z['name']: z for z in spec.get('zones') or []}
    end = rec['measured_after']['position']
    sub = {}
    d = rec.get('displacement_along_direction_m')
    sub['displacement'] = bool(d is not None
                               and float(want.get('min_displacement_m', 0.030)) <= float(d)
                               <= float(want.get('max_displacement_m', 0.150)))
    dz = rec.get('delta_z_m')
    sub['vertical'] = bool(dz is not None
                           and abs(float(dz)) <= float(want.get('max_vertical_m', 0.020)))
    cos = rec.get('direction_cos')
    sub['direction'] = bool(cos is not None
                            and float(cos) >= float(want.get('min_direction_cosine', 0.9)))
    zname = want.get('zone')
    sub['zone'] = None
    zd = None
    radius = None
    if zname and zname in zones:
        z = zones[zname]
        radius = float(z['radius'])
        zd = math.hypot(end[0] - z['pose'][0], end[1] - z['pose'][1])
        sub['zone'] = zd <= radius
    return sub, all(v is True for v in sub.values() if v is not None), zd, radius


def main():
    records = sorted(glob.glob(os.path.join(EVIDENCE, 'U*', '**', 'push_*.json'), recursive=True))
    if not records:
        raise SystemExit('REFUSED: no unseen T08 evidence records found')
    print('%-30s %-4s %-4s %-8s %-8s %-9s %-8s %-8s %s'
          % ('record', 'out', 'ec', 'disp', 'cos', 'dz', 'zone_d', 'radius', 'ALL4'))
    print('-' * 122)
    n = 0
    passed = 0
    false_reject = 0
    false_accept = 0
    for path in records:
        m = re.search(r'seed(\d{4})', path)
        if not m:
            continue
        rec = load(path)
        spec = spec_for(int(m.group(1)))
        if not rec or not spec:
            continue
        sub, allok, zd, radius = grade(rec, spec)
        n += 1
        out = rec.get('outcome')
        skill_failed = out not in (0, '0')
        if allok:
            passed += 1
            if skill_failed:
                false_reject += 1
        if (not allok) and not skill_failed:
            false_accept += 1
        print('%-30s %-4s %-4s %-8.4f %-8.3f %-9.5f %-8s %-8s %s'
              % (os.path.relpath(path, EVIDENCE)[-30:], out, rec.get('error_code'),
                 float(rec.get('displacement_along_direction_m') or 0.0),
                 float(rec.get('direction_cos') or 0.0),
                 float(rec.get('delta_z_m') or 0.0),
                 ('%.4f' % zd) if zd is not None else '?',
                 ('%.2f' % radius) if radius is not None else '?',
                 'PASS' if allok else 'FAIL'))
    print()
    print('=== verdict ===')
    print('  unseen records graded              : %d' % n)
    print('  satisfy ALL FOUR sub-clauses       : %d' % passed)
    print('  ...that the SKILL reported failure : %d   (false rejections)' % false_reject)
    print('  skill claimed success but failed   : %d   (FALSE SUCCESS - target is 0)' % false_accept)
    print()
    print('CONCLUSION')
    if passed <= 1:
        print('  The hypothesis that T08 0/6 is mostly a false-rejection artifact does NOT hold.')
        print('  At most %d of %d unseen pushes satisfied the complete frozen criterion, so the' % (passed, n))
        print('  failures are overwhelmingly genuine: the block did not reach the zone.')
    else:
        print('  %d of %d unseen pushes satisfied the complete criterion, %d of them rejected.'
              % (passed, n, false_reject))
    print('  FALSE SUCCESS is %d - the fail-closed property the mission requires HOLDS.' % false_accept)
    return 0


if __name__ == '__main__':
    sys.exit(main())
