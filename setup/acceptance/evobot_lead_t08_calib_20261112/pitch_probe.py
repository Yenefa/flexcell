"""Does a horizontal pre-move change the pitch the subsequent push inherits?

Motivation, measured from evobot_t08_evidence_loop_20261112/evidence/U/seed3001/t1: in that run the
push increments held link5_x_z around -0.80 (fingers 0.054-0.062, above the 0.035 box top) while the
approach/retreat round trips in the same run held link5_x_z around 0.00 (fingers 0.028, below the box
top). Pose is path-dependent: move_to_pose keeps the current orientation, so what the arm did before
determines the pitch at the approach.

This script issues one move_to_pose to a horizontal staging point, then one push, and reports the
pitch and finger height of both. One world, no overlay, no repository change.
"""
import sys, json
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import PoseStamped
from flexcell_interfaces.action import Observe, PushObject, MoveToPose

OFFSET = 0.0443; BOX_TOP = 0.0350
OUT=sys.argv[1]; STAGE=[float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])]
rclpy.init(); node=Node('pitch_probe')
ob=ActionClient(node,Observe,'observe'); pu=ActionClient(node,PushObject,'push_object'); mv=ActionClient(node,MoveToPose,'move_to_pose')
for c in (ob,pu,mv): c.wait_for_server(timeout_sec=30.0)

def lx(q):
    x,y,z,w=[float(v) for v in q]
    return [1-2*(y*y+z*z), 2*(x*y+z*w), 2*(x*z-y*w)]

def ee():
    g=Observe.Goal(); g.refresh=True; g.max_age_s=0.0
    f=ob.send_goal_async(g); rclpy.spin_until_future_complete(node,f,timeout_sec=30.0)
    h=f.result()
    if h is None or not h.accepted: return None,None
    rf=h.get_result_async(); rclpy.spin_until_future_complete(node,rf,timeout_sec=30.0)
    ws=rf.result().result.world_state
    p=ws.robot.ee_pose.position; o=ws.robot.ee_pose.orientation
    return [float(p.x),float(p.y),float(p.z)], [float(o.x),float(o.y),float(o.z),float(o.w)]

def stage():
    g=MoveToPose.Goal(); g.request_id='stage'
    ps=PoseStamped(); ps.header.frame_id='world'
    ps.pose.position.x, ps.pose.position.y, ps.pose.position.z = STAGE
    ps.pose.orientation.w=1.0
    g.target=ps; g.motion_profile_id=''; g.expected_world_revision=0; g.deadline_ms=30000
    f=mv.send_goal_async(g); rclpy.spin_until_future_complete(node,f,timeout_sec=60.0)
    h=f.result()
    if h is None or not h.accepted: return 'rejected'
    rf=h.get_result_async(); rclpy.spin_until_future_complete(node,rf,timeout_sec=120.0)
    return str(rf.result().result.outcome)

p0,q0 = ee()
print('before stage: ee_z=%.4f lz=%+.4f' % (p0[2], lx(q0)[2]) if p0 else 'before stage: no pose')
print('stage move to %s -> %s' % (STAGE, stage()))
p1,q1 = ee()
if p1: print('after stage : ee_z=%.4f lz=%+.4f finger_z=%.4f clear=%+.4f' % (p1[2], lx(q1)[2], p1[2]-OFFSET*lx(q1)[2], p1[2]-OFFSET*lx(q1)[2]-BOX_TOP))
g=PushObject.Goal(); g.object_name='target_box_a'
g.direction.x=-1.0; g.direction.y=0.0; g.direction.z=0.0
g.distance_m=0.040; g.contact_height_m=0.0200; g.overdrive_m=float('nan')
f=pu.send_goal_async(g); rclpy.spin_until_future_complete(node,f,timeout_sec=60.0)
h=f.result(); res=None
if h is not None and h.accepted:
    rf=h.get_result_async(); rclpy.spin_until_future_complete(node,rf,timeout_sec=240.0)
    r=rf.result().result
    res={'ec':int(r.error_code),'disp':round(float(r.displacement_m),5),'cos':round(float(r.direction_cos),4),'contact':bool(r.contact_made)}
p2,q2 = ee()
json.dump({'stage':STAGE,'before':{'ee_z':p0[2] if p0 else None,'lz':lx(q0)[2] if q0 else None},
           'after_stage':{'ee_z':p1[2] if p1 else None,'lz':lx(q1)[2] if q1 else None,
                          'finger_z':(p1[2]-OFFSET*lx(q1)[2]) if p1 else None},
           'push':res,'after_push':{'ee_z':p2[2] if p2 else None,'lz':lx(q2)[2] if q2 else None}}, open(OUT,'w'), indent=1)
if res: print('push: ec=%d disp=%.4f cos=%+.4f contact=%s' % (res['ec'],res['disp'],res['cos'],res['contact']))
node.destroy_node(); rclpy.shutdown()