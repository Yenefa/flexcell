#!/usr/bin/env python3
"""Print the current end-effector pose from TF (real state, not MoveIt's belief)."""
import sys
import time

import rclpy
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.parameter import Parameter
from tf2_ros import Buffer, TransformListener


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else 'world'
    link = sys.argv[2] if len(sys.argv) > 2 else 'end_effector_link'
    rclpy.init()
    n = Node('ee_probe')
    n.set_parameters([Parameter('use_sim_time', value=True)])
    buf = Buffer()
    TransformListener(buf, n)
    end = time.time() + 6.0
    while time.time() < end:
        rclpy.spin_once(n, timeout_sec=0.1)
    try:
        tr = buf.lookup_transform(base, link, rclpy.time.Time(), Duration(seconds=2.0))
    except Exception as exc:  # noqa: BLE001
        print('LOOKUP_FAILED', exc)
        n.destroy_node()
        rclpy.shutdown()
        sys.exit(1)
    t = tr.transform.translation
    q = tr.transform.rotation
    print('POS %.6f %.6f %.6f' % (t.x, t.y, t.z))
    print('QUAT %.6f %.6f %.6f %.6f' % (q.x, q.y, q.z, q.w))
    n.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
