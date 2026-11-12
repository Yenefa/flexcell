import sys, json, time, traceback
OUT = sys.argv[1]
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 90.0
log = open(OUT + '.err', 'w')
try:
    import rclpy
    from rclpy.node import Node
    from flexcell_interfaces.msg import WorldState
    log.write('imports OK\n'); log.flush()
except Exception:
    log.write('IMPORT FAIL\n' + traceback.format_exc()); log.flush(); sys.exit(3)
fh = open(OUT, 'w')
t0 = time.time()
n = [0]

class R(Node):
    def __init__(self):
        super().__init__('ws_rec')
        self.create_subscription(WorldState, '/flexcell/world_state', self.cb, 20)
        log.write('node created\n'); log.flush()
    def cb(self, msg):
        try:
            n[0] += 1
            e = msg.robot.ee_pose.position
            objs = []
            for o in (getattr(msg, 'objects', None) or []):
                p = o.pose.position
                objs.append([o.name, round(p.x,5), round(p.y,5), round(p.z,5)])
            fh.write(json.dumps({'t': round(time.time()-t0,4),
                'ee': [round(e.x,5), round(e.y,5), round(e.z,5)],
                'g': round(float(msg.robot.gripper_position),5),
                'o': objs}) + '\n')
            fh.flush()
        except Exception:
            log.write('CB FAIL ' + traceback.format_exc()[:400]); log.flush()

rclpy.init()
r = R()
while time.time()-t0 < DUR:
    rclpy.spin_once(r, timeout_sec=0.1)
fh.close(); log.write('SAMPLES %d\n' % n[0]); log.close()
print('SAMPLES', n[0])