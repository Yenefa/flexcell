#!/usr/bin/env python3
"""Grasp-only probe: measure servo grasp reliability WITHOUT the rest of the
demo, so a 100-trial run takes ~15 min instead of ~75.

Why this exists
---------------
The dominant physical failure in this workcell is the carry/teleport servo
intermittently failing to lift the box:

    box_rise_m ~= -0.001 .. -0.006  ->  ERR_GRASP_FAILED (23)
    -> ERR_RECOVERY_EXHAUSTED (51)

Running a full S1 demo to observe it costs ~45 s/episode, and the failure is
rare enough that n=5 tells you nothing. This probe issues /pick_object directly,
releases, and records the measured rise so the failure RATE can be estimated.

It measures only. It does not change the servo, the grasp offset, the contact
model, or the recovery budget - those are other people's decisions.

Read-only with respect to the repo and to the Gazebo stack: it uses the running
stack and writes a JSONL of its own.

Usage:
    python3 setup/111_grasp_probe.py --trials 20 --out /tmp/grasp_probe.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import uuid


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--trials', type=int, default=20)
    ap.add_argument('--object', default='target_box_a')
    ap.add_argument('--out', default='/tmp/grasp_probe.jsonl')
    ap.add_argument('--settle-s', type=float, default=2.0)
    ap.add_argument('--timeout-s', type=float, default=60.0)
    ap.add_argument('--release-s', type=float, default=1.5)
    args = ap.parse_args()

    import rclpy
    from rclpy.action import ActionClient
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.node import Node
    from flexcell_interfaces.action import PickObject, PlaceObject
    from geometry_msgs.msg import PoseStamped

    rclpy.init()
    node = Node('grasp_probe')
    # Persistent executor: rclpy's spin_once(node) removes the node after one
    # callback, which is exactly the defect that broke w1_client on 2026-10-01.
    executor = SingleThreadedExecutor()
    executor.add_node(node)

    pick = ActionClient(node, PickObject, '/pick_object')
    place = ActionClient(node, PlaceObject, '/place_object')

    print('waiting for /pick_object and /place_object ...', flush=True)
    if not pick.wait_for_server(timeout_sec=30.0):
        print('FAIL: /pick_object never appeared', file=sys.stderr)
        return 2
    if not place.wait_for_server(timeout_sec=30.0):
        print('FAIL: /place_object never appeared', file=sys.stderr)
        return 2

    rows = []
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as fh:
        for i in range(args.trials):
            t0 = time.monotonic()

            goal = PickObject.Goal()
            goal.object_name = args.object
            goal.motion_profile_id = 'demo_slow'
            goal.expected_world_revision = 0
            goal.deadline_ms = 0

            fut = pick.send_goal_async(goal)
            executor.spin_until_future_complete(fut, timeout_sec=args.timeout_s)
            handle = fut.result()
            if handle is None or not handle.accepted:
                row = {'trial': i + 1, 'accepted': False, 'reason': 'goal rejected'}
                rows.append(row)
                fh.write(json.dumps(row) + '\n')
                fh.flush()
                print('  %2d/%d  REJECTED' % (i + 1, args.trials), flush=True)
                continue

            rf = handle.get_result_async()
            executor.spin_until_future_complete(rf, timeout_sec=args.timeout_s)
            res = rf.result()
            if res is None:
                row = {'trial': i + 1, 'accepted': True, 'reason': 'no result'}
                rows.append(row)
                fh.write(json.dumps(row) + '\n')
                fh.flush()
                print('  %2d/%d  NO RESULT' % (i + 1, args.trials), flush=True)
                continue

            before = res.result.object_pose_before.position
            after = res.result.object_pose_after.position
            rise = after.z - before.z
            row = {
                'trial': i + 1,
                'accepted': True,
                'outcome': int(res.result.outcome),
                'error_code': int(res.result.error_code),
                'status': int(res.result.status),
                'grasp_attached': bool(res.result.grasp_attached),
                'rise_m': round(rise, 6),
                'after_z': round(after.z, 6),
                'before_z': round(before.z, 6),
                'elapsed_s': round(time.monotonic() - t0, 3),
                'detail': res.result.detail[:160],
            }

            # Release so the next trial starts from the same pose.
            try:
                pg = PlaceObject.Goal()
                pg.object_name = args.object
                pg.motion_profile_id = 'demo_slow'
                pg.expected_world_revision = 0
                pg.deadline_ms = 0
                pg.place_pose = PoseStamped()
                pg.place_pose.header.frame_id = 'world'
                pg.place_pose.pose.position.x = 0.220
                pg.place_pose.pose.position.y = 0.000
                pg.place_pose.pose.position.z = 0.0175
                pf = place.send_goal_async(pg)
                executor.spin_until_future_complete(pf, timeout_sec=args.timeout_s)
                ph = pf.result()
                if ph is not None and ph.accepted:
                    prf = ph.get_result_async()
                    executor.spin_until_future_complete(prf, timeout_sec=args.timeout_s)
                    pr = prf.result()
                    if pr is not None:
                        row['release'] = {
                            'outcome': int(pr.result.outcome),
                            'error_code': int(pr.result.error_code),
                        }
            except Exception as exc:  # noqa: BLE001 - recorded, never hidden
                row['release'] = {'error': type(exc).__name__}

            rows.append(row)
            fh.write(json.dumps(row) + '\n')
            fh.flush()
            print('  %2d/%d  outcome=%d err=%d rise=%+.4f attached=%s  %.1fs'
                  % (i + 1, args.trials, row['outcome'], row['error_code'],
                     row['rise_m'], row['grasp_attached'], row['elapsed_s']),
                  flush=True)

            time.sleep(args.settle_s)

    good = [r for r in rows if r.get('accepted') and r.get('error_code') == 0]
    grasp_fail = [r for r in rows if r.get('error_code') == 23]
    other = [r for r in rows
             if r.get('accepted') and r.get('error_code') not in (0, 23, None)]
    rises = [r['rise_m'] for r in good]

    def wilson(k, n, z=1.96):
        if n == 0:
            return (0.0, 1.0)
        p = k / n
        d = 1 + z * z / n
        c = p + z * z / (2 * n)
        h = z * (p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5
        return (max(0.0, (c - h) / d), min(1.0, (c + h) / d))

    n = len([r for r in rows if r.get('accepted')])
    k = len(good)
    lo, hi = wilson(k, n) if n else (0.0, 1.0)

    print()
    print('=== GRASP PROBE SUMMARY ===')
    print('  trials:            %d' % len(rows))
    print('  goal accepted:     %d' % n)
    print('  grasp OK (err 0):  %d' % k)
    print('  ERR_GRASP_FAILED:  %d' % len(grasp_fail))
    print('  other errors:      %d  %s' % (len(other),
                                           [r.get('error_code') for r in other]))
    if n:
        print('  success rate:      %d/%d = %.3f  Wilson95 [%.3f, %.3f]'
              % (k, n, k / n, lo, hi))
    if rises:
        print('  rise_m on success: min=%+.4f p50=%+.4f max=%+.4f'
              % (min(rises), statistics.median(rises), max(rises)))
    fr = [r['rise_m'] for r in grasp_fail]
    if fr:
        print('  rise_m on FAILURE: min=%+.4f max=%+.4f  (negative = never lifted)'
              % (min(fr), max(fr)))
    print('  rows: %s' % args.out)
    print()
    print('  NOTE: a Wilson interval this wide cannot separate a real grasp')
    print('  regression from servo jitter. It bounds the rate, nothing finer.')

    node.destroy_node()
    executor.shutdown()
    rclpy.shutdown()
    return 0


if __name__ == '__main__':
    sys.exit(main())
