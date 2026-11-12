import json, glob, os
EE_X, FINGER_X, BOX_TOP = 0.1260, 0.0817, 0.0350
OFFSET = EE_X - FINGER_X

def lx(q):
    x,y,z,w=[float(v) for v in q]
    return [1-2*(y*y+z*z), 2*(x*y+z*w), 2*(x*z-y*w)]

rows=[]
for d in sorted(glob.glob('/tmp/sw2_*') + glob.glob('/tmp/pr_*') + glob.glob('/tmp/gap_*')):
    m=os.path.join(d,'sim/skills/move_to_pose.jsonl')
    v=os.path.join(d,'v.json'); r0=os.path.join(d,'r.json')
    res=None
    for p in (v,r0):
        if os.path.exists(p):
            try: res=json.load(open(p))
            except Exception: pass
            if res: break
    if not res or not os.path.exists(m): continue
    verdict=res.get('verdict') or {}
    pu=res.get('result') or res.get('push') or {}
    cos = verdict.get('direction_cosine', pu.get('cos'))
    disp = verdict.get('displacement_m', pu.get('disp'))
    if cos is None: continue
    appr=[]
    for line in open(m, errors='replace'):
        try: rec=json.loads(line)
        except Exception: continue
        rp=rec.get('reached_pose') or {}
        p,q2=rp.get('position'),rp.get('orientation')
        tgt=(rec.get('target') or {}).get('position') or []
        if not p or not q2 or len(q2)!=4 or len(tgt)<3: continue
        try: tz=float(tgt[2]); ez=float(p[2]); l=lx(q2)
        except Exception: continue
        if tz>=0.06: continue
        appr.append({'tz':tz,'ez':ez,'lz':l[2],'fz':ez-OFFSET*l[2]})
    if not appr: continue
    a=min(appr,key=lambda r: abs(r['tz']-0.0200))
    rows.append({'run':d.split('/')[-1],'tz':a['tz'],'ez':a['ez'],'lz':a['lz'],
                 'fz':a['fz'],'clear':a['fz']-BOX_TOP,'cos':float(cos),'disp':float(disp or 0),
                 'ok': float(cos)>=0.9})

print('joinable runs: %d' % len(rows))
above=[r for r in rows if r['clear']>0]
below=[r for r in rows if r['clear']<=0]
def s(name, x):
    if not x: print('  %-6s none' % name); return
    g=sum(1 for r in x if r['ok'])
    print('  %-6s n=%-3d direction-ok %d/%d (%3.0f%%)  mean cos %+.3f  mean disp %.4f  clear %.1f..%.1f mm' % (
        name,len(x),g,len(x),100*g/len(x),sum(r['cos'] for r in x)/len(x),
        sum(r['disp'] for r in x)/len(x), min(r['clear'] for r in x)*1000, max(r['clear'] for r in x)*1000))
print()
s('ABOVE',above); s('BELOW',below)
print()
print('%-12s %6s %6s %8s %8s %7s %7s %s' % ('run','tgt_z','ee_z','lz','finger_z','clear','cos','ok'))
for r in sorted(rows,key=lambda r:r['clear']):
    print('%-12s %6.4f %6.4f %+8.4f %8.4f %+7.4f %+7.3f %s' % (r['run'],r['tz'],r['ez'],r['lz'],r['fz'],r['clear'],r['cos'],'OK' if r['ok'] else 'REV'))