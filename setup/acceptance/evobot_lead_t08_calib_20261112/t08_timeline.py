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
try:
    from control_msgs.action import FollowJointTrajectory
except ImportError:
    FollowJointTrajectory = None

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

# WAIT FOR THE CONTROLLER ACTION BEFORE STAGING.
# move_to_pose does not execute directly - it plans and then forwards the trajectory to
# /arm_controller/follow_joint_trajectory (move_to_pose_server.py:845). Issuing the staging move
# immediately after launch raced that server's start-up: every logged staging move came back
# 'unavailable' with 2 s on the wait_for_server timeout, i.e. the server was not there yet. The
# arm moved partway, which is why the pitch changed, but the goal was never accepted.
# Waiting here converts that constant silent failure into a real move - which CHANGES the starting
# pose the push gets, so this must be measured, not assumed to help.
if STAGE is not None and FollowJointTrajectory is not None:
    _fjt = ActionClient(node, FollowJointTrajectory, '/arm_controller/follow_joint_trajectory')
    if _fjt.wait_for_server(timeout_sec=30.0):
        sys.stderr.write('controller action available before staging\n')
    else:
        sys.stderr.write('WARNING: controller action NOT available after 30 s; staging will likely fail\n')

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
    # DID IT ACTUALLY TRY? Round 72 found a failure mode with ZERO gripper-box contacts and ee z
    # frozen at its start value for the whole phase: the action returned a result, a push_N phase
    # was recorded, and no motion happened. Scoring that as a task failure conflates "could not
    # push it" with "did not try". This mirrors stage_ok, which exists on the staging move for
    # the same reason.
    # A push is considered to have executed if the end effector DESCENDED by more than 10 mm
    # during the phase. The approach always starts at the neutral height (~0.187) and the contact
    # height is ~0.020, so a real push clears this by a factor of ten; a no-op stays at 0.000.
    _phase = [x for x in timeline if x.get('phase') == 'push_%d' % i]
    _zs = [x['ee'][2] for x in _phase if x.get('ee')]
    _drop = (max(_zs) - min(_zs)) if _zs else 0.0
    if not (_drop > 0.010):
        sys.stderr.write('push_%d DID NOT EXECUTE: ee descended only %.4f m over %d samples\n'
                         % (i, _drop, len(_zs)))
    return {'outcome': int(r.outcome), 'error_code': int(r.error_code),
            'ee_descent_m': round(_drop, 4),
            'push_executed': bool(_drop > 0.010),
            'displacement_m': round(float(r.displacement_m),5),
            'displacement_along_direction_m': round(float(r.displacement_along_direction_m),5),
            'direction_cos': round(float(r.direction_cos),5),
            'contact_made': bool(r.contact_made),
            'ee_travel_m': round(float(r.ee_travel_m),5),
            'reach_error_m': round(float(r.reach_error_m),5),
            'increments_executed': int(r.increments_executed)}

s0 = observe()
if s0: s0['t']=round(time.time()-T0,3); s0['phase']='initial'; timeline.append(s0)
# REPEAT COUNT DEFAULTS TO 1. Running two pushes was a diagnostic choice and it invalidated a
# graded run: measured on T08-push-seed3001, push_1 left the box 0.0372 m from the zone centre
# (inside the 0.06 radius, 0.1371 m travelled, cosine 0.9999 - a pass), and push_2 then moved it
# a further 0.0746 m to 0.10981 m out, with total travel 0.20865 m against a 0.15 ceiling. The
# task failed because the second push undid the first. argv[6] overrides for diagnostics.
REPEATS = 1
if len(sys.argv) > 6:
    try:
        REPEATS = max(1, int(sys.argv[6]))
    except ValueError:
        REPEATS = 1
results = []
for i in range(1, REPEATS + 1):
    results.append(push_once(i))
json.dump({'timeline': timeline, 'results': results}, open(OUT,'w'), indent=1)
print('SAMPLES', len(timeline))
for s in timeline:
    bx = s['boxes'].get(OBJ)
    print('  t=%6.2f %-13s ee_z=%.4f bx=%s' % (s['t'], s['phase'], s['ee'][2], bx))
for i,r in enumerate(results,1):
    if r: print('  RESULT %d disp=%.4f cos=%+.4f along=%+.4f contact=%s ee_travel=%.4f' % (i, r['displacement_m'], r['direction_cos'], r['displacement_along_direction_m'], r['contact_made'], r['ee_travel_m']))
ex.shutdown(); node.destroy_node(); rclpy.shutdown()