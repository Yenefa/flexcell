#!/usr/bin/env python3
"""Week-1 acceptance client: call observe/pick/place/verify/task, print JSON.

Usage:
  w1_client.py --action observe
  w1_client.py --action pick   --object target_box
  w1_client.py --action place  --object target_box --pose X Y Z
  w1_client.py --action verify --object target_box --pose X Y Z [--tol 0.05]
  w1_client.py --action task   --object target_box --pose X Y Z [--skip-verify]
"""
import argparse
import json
import sys
import time

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter

from geometry_msgs.msg import PoseStamped

from flexcell_interfaces.action import (
    Observe, PickObject, PlaceObject, RunPickPlace, VerifyObject)

SPEC = {
    'observe': (Observe, '/observe'),
    'pick': (PickObject, '/pick_object'),
    'place': (PlaceObject, '/place_object'),
    'verify': (VerifyObject, '/verify_object'),
    'task': (RunPickPlace, '/run_pick_place'),
}


def name_of(cls, prefix, value):
    for k, v in vars(cls).items():
        if k.startswith(prefix) and isinstance(v, int) and v == value:
            return k
    return str(value)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--action', required=True, choices=sorted(SPEC))
    ap.add_argument('--object', default='target_box')
    ap.add_argument('--pose', nargs=3, type=float, default=[0.12, -0.15, 0.0175])
    ap.add_argument('--tol', type=float, default=0.0)
    ap.add_argument('--skip-verify', action='store_true')
    ap.add_argument('--timeout', type=float, default=150.0)
    args = ap.parse_args()

    cls, act = SPEC[args.action]
    rclpy.init()
    n = Node('w1_client')
    n.set_parameters([Parameter('use_sim_time', value=True)])
    from rclpy.action import ActionClient
    cli = ActionClient(n, cls, act)

    if not cli.wait_for_server(timeout_sec=10.0):
        print(json.dumps({'client_error': 'action %s unavailable' % act}))
        return 2

    g = cls.Goal()
    pose = PoseStamped()
    pose.header.frame_id = 'world'
    pose.pose.position.x, pose.pose.position.y, pose.pose.position.z = args.pose
    pose.pose.orientation.w = 1.0

    extra = {}
    if args.action == 'observe':
        g.refresh = True
    elif args.action == 'pick':
        g.object_name = args.object
        g.motion_profile_id = 'demo_slow'
    elif args.action == 'place':
        g.object_name = args.object
        g.place_pose = pose
        g.motion_profile_id = 'demo_slow'
    elif args.action == 'verify':
        g.object_name = args.object
        g.expected_pose = pose.pose
        g.position_tolerance_m = args.tol
    elif args.action == 'task':
        g.object_name = args.object
        g.place_pose = pose
        g.motion_profile_id = 'demo_slow'
        g.skip_verify = args.skip_verify
        extra['skip_verify'] = args.skip_verify

    print('SENDING action=%s object=%s pose=%s' % (args.action, args.object, args.pose),
          flush=True)
    t0 = time.monotonic()
    send = cli.send_goal_async(g)
    while not send.done():
        rclpy.spin_once(n, timeout_sec=0.05)
    gh = send.result()
    if gh is None or not gh.accepted:
        print(json.dumps({'client_error': 'goal rejected'}))
        return 3
    rf = gh.get_result_async()
    while not rf.done():
        rclpy.spin_once(n, timeout_sec=0.05)
        if time.monotonic() - t0 > args.timeout:
            print('CLIENT_TIMEOUT')
            gh.cancel_goal_async()
            return 4

    r = rf.result().result
    out = {
        'action': args.action,
        'outcome': name_of(cls.Result, 'OUTCOME_', r.outcome),
        'outcome_val': int(r.outcome),
        'error_code': name_of(cls.Result, 'ERR_', getattr(r, 'error_code', 0)),
        'detail': r.detail,
        'wall_seconds': round(time.monotonic() - t0, 3),
    }
    if args.action == 'observe':
        ws = r.world_state
        out['revision'] = int(ws.revision)
        out['objects'] = [{'name': o.name,
                           'position': [round(o.pose.position.x, 4),
                                        round(o.pose.position.y, 4),
                                        round(o.pose.position.z, 4)]}
                          for o in ws.objects]
        out['notes'] = list(ws.notes)
    if args.action == 'pick':
        out['grasp_attached'] = bool(r.grasp_attached)
        out['motion_error_code'] = int(r.motion_error_code)
    if args.action == 'place':
        out['released'] = bool(r.released)
        out['motion_error_code'] = int(r.motion_error_code)
    if args.action == 'verify':
        out['verified'] = bool(r.verified)
        out['position_error_m'] = r.position_error_m
    if args.action == 'task':
        out['fsm_trace'] = list(r.fsm_trace)
        out['object_at_place'] = bool(r.object_at_place)
        out['final_position_error_m'] = r.final_position_error_m
    out.update(extra)
    print('RESULT ' + json.dumps(out, indent=2), flush=True)

    success_vals = {0}
    for attr in ('OUTCOME_SUCCEEDED', 'OUTCOME_VERIFIED'):
        if hasattr(cls.Result, attr):
            success_vals.add(getattr(cls.Result, attr))
    n.destroy_node()
    rclpy.shutdown()
    return 0 if int(r.outcome) in success_vals else 1


if __name__ == '__main__':
    sys.exit(main())
