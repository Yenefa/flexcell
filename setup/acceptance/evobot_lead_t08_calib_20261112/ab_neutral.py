"""Paired A/B in one Gazebo world: does returning the arm to a known-reachable neutral pose
before each push stop the second call from failing with ec 30?

Evidence motivating the candidate: push 1 delivered 145.2 mm and push 2 returned ec 30 with
increments_executed 0 in the same world at the same contact height; and
evobot_lead_t08_height_offset_20261112/README.md already recorded seed5002 failing ec 30 on
the ORDINARY approach pose in a world measured identical to zero variance, concluding the
difference is 'the arm's prior state, which nothing controls'.

Arm home is read from /observe at start, not hardcoded to a task instance.
"""
import sys, json, time
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import PoseStamped
from flexcell_interfaces.action import Observe, PushObject, MoveToPose

OUT = sys.argv[1]
CONTACT_Z = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0200
DIST = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0900
OBJ = sys.argv[4] if len(sys.argv) > 4 else 'target_box_a'

rclpy.init()
node = Node('ab_neutral')
ob = ActionClient(node, Observe, 'observe')
pu = ActionClient(node, PushObject, 'push_object')
mv = ActionClient(node, MoveToPose, 'move_to_pose')
for c in (ob, pu, mv): c.wait_for_server(timeout_sec=30.0)

def snap():
    g = Observe.Goal(); g.refresh = True; g.max_age_s = 0.0
    f = ob.send_goal_async(g); rclpy.spin_until_future_complete(node, f, timeout_sec=30.0)
    h = f.result()
    if h is None or not h.accepted: return None
    rf = h.get_result_async(); rclpy.spin_until_future_complete(node, rf, timeout_sec=30.0)
    ws = rf.result().result.world_state
    e = ws.robot.ee_pose.position
    boxes = {}
    for attr in ('objects','tracked_objects','items'):
        for o in (getattr(ws, attr, None) or []):
            try:
                p = o.pose.position; boxes[o.name] = (round(p.x,5), round(p.y,5), round(p.z,5))
            except Exception: pass
    return {'ee': (round(e.x,5), round(e.y,5), round(e.z,5)), 'boxes': boxes}

def go_home(home):
    g = MoveToPose.Goal(); g.request_id = 'neutral'
    ps = PoseStamped(); ps.header.frame_id = 'world'
    ps.pose.position.x, ps.pose.position.y, ps.pose.position.z = home
    ps.pose.orientation.w = 1.0
    g.target = ps; g.motion_profile_id = ''; g.expected_world_revision = 0; g.deadline_ms = 30000
    f = mv.send_goal_async(g); rclpy.spin_until_future_complete(node, f, timeout_sec=60.0)
    h = f.result()
    if h is None or not h.accepted: return {'ok': False, 'why': 'rejected'}
    rf = h.get_result_async(); rclpy.spin_until_future_complete(node, rf, timeout_sec=120.0)
    r = rf.result().result
    return {'ok': int(getattr(r,'outcome',1))==0,
            'ec': int(getattr(r,'error_code',-1)),
            'err': round(float(getattr(r,'position_error_m',float('nan'))),5)}

def push_once():
    g = PushObject.Goal(); g.object_name = OBJ
    g.direction.x = -1.0; g.direction.y = 0.0; g.direction.z = 0.0
    g.distance_m = DIST; g.contact_height_m = CONTACT_Z; g.overdrive_m = float('nan')
    f = pu.send_goal_async(g); rclpy.spin_until_future_complete(node, f, timeout_sec=60.0)
    h = f.result()
    if h is None or not h.accepted: return {'err': 'rejected'}
    rf = h.get_result_async(); rclpy.spin_until_future_complete(node, rf, timeout_sec=240.0)
    r = rf.result().result
    return {'ec': int(r.error_code), 'disp': round(float(r.displacement_m),5),
            'cos': round(float(r.direction_cos),4), 'contact': bool(r.contact_made),
            'inc': int(r.increments_executed),
            'detail': str(getattr(r,'detail',''))[:120]}

s = snap(); HOME = s['ee']
print('neutral pose (read from /observe at start):', HOME)
rec = {'home': HOME, 'contact_z': CONTACT_Z, 'distance': DIST, 'arms': {}}

for cond in ('A_no_neutral', 'B_neutral'):
    # fresh world state is NOT available mid-run, so run each condition in its own process.
    pass

cond = sys.argv[5] if len(sys.argv) > 5 else 'A_no_neutral'
seq = []
for i in range(1, 4):
    pre = snap()
    h = go_home(HOME) if cond == 'B_neutral' else None
    after_h = snap() if h else None
    r = push_once()
    post = snap()
    seq.append({'attempt': i, 'pre_ee': pre['ee'], 'neutral': h,
                'after_neutral_ee': after_h['ee'] if after_h else None,
                'push': r, 'post_ee': post['ee'], 'post_box': post['boxes'].get(OBJ)})
    print('  %s #%d ec=%s disp=%s inc=%s contact=%s box=%s' %
          (cond, i, r.get('ec'), r.get('disp'), r.get('inc'), r.get('contact'),
           post['boxes'].get(OBJ)))
rec['arms'][cond] = seq
json.dump(rec, open(OUT,'w'), indent=1)
node.destroy_node(); rclpy.shutdown()