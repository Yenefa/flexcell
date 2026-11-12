import json, glob, os
TGT = 0.040
rows=[]
for d in sorted(glob.glob('/tmp/sw2_*') + glob.glob('/tmp/pr_*')):
    v=os.path.join(d,'v.json')
    if not os.path.exists(v): continue
    try: res=json.load(open(v))
    except Exception: continue
    verd=res.get('verdict') or {}; pu=res.get('push') or {}
    if 'displacement_m' not in verd: continue
    pre=(res.get('pre') or {}).get('target_box_a'); post=(res.get('post') or {}).get('target_box_a')
    if not pre or not post: continue
    cos = verd.get('direction_cosine') or 0.0
    sk = pu.get('skill_disp')
    if sk is None: continue
    skill_along = sk * (1.0 if cos >= 0 else -1.0)
    actual_along = round(pre[0]-post[0], 5)
    rows.append({'run':os.path.basename(d),'cos':cos,'skill':skill_along,
                 'actual':actual_along,'dir_ok':cos>=0.9})

print('runs: %d  (direction-correct %d, reversed %d)' % (
    len(rows), sum(1 for r in rows if r['dir_ok']), sum(1 for r in rows if not r['dir_ok'])))
print()
print('%-10s %+7s %10s %10s %7s %7s %s' % ('run','cos','skill_along','actual','skillOK','truthOK',''))
flips=[]
for r in rows:
    js = r['skill'] >= TGT; ja = r['actual'] >= TGT
    mark = '' if js==ja else 'FLIP'
    if js!=ja: flips.append(r)
    print('%-10s %+7.3f %+10.4f %+10.4f %7s %7s %s' % (r['run'], r['cos'], r['skill'], r['actual'], js, ja, mark))
print()
print('flips (skill says %s, truth says otherwise): %d/%d' % ('<%.3f'%TGT, len(flips), len(rows)))
ok=[r for r in rows if r['dir_ok']]
f_ok=[r for r in ok if (r['skill']>=TGT)!=(r['actual']>=TGT)]
print('  among direction-correct (n=%d): %d flips' % (len(ok), len(f_ok)))
rev=[r for r in rows if not r['dir_ok']]
f_rev=[r for r in rev if (r['skill']>=TGT)!=(r['actual']>=TGT)]
print('  among reversed       (n=%d): %d flips' % (len(rev), len(f_rev)))