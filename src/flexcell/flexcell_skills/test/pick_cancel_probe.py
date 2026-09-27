#!/usr/bin/env python3
"""Cancel a PICK mid-motion and verify the arm actually stops (audit P0-3).

The four skill servers used to ignore cancellation entirely: a canceled PICK
kept moving to the end and still reported SUCCEEDED.  This probe needs the
LIVE stack (gazebo + moveit + skill servers); it is deliberately NOT named
test_* so plain pytest/colcon test never collects it.

Verdict (JSON on stdout, exit 0/1):
  outcome == OUTCOME_CANCELED(2), error_code == ERR_CANCELED(32), and the
  joint velocities are back to ~0 after the cancel response.
"""
import json
import sys
import threading
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node

from sensor_msgs.msg import JointState

from flexcell_interfaces.action import PickObject


def main():
    rclpy.init()
    node = Node('pick_cancel_probe')
    cli = ActionClient(node, PickObject, '/pick_object')
    if not cli.wait_for_server(timeout_sec=15.0):
        print(json.dumps({'verdict': 'FAIL', 'why': 'pick server unavailable'}))
        return 1

    js = {'msg': None}

    def on_js(msg):
        js['msg'] = msg

    node.create_subscription(JointState, '/joint_states', on_js, 10)
    spin = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spin.start()

    g = PickObject.Goal()
    g.object_name = 'target_box_a'
    send = cli.send_goal_async(g)
    t0 = time.monotonic()
    while not send.done() and time.monotonic() - t0 < 15:
        time.sleep(0.05)
    gh = send.result()
    if gh is None or not gh.accepted:
        print(json.dumps({'verdict': 'FAIL', 'why': 'goal rejected'}))
        return 1

    res_f = gh.get_result_async()
    time.sleep(4.0)   # mid-APPROACH: the demo_slow approach takes ~10 s
    cancel_t = time.monotonic()
    gh.cancel_goal_async()

    t0 = time.monotonic()
    while not res_f.done() and time.monotonic() - t0 < 60:
        time.sleep(0.05)
    if not res_f.done():
        print(json.dumps({'verdict': 'FAIL', 'why': 'no result after cancel'}))
        return 1
    res = res_f.result().result

    # give the stopped controller 2 s to drain, then read residual velocity
    time.sleep(2.0)
    msg = js['msg']
    peak = max((abs(v) for v in (msg.velocity if msg and msg.velocity else [])),
               default=None)

    ok = (int(res.outcome) == PickObject.Result.OUTCOME_CANCELED
          and int(res.error_code) == PickObject.Result.ERR_CANCELED
          and peak is not None and peak < 0.02)
    print(json.dumps({
        'verdict': 'PASS' if ok else 'FAIL',
        'outcome': int(res.outcome), 'error_code': int(res.error_code),
        'detail': res.detail, 'cancel_to_result_s':
            round(time.monotonic() - cancel_t, 2),
        'peak_velocity_after_stop': peak,
    }))
    rclpy.shutdown()
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
