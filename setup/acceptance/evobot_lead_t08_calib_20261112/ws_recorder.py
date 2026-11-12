import sys, json, time
import rclpy
from rclpy.node import Node
from flexcell_interfaces.msg import WorldState

OUT = sys.argv[1]
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 90.0
fh = open(OUT, 'w')
t0 = time.time()
n = [0]

class R(Node):
    def __init__(self):
        super().__init__('ws_rec')
        self.create_subscription(WorldState, '/flexcell/world_state', self.cb, 20)
    def cb(self, msg):
        n[0] += 1
        e = msg.robot.ee_pose.position
        objs = []
        for o in getattr(msg, 'objects', []) or []:
            try:
                p = o.pose.position
                objs.append({'name': o.name, 'x': round(p.x,5), 'y': round(p.y,5), 'z': round(p.z,5)})
            except Exception:
                objs.append({'raw': str(o)[:80]})
        fh.write(json.dumps({'t': round(time.time()-t0,4),
                             'ee': [round(e.x,5), round(e.y,5), round(e.z,5)],
                             'grip': round(float(msg.robot.gripper_position),5),
                             'objs': objs}) + '\n')

rclpy.init()
r = R()
while time.time()-t0 < DUR:
    rclpy.spin_once(r, timeout_sec=0.1)
fh.close()
print('WORLDSTATE_SAMPLES', n[0], flush=True)