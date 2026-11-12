"""One push per world: skill displacement (pre-retreat) vs measured displacement (post-retreat).

Quantifies the benefit of moving the sample point, without touching contracts/push.py:
the skill reports what it sees, and observe_box reports what actually happened after the
retreat returned.
"""
import sys, json, time
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from flexcell_interfaces.action import Observe, PushObject

OUT = sys.argv[1]; Z = float(sys.argv[2]); OBJ = sys.argv[3]; X0 = float(sys.argv[4])
rclpy.init(); node = Node('gap'); 
ob = ActionClient(node, Observe, 'observe'); pu = ActionClient(node, PushObject, 'push_object')
ob.wait_for_server(timeout_sec=30.0); pu.wait_for_server(timeout_sec=30.0)

def obs():
    g = Observe.Goal(); g.refresh = True; g.max_age_s = 0.0
    f = ob.send_goal_async(g); rclpy.spin_until_future_complete(node, f, timeout_sec=30.0)
    h = f.result()
    if h is None or not h.accepted: return None
    rf = h.get_result_async(); rclpy.spin_until_future_complete(node, rf, timeout_sec=30.0)
    ws = rf.result().result.world_state
    for attr in ('objects','tracked_objects','items'):
        for o in (getattr(ws, attr, None) or []):
            if getattr(o,'name','') == OBJ:
                p = o.pose.position
                return [float(p.x), float(p.y), float(p.z)]
    return None

pre = obs()
g = PushObject.Goal(); g.object_name = OBJ
g.direction.x = -1.0; g.direction.y = 0.0; g.direction.z = 0.0
g.distance_m = 0.10; g.contact_height_m = Z; g.overdrive_m = float('nan')
f = pu.send_goal_async(g); rclpy.spin_until_future_complete(node, f, timeout_sec=60.0)
h = f.result(); res = None
if h is not None and h.accepted:
    rf = h.get_result_async(); rclpy.spin_until_future_complete(node, rf, timeout_sec=240.0)
    r = rf.result().result
    res = {'ec': int(r.error_code), 'skill_disp': round(float(r.displacement_m),5),
           'skill_along': round(float(r.displacement_along_direction_m),5)}
post = obs()
out = {'contact_z': Z, 'x0': X0, 'pre': pre, 'post': post, 'result': res}
if post:
    out['actual_along'] = round((X0 - post[0]) * -1.0 * -1.0, 5)  # -x push: along = x0 - x
    out['actual_along'] = round(X0 - post[0], 5)
json.dump(out, open(OUT,'w'), indent=1)
if res and post:
    print('z=%.4f ec=%-3d skill=%+.4f  actual=%+.4f  gap=%+.4f' % (
        Z, res['ec'], res['skill_along'], out['actual_along'],
        out['actual_along'] - res['skill_along']))
else:
    print('z=%.4f INCOMPLETE' % Z)
node.destroy_node(); rclpy.shutdown()