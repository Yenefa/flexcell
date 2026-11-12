import sys, os, json, time
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from PIL import Image as PImage
import numpy as np

OUT, DUR, RATE = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
os.makedirs(OUT, exist_ok=True)
meta = []
last = [0.0]

class Grab(Node):
    def __init__(self):
        super().__init__('cam_grab')
        self.create_subscription(Image, '/flexcell/camera/rgb', self.cb, 10)
    def cb(self, msg):
        now = time.time()
        if now - last[0] < 1.0 / RATE:
            return
        last[0] = now
        h, w = msg.height, msg.width
        buf = np.frombuffer(bytes(msg.data), dtype=np.uint8)
        enc = msg.encoding.lower()
        if enc == 'bgr8':
            arr = buf.reshape((h, w, 3))[:, :, ::-1]
        elif enc == 'rgba8':
            arr = buf.reshape((h, w, 4))[:, :, :3]
        else:
            arr = buf.reshape((h, w, 3))
        name = 'f_%06.2f.png' % (now % 1000)
        p = os.path.join(OUT, name)
        PImage.fromarray(arr).save(p)
        meta.append({'file': name, 'w': w, 'h': h, 'enc': msg.encoding,
                     'bytes': os.path.getsize(p), 't': round(now, 3)})
        print('saved', name, w, 'x', h, os.path.getsize(p), flush=True)

rclpy.init()
g = Grab()
t0 = time.time()
while time.time() - t0 < DUR:
    rclpy.spin_once(g, timeout_sec=0.2)
json.dump(meta, open(os.path.join(OUT, 'frames.json'), 'w'), indent=2)
print('TOTAL_FRAMES', len(meta), flush=True)
g.destroy_node(); rclpy.shutdown()