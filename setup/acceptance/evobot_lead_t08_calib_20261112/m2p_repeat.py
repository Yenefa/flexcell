"""Does move_to_pose converge if asked repeatedly for the SAME point?

Motivation: archived ec 30 details show the approach abandoned at 22.8/25.4/24.1 mm
against a 20 mm window. If a second or third attempt lands closer, a retry in the
recovery layer is the in-scope fix. If residual plateaus above 20 mm, retrying is not
the answer and the constraint is elsewhere.
"""
import sys, json, time
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import PoseStamped
from flexcell_interfaces.action import Observe, MoveToPose

OUT = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 5
TX = float(sys.argv[3]) if len(sys.argv) > 3 else 0.107
TY = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
TZ = float(sys.argv[5]) if len(sys.argv) > 5 else 0.0200

rclpy.init()
node = Node('m2p_rep')
ob = ActionClient(node, Observe, 'observe')
mv = ActionClient(node, MoveToPose, 'move_to_pose')
ob.wait_for_server(timeout_sec=30.0)
mv.wait_for_server(timeout_sec=30.0)

def snapshot():
    g = Observe.Goal(); g.refresh = True; g.max_age_s = 0.0
    f = ob.send_goal_async(g)
    rclpy.spin_until_future_complete(node, f, timeout_sec=30.0)
    h = f.result()
    if h is None or not h.accepted: return None
    rf = h.get_result_async()
    rclpy.spin_until_future_complete(node, rf, timeout_sec=30.0)
    ws = rf.result().result.world_state
    e = ws.robot.ee_pose.position
    return (round(e.x,6), round(e.y,6), round(e.z,6))

rows = []
start = snapshot()
print('start ee =', start)
for i in range(1, N+1):
    g = MoveToPose.Goal()
    g.request_id = 'rep-%02d' % i
    ps = PoseStamped()
    ps.header.frame_id = 'world'
    ps.pose.position.x = TX; ps.pose.position.y = TY; ps.pose.position.z = TZ
    ps.pose.orientation.w = 1.0
    g.target = ps
    g.motion_profile_id = ''
    g.expected_world_revision = 0
    g.deadline_ms = 30000
    f = mv.send_goal_async(g)
    rclpy.spin_until_future_complete(node, f, timeout_sec=60.0)
    h = f.result()
    if h is None or not h.accepted:
        rows.append({'attempt': i, 'err': 'rejected'}); continue
    rf = h.get_result_async()
    rclpy.spin_until_future_complete(node, rf, timeout_sec=120.0)
    r = rf.result().result
    e = snapshot()
    dx = (e[0]-TX) if e else float('nan')
    dy = (e[1]-TY) if e else float('nan')
    dz = (e[2]-TZ) if e else float('nan')
    dist = (dx*dx+dy*dy+dz*dz) ** 0.5 if e else float('nan')
    row = {'attempt': i, 'ee': e,
           'outcome': int(getattr(r,'outcome',-1)),
           'error_code': int(getattr(r,'error_code',-1)),
           'position_error_m': float(getattr(r,'position_error_m',float('nan'))),
           'detail': str(getattr(r,'detail',''))[:160],
           'dist_from_target_m': round(dist,6)}
    rows.append(row)
    print('  %d: outcome=%d ec=%d reported_err=%.4f  actual_dist=%.4f  ee=%s' %
          (i, row['outcome'], row['error_code'], row['position_error_m'], dist, e))
    if row['detail']: print('     detail:', row['detail'])
json.dump({'target': [TX,TY,TZ], 'start': start, 'rows': rows}, open(OUT,'w'), indent=1)
node.destroy_node(); rclpy.shutdown()