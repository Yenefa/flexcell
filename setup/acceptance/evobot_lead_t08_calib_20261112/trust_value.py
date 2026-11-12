"""How often does trusting the reported displacement give the WRONG answer?

Offline: for each archived T08 run, compare the decision made from the skill's own
displacement against the decision implied by ground truth. No Gazebo, no ROS.
"""
import json, glob, os
BASE='/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp/'
TGT=0.100  # distance to zone centre, identical across all T08 specs
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
    ec=pj.get('error_code')
    newp=os.path.join(d,'push_01.json')
    rows.append({'task':tid,'ec':ec,'rep':rep,'actual':actual,
                 'rep_ok': rep>=TGT, 'actual_ok': actual>=TGT,
                 'trust': ec not in (27,28)})

n=len(rows)
wrong=[r for r in rows if r['rep_ok']!=r['actual_ok']]
print('runs: %d' % n)
print('decisions where reported and actual DISAGREE: %d (%.0f%%)' % (len(wrong), 100*len(wrong)/max(n,1)))
print()
print('%-22s %3s %8s %8s %6s %6s %6s' % ('task','ec','reported','actual','repOk','actOk','agree'))
for r in rows:
    print('%-22s %3s %8.4f %8.4f %6s %6s %6s' % (r['task'], r['ec'], r['rep'], r['actual'], r['rep_ok'], r['actual_ok'], r['rep_ok']==r['actual_ok']))
print()
untrusted=[r for r in rows if not r['trust']]
if untrusted:
    bad=[r for r in untrusted if r['rep_ok']!=r['actual_ok']]
    print('runs with ec 27/28 (would be re-observed): %d' % len(untrusted))
    print('  of those, decisions that disagree: %d (%.0f%%)' % (len(bad), 100*len(bad)/len(untrusted)))
trusted=[r for r in rows if r['trust']]
if trusted:
    bad2=[r for r in trusted if r['rep_ok']!=r['actual_ok']]
    print('runs with other codes (trusted): %d' % len(trusted))
    print('  of those, decisions that disagree: %d' % len(bad2))