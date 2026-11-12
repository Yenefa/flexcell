import json, glob, os
BASE='/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp/'
specs={}
for d in ('benchmark/tasks/t08_dev/','benchmark/tasks/t08_unseen/'):
    for p in glob.glob(BASE+d+'*.json'):
        try:
            s=json.load(open(p)); specs[os.path.basename(p).replace('.json','')]=s
        except Exception: pass

rows=[]
for gt in sorted(glob.glob(BASE+'setup/acceptance/**/gt_after.json', recursive=True)):
    d=os.path.dirname(gt)
    push=os.path.join(d,'push_00.json')
    if not os.path.exists(push): continue
    try:
        g=json.load(open(gt)); pj=json.load(open(push))
    except Exception: continue
    box=(g.get('objects') or {}).get('target_box_a')
    if not box: continue
    # initial x from the task spec matched by sibling verdict.json task_id
    vp=os.path.join(d,'verdict.json')
    tid=None
    if os.path.exists(vp):
        try: tid=json.load(open(vp)).get('task_id')
        except Exception: pass
    spec=specs.get(tid) if tid else None
    if spec is None: continue
    x0=spec['objects'][0]['initial_pose'][0]
    actual=round(x0-box[0],5)
    rep=round(float(pj.get('displacement_m') or 0),5)
    rows.append((tid, os.path.basename(os.path.dirname(d)), pj.get('error_code'), rep, actual,
                 round(actual-rep,5), round((actual/rep) if rep>1e-6 else float('inf'),2)))

print('%-22s %-10s %3s %8s %8s %9s %6s' % ('task','run','ec','reported','actual','gap','ratio'))
for r in rows: print('%-22s %-10s %3s %8.4f %8.4f %+9.4f %6.2f' % r)
print()
if rows:
    big=[r for r in rows if r[5]>0.02]
    print('runs compared: %d' % len(rows))
    print('runs where actual exceeds reported by >20mm: %d' % len(big))
    print('mean gap: %+.4f m' % (sum(r[5] for r in rows)/len(rows)))