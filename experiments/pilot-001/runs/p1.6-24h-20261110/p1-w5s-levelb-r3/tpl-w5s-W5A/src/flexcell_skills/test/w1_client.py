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
import uuid

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String as StringMsg

from flexcell_interfaces.action import (
    Observe, PickObject, PlaceObject, RunDemo, RunPickPlace, VerifyObject)

SPEC = {
    'observe': (Observe, '/observe'),
    'pick': (PickObject, '/pick_object'),
    'place': (PlaceObject, '/place_object'),
    'verify': (VerifyObject, '/verify_object'),
    'task': (RunPickPlace, '/run_pick_place'),
    'demo': (RunDemo, '/run_demo'),
}


def name_of(cls, prefix, value):
    for k, v in vars(cls).items():
        if k.startswith(prefix) and isinstance(v, int) and v == value:
            return k
    return str(value)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--action', required=True, choices=sorted(SPEC) + ['inject'])
    ap.add_argument('--object', default='target_box')
    ap.add_argument('--pose', nargs=3, type=float, default=[0.12, -0.15, 0.0175])
    ap.add_argument('--tol', type=float, default=0.0)
    ap.add_argument('--skip-verify', action='store_true')
    ap.add_argument('--scenario', default='week1_demo_v1')
    ap.add_argument('--inject', default='')
    ap.add_argument('--inject-request-id', default='',
                    help='correlate the injection lifecycle transition')
    ap.add_argument('--expect-inject-state', default='',
                    help='seal the step: wait for this lifecycle state '
                         '(armed|cleared|applied|requested|idle) and exit '
                         'non-zero if it is not observed')
    ap.add_argument('--inject-timeout', type=float, default=8.0)
    ap.add_argument('--timeout', type=float, default=150.0)
    args = ap.parse_args()

    rclpy.init()
    n = Node('w1_client')
    # This CLI uses monotonic deadlines and zero-stamped goals. A simulation
    # clock subscription is unnecessary and can swamp its action waitable.
    from rclpy.executors import SingleThreadedExecutor
    executor = SingleThreadedExecutor()
    executor.add_node(n)

    # failure injection is a topic, not an action
    if args.action == 'inject':
        # Subscribe FIRST so the transition cannot be missed, then publish with
        # a request id and wait for the matching lifecycle state.  The old
        # fire-and-forget form let a lost request pass unnoticed, which is how a
        # benchmark episode ran under the wrong condition (2026-09-29).
        from rclpy.qos import (QoSDurabilityPolicy, QoSProfile,
                               QoSReliabilityPolicy)
        seen = []
        sub_qos = QoSProfile(depth=5)
        sub_qos.reliability = QoSReliabilityPolicy.RELIABLE
        sub_qos.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL
        n.create_subscription(StringMsg, '/flexcell/inject_status',
                              lambda m: seen.append(m.data), sub_qos)
        pub = n.create_publisher(StringMsg, '/flexcell/inject', 10)
        import time as _t
        deadline = _t.monotonic() + 5.0
        while pub.get_subscription_count() == 0 and _t.monotonic() < deadline:
            _t.sleep(0.1)
        if pub.get_subscription_count() == 0:
            print('INJECT WARNING: no subscriber matched; payload may be lost')
        payload = args.inject
        if args.inject_request_id:
            # a clear carries its id as a bare "#id" (nothing to suffix)
            payload = ('#%s' % args.inject_request_id if not payload
                       else '%s#%s' % (payload, args.inject_request_id))
        for _ in range(5):
            pub.publish(StringMsg(data=payload))
            _t.sleep(0.2)
        want = args.expect_inject_state
        if not want:
            want = 'armed' if payload else 'cleared'
        end = _t.monotonic() + args.inject_timeout
        got = None
        while _t.monotonic() < end:
            executor.spin_once(timeout_sec=0.1)
            for raw in list(seen):
                try:
                    snap = json.loads(raw)
                except ValueError:
                    continue
                if (snap.get('state') == want
                        and (not args.inject_request_id
                             or snap.get('request_id') == args.inject_request_id)):
                    got = snap
                    break
            if got is not None:
                break
        print('INJECT payload=%r expect=%s observed=%s'
              % (payload, want, json.dumps(got, sort_keys=True) if got else None))
        n.destroy_node()
        rclpy.shutdown()
        if got is None:
            print('INJECT FAILED: state %r not observed within %.1fs'
                  % (want, args.inject_timeout))
            return 3
        return 0

    cls, act = SPEC[args.action]
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
    elif args.action == 'demo':
        g.scenario_id = args.scenario
        extra['scenario_id'] = args.scenario

    print('SENDING action=%s object=%s pose=%s' % (args.action, args.object, args.pose),
          flush=True)
    t0 = time.monotonic()
    from unique_identifier_msgs.msg import UUID
    goal_uuid = UUID(uuid=list(uuid.uuid4().bytes))
    print('GOAL_UUID ' + bytes(goal_uuid.uuid).hex(), flush=True)
    send = cli.send_goal_async(g, goal_uuid=goal_uuid)
    while not send.done():
        executor.spin_once(timeout_sec=0.05)
        if time.monotonic() - t0 > min(30.0, args.timeout):
            print('CLIENT_GOAL_SEND_TIMEOUT: acceptance unknown; stop batch and inspect task state', flush=True)
            n.destroy_node()
            rclpy.shutdown()
            return 4
    gh = send.result()
    if gh is None or not gh.accepted:
        print(json.dumps({'client_error': 'goal rejected'}))
        return 3
    pending_results = [gh.get_result_async()]
    next_result_read = time.monotonic() + 5.0
    while not any(f.done() for f in pending_results):
        executor.spin_once(timeout_sec=0.05)
        if time.monotonic() >= next_result_read:
            # GetResult is idempotent and refers to this exact accepted goal.
            # Retry a lost read; never resend the robot's action goal.
            pending_results.append(gh.get_result_async())
            next_result_read = time.monotonic() + 5.0
        if time.monotonic() - t0 > args.timeout:
            print('CLIENT_TIMEOUT')
            gh.cancel_goal_async()
            return 4

    result_reply = next(f.result() for f in pending_results if f.done())
    if result_reply.status == 0:
        print('CLIENT_RESULT_UNKNOWN: server no longer retains this goal', flush=True)
        return 4
    r = result_reply.result
    out = {
        'action': args.action,
        'goal_uuid': bytes(goal_uuid.uuid).hex(),
        'outcome': name_of(cls.Result, 'OUTCOME_', r.outcome),
        'outcome_val': int(r.outcome),
        'error_code': name_of(cls.Result, 'ERR_', getattr(r, 'error_code', 0)),
        'detail': r.detail,
        'evidence_id': getattr(r, 'evidence_id', ''),
        'wall_seconds': round(time.monotonic() - t0, 3),
    }
    if args.action == 'observe':
        ws = r.world_state
        out['revision'] = int(ws.revision)
        out['source'] = ws.source
        out['objects'] = [{'name': o.name, 'available': bool(o.available),
                           'position': [round(o.pose.position.x, 4),
                                        round(o.pose.position.y, 4),
                                        round(o.pose.position.z, 4)]}
                          for o in ws.objects]
        out['carry'] = {'engaged': bool(ws.carry.engaged),
                        'object_id': ws.carry.object_id}
        out['zones'] = [{'id': z.id, 'occupancy': int(z.occupancy)}
                        for z in ws.zones]
        out['ee'] = [round(ws.robot.ee_pose.position.x, 4),
                     round(ws.robot.ee_pose.position.y, 4),
                     round(ws.robot.ee_pose.position.z, 4)]
        out['notes'] = list(ws.notes)
    if args.action == 'demo':
        out['fsm_trace'] = list(r.fsm_trace)
        out['object_a_at_zone'] = bool(r.object_a_at_zone)
        out['object_b_at_zone'] = bool(r.object_b_at_zone)
        out['zone_a_error_m'] = r.zone_a_error_m
        out['zone_b_error_m'] = r.zone_b_error_m
        out['run_id'] = r.run_id
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
