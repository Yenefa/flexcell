import json, glob, math, os

EE_X, FINGER_X = 0.1260, 0.0817
OFFSET = EE_X - FINGER_X          # 0.0443 m: fingers behind the ee frame along link5 -x
BOX_TOP = 0.0350

def link5_x_world(q):
    x,y,z,w = q
    # first column of the rotation matrix = link frame x-axis in world
    return [1-2*(y*y+z*z), 2*(x*y+z*w), 2*(x*z-y*w)]

rows = []
for f in glob.glob('/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp/setup/acceptance/**/move_to_pose.jsonl', recursive=True):
    for line in open(f, errors='replace'):
        try: d = json.loads(line)
        except Exception: continue
        rp = d.get('reached_pose') or {}
        p, q = rp.get('position'), rp.get('orientation')
        if not p or not q or len(q) != 4: continue
        tgt = (d.get('target') or {}).get('position') or []
        try:
            lx = link5_x_world([float(v) for v in q])
            finger_z = float(p[2]) - OFFSET * lx[2]
        except Exception:
            continue
        rows.append({'file': f.split('/evidence/')[-1] if '/evidence/' in f else os.path.basename(os.path.dirname(f)),
                     'req': d.get('request_id'), 'tgt_z': float(tgt[2]) if len(tgt)>2 else None,
                     'ee_z': float(p[2]), 'lxz': lx[2], 'finger_z': finger_z,
                     'clear': finger_z - BOX_TOP, 'outcome': d.get('outcome')})

print('move_to_pose records with a reached pose: %d' % len(rows))
if not rows:
    raise SystemExit('none found')
print()
# push approaches target the box side at the requested contact height
push = [r for r in rows if r['tgt_z'] is not None and r['tgt_z'] < 0.06 and abs((r['tgt_z'] or 0)) > 0]
print('records with a low target z (<0.06, i.e. a push approach): %d' % len(push))
print()
if push:
    fz = sorted(r['finger_z'] for r in push)
    cl = sorted(r['clear'] for r in push)
    def q(v, f): return v[min(len(v)-1, int(len(v)*f))]
    print('finger height over the box top (m):')
    print('  min %.4f   p25 %.4f   median %.4f   p75 %.4f   max %.4f' % (fz[0], q(fz,.25), q(fz,.5), q(fz,.75), fz[-1]))
    print('  records with fingers ABOVE the box top: %d/%d (%.0f%%)' % (sum(1 for r in push if r['clear']>0), len(push), 100*sum(1 for r in push if r['clear']>0)/len(push)))
    print()
    print('clearance above box top (mm):')
    print('  min %.1f   median %.1f   max %.1f' % (cl[0]*1000, q(cl,.5)*1000, cl[-1]*1000))
    print()
    print('link5 x-axis z component (drives the offset):')
    lz = sorted(r['lxz'] for r in push)
    print('  min %.4f   median %.4f   max %.4f   (negative = pointing down)' % (lz[0], q(lz,.5), lz[-1]))
    print()
    print('worked example rows:')
    for r in push[:6]:
        print('  %-28s tgt_z=%s ee_z=%.4f lxz=%+.4f -> finger_z=%.4f (clear %+.4f) %s' % (
            str(r['file'])[:28], ('%.4f'%r['tgt_z']) if r['tgt_z'] is not None else '?',
            r['ee_z'], r['lxz'], r['finger_z'], r['clear'], r['outcome']))