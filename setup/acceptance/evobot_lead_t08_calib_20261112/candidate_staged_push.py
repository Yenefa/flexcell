"""Candidate arm for the paired T08 comparison: staging move, then one push, judged by T08 clauses.

WHY A STAGING MOVE. move_to_pose keeps the current orientation, so the pitch at a push approach is
inherited from whatever the arm did immediately before. Measured in pitch_probe.py: from the neutral
pose link5_x_z is -0.0012, and staging to (0.35, 0, 0.03) yields -0.3171 at the approach instead of
the -0.7327 median over 204 archived approaches. Flatter link5 means the 44.3 mm offset between
end_effector_link and the finger joints projects less onto world z, so the fingers sit lower.

Pre-registered criterion, fixed before this script was run: the candidate must reach direction-correct
in >= 75% of attempts AND task pass in >= 50%. Baseline on the default approach is 42% and 44%.
"""
import sys, json, math
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import PoseStamped
from flexcell_interfaces.action import Observe, PushObject, MoveToPose

OFFSET = 0.0443; BOX_TOP = 0.0350
OUT=sys.argv[1]; TASK=sys.argv[2]; STAGE=[float(v) for v in sys.argv[3:6]]
REQ=float(sys.argv[6]) if len(sys.argv)>6 else 0.040
Z=float(sys.argv[7]) if len(sys.argv)>7 else 0.0200

def lx(q):
    x,y,z,w=[float(v) for v in q]
    return [1-2*(y*y+z*z), 2*(x*y+z*w), 2*(x*z-y*w)]

rclpy.init(); node=Node('cand')
ob=ActionClient(node,Observe,'observe'); pu=ActionClient(node,PushObject,'push_object'); mv=ActionClient(node,MoveToPose,'move_to_pose')
for c in (ob,pu,mv): c.wait_for_server(timeout_sec=30.0)

def snap():
    g=Observe.Goal(); g.refresh=True; g.max_age_s=0.0
    f=ob.send_goal_async(g); rclpy.spin_until_future_complete(node,f,timeout_sec=30.0)
    h=f.result()
    if h is None or not h.accepted: return None,None,None
    rf=h.get_result_async(); rclpy.spin_until_future_complete(node,rf,timeout_sec=30.0)
    ws=rf.result().result.world_state
    boxes={}
    for attr in ('objects','tracked_objects','items'):
        for o in (getattr(ws,attr,None) or []):
            p=o.pose.position; boxes[o.name]=[float(p.x),float(p.y),float(p.z)]
    e=ws.robot.ee_pose.position; q=ws.robot.ee_pose.orientation
    return boxes,[float(e.x),float(e.y),float(e.z)],[float(q.x),float(q.y),float(q.z),float(q.w)]

def stage_move():
    g=MoveToPose.Goal(); g.request_id='stage'
    ps=PoseStamped(); ps.header.frame_id='world'
    ps.pose.position.x,ps.pose.position.y,ps.pose.position.z=STAGE
    ps.pose.orientation.w=1.0
    g.target=ps; g.motion_profile_id=''; g.expected_world_revision=0; g.deadline_ms=30000
    f=mv.send_goal_async(g); rclpy.spin_until_future_complete(node,f,timeout_sec=60.0)
    h=f.result()
    if h is None or not h.accepted: return 'rejected'
    rf=h.get_result_async(); rclpy.spin_until_future_complete(node,rf,timeout_sec=120.0)
    return str(rf.result().result.outcome)

spec=json.load(open(TASK))
want=spec['expected_goal']['push']['target_box_a']
zone=[z for z in spec['zones'] if z['name']==want['zone']][0]
obj='target_box_a'

# STAGING GUARD. The staging move is not always effective: in the 18-run injected sweep,
# seed3000 runs 2 and 3 ended with link5_x_z at -0.0012 and -0.0002 instead of the -0.32 the
# move normally produces, meaning the pose was not actually changed. One of those two still
# passed by luck and the other failed at ec 30 with zero displacement. Rather than hope, the
# pitch is verified after the move and the move retried if it did not take.
PITCH_TARGET = -0.20        # coarser than the achieved ~-0.32; only asks that the arm is pitched
PITCH_TOL = 0.12            # at all, which is the property the fix depends on
STAGE_TRIES = 3

b0,ee0,q0=snap()
st=stage_move()
b1,ee1,q1=snap()
pitch=(lx(q1)[2] if q1 else None)
stage_attempts=1
while STAGE_TRIES > stage_attempts and (pitch is None or abs(pitch) < abs(PITCH_TARGET) - PITCH_TOL):
    stage_attempts += 1
    st=stage_move()
    b1,ee1,q1=snap()
    pitch=(lx(q1)[2] if q1 else None)
stage_ok = pitch is not None and abs(pitch) >= abs(PITCH_TARGET) - PITCH_TOL

g=PushObject.Goal(); g.object_name=obj
g.direction.x=-1.0; g.direction.y=0.0; g.direction.z=0.0
g.distance_m=REQ; g.contact_height_m=Z; g.overdrive_m=float('nan')
f=pu.send_goal_async(g); rclpy.spin_until_future_complete(node,f,timeout_sec=60.0)
h=f.result(); res=None
if h is not None and h.accepted:
    rf=h.get_result_async(); rclpy.spin_until_future_complete(node,rf,timeout_sec=240.0)
    r=rf.result().result
    res={'ec':int(r.error_code),'skill_disp':round(float(r.displacement_m),5),'contact':bool(r.contact_made)}
b2,ee2,q2=snap()

# Raw positions are kept because the frozen evaluator needs them: derived fields alone
# (displacement, cosine, zone distance) are this script's own summary and cannot be fed
# back into evaluate.py. Without these, independent acceptance is impossible.
out={'stage':STAGE,'stage_outcome':st,'pitch_lz':pitch,'stage_attempts':stage_attempts,
     'stage_ok':stage_ok,
     'finger_z':(ee1[2]-OFFSET*pitch) if (ee1 and pitch is not None) else None,
     'pre':b1,'post':b2,'push':res}
judged=False
if b1 and b2 and obj in b1 and obj in b2:
    pre=b1[obj]; post=b2[obj]
    disp=math.hypot(post[0]-pre[0],post[1]-pre[1])
    along=(post[0]-pre[0])*-1.0
    cos=along/disp if disp>1e-6 else 0.0
    zd=math.hypot(post[0]-zone['pose'][0],post[1]-zone['pose'][1])
    ok=bool(want['min_displacement_m']<=disp<=want['max_displacement_m']
            and abs(post[2]-pre[2])<=want['max_vertical_m']
            and cos>=want['min_direction_cosine'] and zd<=zone['radius'])
    out.update({'displacement_m':round(disp,5),'cos':round(cos,4),'zone_distance':round(zd,5),'passed':ok})
    judged=True
json.dump(out,open(OUT,'w'),indent=1)
if judged:
    print('stage=%s lz=%s finger_z=%s ec=%s disp=%.4f cos=%+.3f zone=%.4f -> %s' % (
        STAGE, ('%+.4f'%pitch) if pitch is not None else 'n/a',
        ('%.4f'%out['finger_z']) if out['finger_z'] else 'n/a',
        res['ec'] if res else '?', out['displacement_m'], out['cos'], out['zone_distance'],
        'PASS' if out['passed'] else 'FAIL'))
else:
    print('stage=%s INCOMPLETE' % STAGE)
node.destroy_node(); rclpy.shutdown()