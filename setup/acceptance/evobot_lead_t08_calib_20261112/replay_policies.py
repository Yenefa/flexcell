"""Replay archived recovery attempts under both objectives. No Gazebo.

All six T08 task specs share the same geometry (box 0.100 m from the zone centre,
radius 0.060), so the constants are 0.100 for centre-policy and 0.040 for enter-policy -
verified from the specs rather than assumed.
"""
import json, glob, os

BASE = '/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp/'
TGT_CENTRE = 0.100
TGT_ENTER = 0.040

def replay(attempts, target):
    acc = 0.0; used = 0
    for a in attempts:
        mv = a.get('displacement_along_direction_m')
        if mv is None or not isinstance(mv, (int, float)): break
        if float(mv) < 0: break
        acc += float(mv); used += 1
        if acc >= target: break
    return acc, used

rows = []
for f in sorted(glob.glob(BASE + 'setup/acceptance/**/recovery.json', recursive=True)):
    try: d = json.load(open(f))
    except Exception: continue
    atts = d.get('attempts') or []
    if not atts: continue
    acc_c, used_c = replay(atts, TGT_CENTRE)
    acc_e, used_e = replay(atts, TGT_ENTER)
    orig = (d.get('verdict') or {}).get('attempts', len(atts))
    rows.append((f.replace(BASE, ''), len(atts), orig, round(acc_c,4), used_c, acc_c >= TGT_CENTRE,
                 round(acc_e,4), used_e, acc_e >= TGT_ENTER))

print('%-58s %3s %4s %7s %3s %5s %7s %3s %5s' % ('recovery.json','n','orig','accC','uC','Cok','accE','uE','Eok'))
for r in rows:
    print('%-58s %3d %4s %7.4f %3d %5s %7.4f %3d %5s' % r)
print()
if rows:
    print('files: %d' % len(rows))
    print('attempts actually spent  : %d' % sum(r[2] for r in rows))
    print('attempts under centre    : %d' % sum(r[4] for r in rows))
    print('attempts under enter     : %d' % sum(r[7] for r in rows))
    print('centre reaches 0.100     : %d/%d' % (sum(1 for r in rows if r[5]), len(rows)))
    print('enter  reaches 0.040     : %d/%d' % (sum(1 for r in rows if r[8]), len(rows)))