import sys, os, json, time
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from PIL import Image as PImage
import numpy as np

OUT = sys.argv[1]
MAXN = int(sys.argv[2]) if len(sys.argv) > 2 else 6
os.makedirs(OUT, exist_ok=True)
n = [0]
meta = []

class Grab(Node):
    def __init__(self):
        super().__init__('cam_grab')
        self.create_subscription(Image, '/flexcell/camera/rgb', self.cb, 10)
    def cb(self, msg):
        if n[0] >= MAXN: return
        n[0] += 1
        h, w = msg.height, msg.width
        buf = np.frombuffer(bytes(msg.data), dtype=np.uint8)
        enc = msg.encoding.lower()
        if enc in ('rgb8', 'r8g8b8'):
            arr = buf.reshape((h, w, 3))
        elif enc == 'bgr8':
            arr = buf.reshape((h, w, 3))[:, :, ::-1]
        elif enc == 'rgba8':
            arr = buf.reshape((h, w, 4))[:, :, :3]
        else:
            arr = buf.reshape((h, w, 3))
        p = os.path.join(OUT, 'frame_%02d.png' % n[0])
        PImage.fromarray(arr).save(p)
        meta.append({'file': os.path.basename(p), 'w': w, 'h': h, 'encoding': msg.encoding,
                     't': round(time.time(), 3)})
        print('saved', p, w, 'x', h, msg.encoding, flush=True)

rclpy.init()
g = Grab()
t0 = time.time()
while n[0] < MAXN and time.time() - t0 < 25:
    rclpy.spin_once(g, timeout_sec=0.5)
json.dump(meta, open(os.path.join(OUT, 'frames.json'), 'w'), indent=2)
print('TOTAL_FRAMES', n[0], flush=True)
g.destroy_node(); rclpy.shutdown()