"""T08 pose diagnostic: /observe before and after every push, so H1 vs H3 stops being an inference.

WHY THE OBSERVE ACTION AND NOT A SUBSCRIPTION: /flexcell/world_state is published by
observe_server on demand only. A subscriber sees nothing while the arm is idle, which is
how two earlier recorder attempts returned 0 samples against a topic that reports one
publisher. The action also takes refresh=true to force a fresh ground-truth sample.
"""
import sys, json, time
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from flexcell_interfaces.action import Observe, PushObject

OUT = sys.argv[1]
ATTEMPTS = int(sys.argv[2]) if len(sys.argv) > 2 else 2
CONTACT_Z = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0200
DIST = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0900
OBJ = sys.argv[5] if len(sys.argv) > 5 else 'target_box_a'

rclpy.init()
node = Node('t08_diag')
obs = ActionClient(node, Observe, 'observe')
push = ActionClient(node, PushObject, 'push_object')
obs.wait_for_server(timeout_sec=30.0)
push.wait_for_server(timeout_sec=30.0)
rec = []

def snapshot(tag):
    g = Observe.Goal(); g.refresh = True; g.max_age_s = 0.0
    f = obs.send_goal_async(g)
    rclpy.spin_until_future_complete(node, f, timeout_sec=30.0)
    h = f.result()
    if h is None or not h.accepted:
        rec.append({'tag': tag, 'err': 'observe rejected'}); return None
    rf = h.get_result_async()
    rclpy.spin_until_future_complete(node, rf, timeout_sec=30.0)
    w = rf.result().result
    ws = w.world_state
    e = ws.robot.ee_pose.position
    objs = []
    for attr in ('objects', 'tracked_objects', 'items'):
        for o in (getattr(ws, attr, None) or []):
            try:
                p = o.pose.position
                objs.append({'name': o.name, 'x': round(p.x,5), 'y': round(p.y,5), 'z': round(p.z,5)})
            except Exception:
                pass
    d = {'tag': tag, 't': round(time.time(),3),
         'ee': [round(e.x,5), round(e.y,5), round(e.z,5)],
         'ee_frame': getattr(ws.robot, 'ee_frame', ''),
         'gripper': round(float(getattr(ws.robot, 'gripper_position', 0.0)),5),
         'joints': [round(float(v),5) for v in (getattr(ws.robot,'positions',None) or [])],
         'objects': objs, 'rev': int(ws.revision), 'status': int(w.status)}
    rec.append(d)
    return d

snapshot('initial')
for i in range(ATTEMPTS):
    snapshot('before_push_%d' % (i+1))
    g = PushObject.Goal()
    g.object_name = OBJ
    g.direction.x = -1.0; g.direction.y = 0.0; g.direction.z = 0.0
    g.distance_m = DIST; g.contact_height_m = CONTACT_Z
    g.overdrive_m = float('nan')
    f = push.send_goal_async(g)
    rclpy.spin_until_future_complete(node, f, timeout_sec=60.0)
    h = f.result()
    if h is None or not h.accepted:
        rec.append({'tag': 'push_%d' % (i+1), 'err': 'push rejected'}); break
    rf = h.get_result_async()
    rclpy.spin_until_future_complete(node, rf, timeout_sec=240.0)
    r = rf.result().result
    rec.append({'tag': 'push_%d' % (i+1), 'result': {
        'outcome': int(r.outcome), 'error_code': int(r.error_code),
        'displacement_m': float(r.displacement_m),
        'displacement_along_direction_m': float(r.displacement_along_direction_m),
        'direction_cos': float(r.direction_cos), 'contact_made': bool(r.contact_made),
        'ee_travel_m': float(r.ee_travel_m), 'reach_error_m': float(r.reach_error_m),
        'increments_executed': int(r.increments_executed)}})
    snapshot('after_push_%d' % (i+1))

json.dump(rec, open(OUT, 'w'), indent=2)
print('RECORDS', len(rec))
for r in rec:
    if 'ee' in r: print('  %-16s ee=%s grip=%.5f objs=%s' % (r['tag'], r['ee'], r['gripper'], [(o['name'],o['x']) for o in r['objects']]))
    elif 'result' in r: x=r['result']; print('  %-16s disp=%.4f cos=%+.4f contact=%s ee_travel=%.4f reach=%.4f' % (r['tag'], x['displacement_m'], x['direction_cos'], x['contact_made'], x['ee_travel_m'], x['reach_error_m']))
node.destroy_node(); rclpy.shutdown()