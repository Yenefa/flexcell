#!/usr/bin/env python3
"""Grade the six frozen fresh-instance T08 pushes against all four sub-clauses.

WHAT THIS IS FOR
    Round 8 satisfied the push criterion once, on a DEV tuning instance. This grades a set of six
    instances that were frozen by sha256 before the first run, so the result is a generalisation
    statement rather than a demonstration.

WHAT IT DELIBERATELY DOES NOT DO
    It does not grade `unmoved: target_box_b`. Only the pushed object is measured by the push action,
    so that clause is UNMEASURED here and the report says so instead of assuming the blue block stayed
    still because it is geometrically far away.
"""
import glob
import json
import math
import os
import re
import sys

WT = '/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp'
SPECS = os.path.join(WT, 'benchmark', 'tasks', 't08_fresh_zone_20261112')
EVID = '/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/ci-public-window/evidence/t08_overdrive_20261112'
MANIFEST = os.path.join(SPECS, 'freeze_manifest.json')


def pos_of(value):
    """measured_after may arrive as a dict of floats or as a str() of a Pose message."""
    if isinstance(value, dict):
        return [value['x'], value['y'], value['z']]
    m = re.search(r'x=([-\d.e+]+), y=([-\d.e+]+), z=([-\d.e+]+)', str(value))
    if not m:
        return None
    return [float(m.group(1)), float(m.group(2)), float(m.group(3))]


def main():
    manifest = json.load(open(MANIFEST, encoding='utf-8'))
    print('=== instance freeze check ===')
    for tid, sha in sorted(manifest['instances'].items()):
        path = os.path.join(SPECS, tid + '.json')
        spec = json.load(open(path, encoding='utf-8'))
        got = spec['instance_sha256']
        print('  %-22s %s' % (tid, 'INTACT' if got == sha else 'MISMATCH'))
    print()
    print('%-22s %-6s %-6s %-9s %-8s %-9s %-8s %-7s %s'
          % ('instance', 'out', 'ec', 'disp', 'cos', 'dz', 'zone_d', 'radius', 'ALL4'))
    print('-' * 108)
    n = passed = 0
    missing = []
    for tid in sorted(manifest['instances']):
        spec = json.load(open(os.path.join(SPECS, tid + '.json'), encoding='utf-8'))
        want = spec['expected_goal']['push']['target_box_a']
        zone = [z for z in spec['zones'] if z['name'] == want['zone']][0]
        seed = tid.split('seed')[-1]
        push_path = os.path.join(EVID, 'seed' + seed, 'push.json')
        if not os.path.exists(push_path):
            missing.append(tid)
            print('%-22s %s' % (tid, 'NO RESULT'))
            continue
        rec = json.load(open(push_path, encoding='utf-8'))
        if rec.get('HARNESS_ERROR'):
            missing.append(tid)
            print('%-22s %s' % (tid, 'HARNESS_ERROR - not a measurement'))
            continue
        d = rec.get('displacement_m')
        dz = rec.get('delta_z_m')
        cos = rec.get('direction_cos')
        end = pos_of(rec.get('measured_after'))
        if None in (d, dz, cos) or end is None:
            missing.append(tid)
            print('%-22s incomplete record' % tid)
            continue
        zd = math.hypot(end[0] - zone['pose'][0], end[1] - zone['pose'][1])
        ok = (float(want['min_displacement_m']) <= float(d) <= float(want['max_displacement_m'])
              and abs(float(dz)) <= float(want['max_vertical_m'])
              and float(cos) >= float(want['min_direction_cosine'])
              and zd <= float(zone['radius']))
        n += 1
        if ok:
            passed += 1
        print('%-22s %-6s %-6s %-9.4f %-8.4f %-9.5f %-8.4f %-7.2f %s'
              % (tid, rec.get('outcome'), rec.get('error_code'), float(d), float(cos),
                 float(dz), zd, float(zone['radius']), 'PASS' if ok else 'FAIL'))
    print()
    print('=== verdict ===')
    print('  instances graded                        : %d of 6' % n)
    print('  satisfy ALL FOUR push sub-clauses       : %d' % passed)
    print('  pre-registered prediction               : at least 5 of 6 (round 9 baseline: 2 of 6)')
    if missing:
        print('  no usable result                        : %s' % ', '.join(missing))
    print('  unmoved:target_box_b                    : UNMEASURED (push action measures only the pushed object)')
    print()
    if passed >= 5:
        print('  RESULT: overdrive raises the task-clause pass count as predicted. This is a')
    else:
        print('  RESULT: the prediction is FALSIFIED at %d/6. Reported as a miss; the same instances'
              % passed)
        print('          will not be re-tuned and re-run.')
    return 0


if __name__ == '__main__':
    sys.exit(main())