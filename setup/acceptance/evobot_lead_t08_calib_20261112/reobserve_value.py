"""How much would ALWAYS re-observing change? Offline over the 28 archived runs.

Round 15 showed an error-code filter cannot separate good decisions from bad (15% vs 13%).
The remaining option is to stop trusting the skill displacement at all and measure the box
directly after each push. This quantifies what that would change before implementing it.
"""
import json, glob, os
BASE='/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp/'
TGT=0.100
specs={}
for d in ('benchmark/tasks/t08_dev/','benchmark/tasks/t08_unseen/'):
    for p in glob.glob(BASE+d+'*.json'):
        try: specs[os.path.basename(p).replace('.json','')]=json.load(open(p))
        except Exception: pass

rows=[]
for gt in sorted(glob.glob(BASE+'setup/acceptance/**/gt_after.json', recursive=True)):
    d=os.path.dirname(gt); push=os.path.join(d,'push_00.json')
    if not os.path.exists(push): continue
    try: g=json.load(open(gt)); pj=json.load(open(push))
    except Exception: continue
    box=(g.get('objects') or {}).get('target_box_a')
    if not box: continue
    vp=os.path.join(d,'verdict.json'); tid=None
    if os.path.exists(vp):
        try: tid=json.load(open(vp)).get('task_id')
        except Exception: pass
    spec=specs.get(tid) if tid else None
    if spec is None: continue
    x0=spec['objects'][0]['initial_pose'][0]
    actual=round(x0-box[0],5)
    rep=round(float(pj.get('displacement_m') or 0),5)
    rows.append((tid, pj.get('error_code'), rep, actual, rep>=TGT, actual>=TGT))

n=len(rows)
rep_ok=sum(1 for r in rows if r[4])
act_ok=sum(1 for r in rows if r[5])
flip=sum(1 for r in rows if r[4]!=r[5])
print('runs: %d' % n)
print()
print('decisions using the SKILL report      : %d/%d reached' % (rep_ok, n))
print('decisions using GROUND TRUTH re-observe: %d/%d reached' % (act_ok, n))
print('decisions that FLIP                    : %d (%.0f%%)' % (flip, 100*flip/max(n,1)))
print()
print('the flips:')
for r in rows:
    if r[4]!=r[5]:
        print('  %-22s ec=%-3s reported %.4f (%s)  actual %.4f (%s)' % (r[0], r[1], r[2], 'reached' if r[4] else 'short', r[3], 'reached' if r[5] else 'short'))