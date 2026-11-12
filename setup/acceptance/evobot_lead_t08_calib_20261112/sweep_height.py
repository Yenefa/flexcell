"""One push per world at a given commanded contact height. No sampling during the push:
an earlier version called /observe from inside the wait loop on the same node and deadlocked,
because spin_until_future_complete on one node cannot service the in-flight push goal.
Post-push ground truth is enough for the height question.
"""
import sys, json, time
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from flexcell_interfaces.action import Observe, PushObject

OUT = sys.argv[1]
Z = float(sys.argv[2])
DIST = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0900
OBJ = sys.argv[4] if len(sys.argv) > 4 else 'target_box_a'

rclpy.init()
node = Node('sweep')
ob = ActionClient(node, Observe, 'observe')
pu = ActionClient(node, PushObject, 'push_object')
ob.wait_for_server(timeout_sec=30.0)
pu.wait_for_server(timeout_sec=30.0)

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
                p = o.pose.position; boxes[o.name] = [round(p.x,5), round(p.y,5), round(p.z,5)]
            except Exception: pass
    return {'ee': [round(e.x,5), round(e.y,5), round(e.z,5)], 'boxes': boxes}

pre = snap()
g = PushObject.Goal(); g.object_name = OBJ
g.direction.x = -1.0; g.direction.y = 0.0; g.direction.z = 0.0
g.distance_m = DIST; g.contact_height_m = Z; g.overdrive_m = float('nan')
f = pu.send_goal_async(g)
rclpy.spin_until_future_complete(node, f, timeout_sec=60.0)
h = f.result()
res = None
if h is not None and h.accepted:
    rf = h.get_result_async()
    rclpy.spin_until_future_complete(node, rf, timeout_sec=240.0)
    r = rf.result().result
    res = {'ec': int(r.error_code), 'disp': round(float(r.displacement_m),5),
           'along': round(float(r.displacement_along_direction_m),5),
           'cos': round(float(r.direction_cos),4), 'contact': bool(r.contact_made),
           'inc': int(r.increments_executed), 'ee_travel': round(float(r.ee_travel_m),5),
           'reach': round(float(r.reach_error_m),5), 'detail': str(getattr(r,'detail',''))[:120]}
post = snap()
out = {'commanded_z': Z, 'distance': DIST,
       'pre_box': pre['boxes'].get(OBJ) if pre else None,
       'post_box': post['boxes'].get(OBJ) if post else None,
       'ee_final': post['ee'] if post else None, 'result': res}
json.dump(out, open(OUT,'w'), indent=1)
if res:
    dx = 0.0
    if out['pre_box'] and out['post_box']: dx = out['post_box'][0]-out['pre_box'][0]
    print('z=%.4f ec=%-2d disp=%.4f cos=%+.4f contact=%-5s inc=%d ee_final=%s dx=%+.4f' % (
        Z, res['ec'], res['disp'], res['cos'], res['contact'], res['inc'],
        out['ee_final'], dx))
else:
    print('z=%.4f PUSH REJECTED' % Z)
node.destroy_node(); rclpy.shutdown()