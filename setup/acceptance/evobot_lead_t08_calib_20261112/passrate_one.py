"""Single-shot T08 pass-rate: one push per fresh world, judged against the task's own clauses.

Deliberately NOT the recovery harness: that pushes repeatedly in one world, so each attempt
inherits a box the previous attempt moved. Round 19 showed the two measure different things.

IMPORTANT: this recomputes the T08 clauses from ground truth here rather than invoking the
frozen evaluator. It is an independent recomputation of the same predicates, not a substitute
for evaluate.py, and is labelled that way in the output.
"""
import sys, json, math
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from flexcell_interfaces.action import Observe, PushObject

OUT=sys.argv[1]; TASK=sys.argv[2]; Z=float(sys.argv[3])
rclpy.init(); node=Node('passrate')
ob=ActionClient(node,Observe,'observe'); pu=ActionClient(node,PushObject,'push_object')
ob.wait_for_server(timeout_sec=30.0); pu.wait_for_server(timeout_sec=30.0)

def obs():
    g=Observe.Goal(); g.refresh=True; g.max_age_s=0.0
    f=ob.send_goal_async(g); rclpy.spin_until_future_complete(node,f,timeout_sec=30.0)
    h=f.result()
    if h is None or not h.accepted: return None
    rf=h.get_result_async(); rclpy.spin_until_future_complete(node,rf,timeout_sec=30.0)
    ws=rf.result().result.world_state
    out={}
    for attr in ('objects','tracked_objects','items'):
        for o in (getattr(ws,attr,None) or []):
            p=o.pose.position; out[o.name]=[float(p.x),float(p.y),float(p.z)]
    return out

spec=json.load(open(TASK))
want=spec['expected_goal']['push']['target_box_a']
zone=[z for z in spec['zones'] if z['name']==want['zone']][0]
objname='target_box_a'
x0=spec['objects'][0]['initial_pose'][0]

pre=obs()
g=PushObject.Goal(); g.object_name=objname
g.direction.x=-1.0; g.direction.y=0.0; g.direction.z=0.0
g.distance_m=0.10; g.contact_height_m=Z; g.overdrive_m=float('nan')
f=pu.send_goal_async(g); rclpy.spin_until_future_complete(node,f,timeout_sec=60.0)
h=f.result(); res=None
if h is not None and h.accepted:
    rf=h.get_result_async(); rclpy.spin_until_future_complete(node,rf,timeout_sec=240.0)
    r=rf.result().result
    res={'ec':int(r.error_code),'skill_disp':round(float(r.displacement_m),5)}
post=obs()
verdict={'evaluated_by':'independent recomputation of T08 clauses','task':spec['task_id']}
if post and objname in post and objname in pre:
    a=post[objname]; b=pre[objname]
    disp=math.hypot(a[0]-b[0], a[1]-b[1])
    dz=abs(a[2]-b[2])
    along=(a[0]-b[0])*(-1.0)
    cos=along/disp if disp>0 else 0.0
    zdist=math.hypot(a[0]-zone['pose'][0], a[1]-zone['pose'][1])
    verdict.update({'displacement_m':round(disp,5),'vertical_m':round(dz,5),
                    'direction_cosine':round(cos,4),'zone_distance_m':round(zdist,5),
                    'box_x':round(a[0],5)})
    c1=want['min_displacement_m']<=disp<=want['max_displacement_m']
    c2=dz<=want['max_vertical_m']
    c3=cos>=want['min_direction_cosine']
    c4=zdist<=zone['radius']
    verdict['clauses']={'displacement':c1,'vertical':c2,'cosine':c3,'zone':c4}
    verdict['passed']=bool(c1 and c2 and c3 and c4)
json.dump({'verdict':verdict,'push':res,'pre':pre,'post':post}, open(OUT,'w'), indent=1)
v=verdict.get('passed')
print('%-10s ec=%-3s disp=%.4f cos=%+.3f zone=%.4f -> %s' % (spec['task_id'][-8:],
      str(res['ec']) if res else '?', verdict.get('displacement_m',0),
      verdict.get('direction_cosine',0), verdict.get('zone_distance_m',0),
      'PASS' if v else 'FAIL'))
node.destroy_node(); rclpy.shutdown()