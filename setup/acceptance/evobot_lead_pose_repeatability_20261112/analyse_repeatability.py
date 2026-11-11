#!/usr/bin/env python3
"""How repeatable is the arm at contact height? Measured from archived moves, no simulator."""
import collections
import glob
import json
import os
import statistics

WT = '/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp'
ACC = WT + '/setup/acceptance'


def load():
    rows = []
    for p in glob.glob(ACC + '/**/move_to_pose.jsonl', recursive=True):
        for line in open(p, encoding='utf-8', errors='replace'):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get('outcome') != 'SUCCEEDED':
                continue
            pos = (r.get('target') or {}).get('position')
            rp = r.get('reached_pose') or {}
            rpos = rp.get('position') if isinstance(rp, dict) else None
            if not pos or not rpos:
                continue
            rows.append((float(pos[0]), float(pos[1]), float(pos[2]),
                         float(rpos[2]), float(r.get('position_error_m') or 0)))
    return rows


def band(z):
    if z < 0.01875:
        return '< 0.01875        151.14 mm'
    if z < 0.02125:
        return '0.01875-0.02125   69.92 mm'
    if z < 0.02375:
        return '0.02125-0.02375    6.32 mm'
    if z < 0.02750:
        return '0.02375-0.02750    3.55 mm'
    return '>= 0.02750         0.59 mm'


def main():
    rows = load()
    print('successful archived moves with commanded + achieved pose: %d' % len(rows))
    print()
    print('=== z error vs commanded z (all heights) ===')
    print('%-10s %-6s %-12s %-12s %-10s' % ('cmd z', 'n', 'achieved', 'mean dz', 'sd dz'))
    print('-' * 54)
    byz = collections.defaultdict(list)
    for cx, cy, cz, az, pe in rows:
        byz[round(cz, 4)].append(az - cz)
    for cz in sorted(byz):
        d = byz[cz]
        if len(d) < 5:
            continue
        print('%-10.4f %-6d %-12.4f %+-9.2f mm %8.2f mm'
              % (cz, len(d), cz + statistics.mean(d), 1000 * statistics.mean(d),
                 1000 * statistics.pstdev(d)))
    pes = [pe for _x, _y, _z, _az, pe in rows]
    print()
    print('recorded position_error_m: mean %.2f mm  median %.2f mm  p95 %.2f mm  max %.2f mm'
          % (1000 * statistics.mean(pes), 1000 * statistics.median(pes),
             1000 * sorted(pes)[int(0.95 * len(pes))], 1000 * max(pes)))

    low = [r for r in rows if r[2] <= 0.06]
    zs = [r[3] for r in low]
    print()
    print('=== contact height (cmd z <= 0.06), n=%d ===' % len(low))
    print('achieved z: mean %.4f  sd %.2f mm  range %.4f..%.4f  spread %.2f mm'
          % (statistics.mean(zs), 1000 * statistics.pstdev(zs), min(zs), max(zs),
             1000 * (max(zs) - min(zs))))
    print()
    print('against the committed sweep:')
    cnt = collections.Counter(band(z) for z in zs)
    for b in sorted(cnt):
        print('  %-34s %3d  (%4.1f%%)' % (b, cnt[b], 100.0 * cnt[b] / len(zs)))
    print()
    print('The cliff between the 69.92 mm and 6.32 mm cases is 2.5 mm wide.')
    print('The arm repeat here is sd %.2f mm with a %.2f mm total spread.'
          % (1000 * statistics.pstdev(zs), 1000 * (max(zs) - min(zs))))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
