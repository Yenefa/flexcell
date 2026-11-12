import sys, json, time
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy
from tf2_msgs.msg import TFMessage

OUT = sys.argv[1]
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 90.0
fh = open(OUT, 'w')
t0 = time.time()
stats = {'tf': 0, 'ws': 0}

def em(rec):
    rec['t'] = round(time.time() - t0, 4)
    fh.write(json.dumps(rec) + '\n')

class R(Node):
    def __init__(self):
        super().__init__('pose_rec')
        self.create_subscription(TFMessage, '/tf', self.tf_cb, 50)
        try:
            self.create_subscription(TFMessage, '/flexcell/world_state', self.ws_cb, 50)
        except Exception:
            pass
    def tf_cb(self, msg):
        for tr in msg.transforms:
            p = tr.transform.translation; q = tr.transform.rotation
            em({'k': 'tf', 'f': tr.child_frame_id, 'p': [p.x, p.y, p.z],
                'q': [q.x, q.y, q.z, q.w]})
            stats['tf'] += 1
    def ws_cb(self, msg):
        stats['ws'] += 1
        try:
            d = {f: getattr(msg, f) for f in ('name', 'pose', 'objects', 'models') if hasattr(msg, f)}
            em({'k': 'ws', 'raw': str(d)[:1500]})
        except Exception as e:
            em({'k': 'ws', 'err': str(e)})

rclpy.init()
n = R()
while time.time() - t0 < DUR:
    rclpy.spin_once(n, timeout_sec=0.1)
fh.close()
print('STATS', stats, flush=True)