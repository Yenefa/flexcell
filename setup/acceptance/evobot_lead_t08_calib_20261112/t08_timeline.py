"""Sample ground truth DURING a push, not only before and after.

Previous round showed the service reporting direction_cos +0.999 while the box went
further in +x, which is arithmetically impossible under contact_metrics if the service
and the snapshot see the same poses. Three explanations remain: sampling timing, a sign
or frame convention inside measure(), or the box being displaced during the
descend-to-contact phase. A time series separates all three.
"""
import sys, json, time, threading
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from flexcell_interfaces.action import Observe, PushObject, MoveToPose
from geometry_msgs.msg import PoseStamped

OUT = sys.argv[1]
CONTACT_Z = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0200
DIST = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0900
OBJ = sys.argv[4] if len(sys.argv) > 4 else 'target_box_a'

rclpy.init()
node = Node('t08_timeline')
obs_c = ActionClient(node, Observe, 'observe')
push_c = ActionClient(node, PushObject, 'push_object')
mv_c = ActionClient(node, MoveToPose, 'move_to_pose')
obs_c.wait_for_server(timeout_sec=30.0)
push_c.wait_for_server(timeout_sec=30.0)
mv_c.wait_for_server(timeout_sec=30.0)

# Optional staging move, passed as argv[5]. WHY IT IS HERE: the candidate fix is a
# move_to_pose to a neutral staging point before the push, which changes the inherited
# approach pitch. To produce ONE run whose timeline and contact trace describe the SAME
# physical episode, the sampler has to do the staging itself. Earlier bundles mixed a
# timeline from one run with a contact trace from another, and the evaluator correctly
# refused the push verdict.
STAGE = None
if len(sys.argv) > 5:
    try:
        STAGE = tuple(float(x) for x in sys.argv[5].split(','))
    except ValueError:
        STAGE = None

ex = MultiThreadedExecutor(num_threads=4)
ex.add_node(node)
th = threading.Thread(target=ex.spin, daemon=True)
th.start()

def observe(max_wait=8.0):
    g = Observe.Goal(); g.refresh = True; g.max_age_s = 0.0
    f = obs_c.send_goal_async(g)
    t0 = time.time()
    while not f.done() and time.time() - t0 < max_wait:
        time.sleep(0.005)
    if not f.done(): return None
    h = f.result()
    if h is None or not h.accepted: return None
    rf = h.get_result_async()
    t0 = time.time()
    while not rf.done() and time.time() - t0 < max_wait:
        time.sleep(0.005)
    if not rf.done(): return None
    ws = rf.result().result.world_state
    e = ws.robot.ee_pose.position
    boxes = {}
    for attr in ('objects', 'tracked_objects', 'items'):
        for o in (getattr(ws, attr, None) or []):
            try:
                p = o.pose.position
                boxes[o.name] = (round(p.x,5), round(p.y,5), round(p.z,5))
            except Exception:
                pass
    return {'ee': (round(e.x,5), round(e.y,5), round(e.z,5)), 'boxes': boxes,
            'grip': round(float(getattr(ws.robot,'gripper_position',0.0)),5)}

if STAGE is not None:
    g = MoveToPose.Goal(); g.request_id = 'stage'
    ps = PoseStamped(); ps.header.frame_id = 'world'
    ps.pose.position.x, ps.pose.position.y, ps.pose.position.z = STAGE
    ps.pose.orientation.w = 1.0
    g.target = ps; g.motion_profile_id = ''; g.expected_world_revision = 0; g.deadline_ms = 30000
    _f = mv_c.send_goal_async(g)
    _t0 = time.time()
    while not _f.done() and time.time() - _t0 < 60.0:
        time.sleep(0.005)
    _h = _f.result() if _f.done() else None
    _out = 'rejected'
    if _h is not None and _h.accepted:
        _rf = _h.get_result_async()
        _t0 = time.time()
        while not _rf.done() and time.time() - _t0 < 120.0:
            time.sleep(0.005)
        _out = str(_rf.result().result.outcome) if _rf.done() else 'timeout'
    sys.stderr.write('staging move to %s -> %s\n' % (STAGE, _out))

timeline = []
T0 = time.time()
def push_once(i):
    g = PushObject.Goal()
    g.object_name = OBJ
    g.direction.x = -1.0; g.direction.y = 0.0; g.direction.z = 0.0
    g.distance_m = DIST; g.contact_height_m = CONTACT_Z
    g.overdrive_m = float('nan')
    f = push_c.send_goal_async(g)
    while not f.done(): time.sleep(0.005)
    h = f.result()
    if h is None or not h.accepted: return None
    rf = h.get_result_async()
    # sample continuously while the goal runs
    while not rf.done():
        s = observe()
        if s:
            s['t'] = round(time.time()-T0, 3); s['phase'] = 'push_%d' % i
            timeline.append(s)
    r = rf.result().result
    s = observe()
    if s:
        s['t'] = round(time.time()-T0, 3); s['phase'] = 'push_%d_done' % i
        timeline.append(s)
    return {'outcome': int(r.outcome), 'error_code': int(r.error_code),
            'displacement_m': round(float(r.displacement_m),5),
            'displacement_along_direction_m': round(float(r.displacement_along_direction_m),5),
            'direction_cos': round(float(r.direction_cos),5),
            'contact_made': bool(r.contact_made),
            'ee_travel_m': round(float(r.ee_travel_m),5),
            'reach_error_m': round(float(r.reach_error_m),5),
            'increments_executed': int(r.increments_executed)}

s0 = observe()
if s0: s0['t']=round(time.time()-T0,3); s0['phase']='initial'; timeline.append(s0)
results = []
for i in (1, 2):
    results.append(push_once(i))
json.dump({'timeline': timeline, 'results': results}, open(OUT,'w'), indent=1)
print('SAMPLES', len(timeline))
for s in timeline:
    bx = s['boxes'].get(OBJ)
    print('  t=%6.2f %-13s ee_z=%.4f bx=%s' % (s['t'], s['phase'], s['ee'][2], bx))
for i,r in enumerate(results,1):
    if r: print('  RESULT %d disp=%.4f cos=%+.4f along=%+.4f contact=%s ee_travel=%.4f' % (i, r['displacement_m'], r['direction_cos'], r['displacement_along_direction_m'], r['contact_made'], r['ee_travel_m']))
ex.shutdown(); node.destroy_node(); rclpy.shutdown()