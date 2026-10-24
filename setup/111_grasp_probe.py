#!/usr/bin/env python3
"""Grasp-only diagnostic with confirmed actions and canonical trial boundaries.

This sends real pick/place/reset commands to the running stack. It measures
physical pick results without changing the carry mechanism or recovery policy;
it is not a benchmark qualification or an authorization for a larger campaign.

Usage (ROS environment sourced, stack running):
    python3 setup/111_grasp_probe.py --object target_box_b --trials 5 --out /tmp/grasp_probe.jsonl
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import time
import uuid

from flexcell_skills.contracts.metrics import wilson
from flexcell_skills.skill_contract import check_pick, check_place


def call_action(executor, client, goal, timeout_s, stop_timeout_s):
    """One physical dispatch; on uncertainty cancel, inspect termination, stop.

    The caller must stop whenever harness_error is present, even if a late
    terminal result arrives. Cancel acknowledgement alone does not prove stop.
    """
    meta = dict(accepted=None, terminal_confirmed=False, ros_status=None,
                goal_uuid=None, harness_error=None)
    handle = result_future = result = None
    phase = 'goal acceptance'
    try:
        future = client.send_goal_async(goal)
        executor.spin_until_future_complete(future, timeout_sec=timeout_s)
        if not future.done():
            meta['harness_error'] = 'goal acceptance timed out; acceptance unknown'
            return None, meta
        handle = future.result()
        if handle is None:
            raise RuntimeError('missing goal handle')
        meta['accepted'] = bool(handle.accepted)
        goal_id = getattr(handle, 'goal_id', None)
        if goal_id is not None:
            meta['goal_uuid'] = bytes(goal_id.uuid).hex()
        if not handle.accepted:
            meta.update(terminal_confirmed=True, harness_error='goal rejected')
            return None, meta
        phase = 'action result'
        result_future = handle.get_result_async()
        executor.spin_until_future_complete(result_future, timeout_sec=timeout_s)
        if result_future.done():
            response = result_future.result()
            if response is not None and response.status in (4, 5, 6):
                meta.update(terminal_confirmed=True, ros_status=int(response.status))
                result = response.result
                if result is not None:
                    return result, meta
                meta['harness_error'] = 'terminal action has no result payload'
                return None, meta
            meta['harness_error'] = 'action result has no confirmed terminal status'
        else:
            meta['harness_error'] = 'action result timed out'
    except Exception as exc:  # transport errors never cause another goal
        meta['harness_error'] = '%s failed: %s' % (phase, type(exc).__name__)

    if handle is not None and meta['accepted']:
        try:
            cancel = handle.cancel_goal_async()
            executor.spin_until_future_complete(cancel, timeout_sec=stop_timeout_s)
            response = cancel.result() if cancel.done() else None
            meta['cancel_acknowledged'] = bool(response and response.goals_canceling)
        except Exception as exc:
            meta['cancel_error'] = type(exc).__name__
        try:
            if result_future is None:
                result_future = handle.get_result_async()
            executor.spin_until_future_complete(result_future, timeout_sec=stop_timeout_s)
            response = result_future.result() if result_future.done() else None
            if response is not None and response.status in (4, 5, 6):
                meta.update(terminal_confirmed=True, ros_status=int(response.status))
                result = response.result
        except Exception as exc:
            meta['terminal_read_error'] = type(exc).__name__
    return result, meta


def measured_position(pose):
    """Default ROS Pose has an all-zero quaternion, not a measured pose."""
    if pose is None:
        return None
    p, q = pose.position, pose.orientation
    position = [p.x, p.y, p.z]
    quaternion = [q.x, q.y, q.z, q.w]
    if not all(math.isfinite(v) for v in position + quaternion):
        return None
    if sum(v * v for v in quaternion) <= 0:
        return None
    return position


def capture_pick(result, meta):
    row = dict(action=meta, pick_ok=False)
    if result is None:
        return row
    before = measured_position(result.object_pose_before)
    after = measured_position(result.object_pose_after)
    rise = after[2] - before[2] if before is not None and after is not None else None
    if rise is not None and not math.isfinite(rise):
        rise = None
    row.update(outcome=int(result.outcome), error_code=int(result.error_code),
               status=int(result.status), grasp_attached=bool(result.grasp_attached),
               evidence_id=result.evidence_id, detail=result.detail,
               before=before, after=after,
               rise_m=rise)
    success = (meta.get('ros_status') == 4 and result.outcome == 0 and
               result.status == 1 and result.error_code == 0)
    failure = (meta.get('ros_status') == 6 and result.outcome == 1 and
               result.status == 2 and result.error_code != 0)
    if not success and not failure:
        row['harness_error'] = 'inconsistent ROS terminal / skill result contract'
    elif success:
        row['harness_error'] = check_pick(result)
        if row['harness_error'] is None and rise is None:
            row['harness_error'] = 'pick success has no finite measured poses/rise'
        if row['harness_error'] is None and row['rise_m'] <= 0:
            row['harness_error'] = 'pick success contradicts the measured nonpositive rise'
        row['pick_ok'] = row['harness_error'] is None
    return row


def run_probe(args, transport, sleep=time.sleep):
    """Offline tests drive the real trial loop through a fake transport."""
    rows = []
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, 'x', encoding='utf-8') as stream:
        for trial in range(1, args.trials + 1):
            t0 = time.monotonic()
            row = dict(trial=trial, object_name=args.object)
            ready = transport.prepare()
            row['precondition'] = ready
            if not ready['ok']:
                row['harness_error'] = 'canonical reset or injection clear failed'
            else:
                result, meta = transport.pick(args.object)
                row.update(capture_pick(result, meta))
                row['harness_error'] = meta['harness_error'] or row.get('harness_error')
                if row['pick_ok'] and not row['harness_error']:
                    # Restore this object's measured start, including B's y.
                    placed, release = transport.place(args.object, row['before'])
                    row['release'] = release
                    if placed is not None:
                        release.update(outcome=int(placed.outcome), error_code=int(placed.error_code),
                                       status=int(placed.status), released=bool(placed.released),
                                       evidence_id=placed.evidence_id, detail=placed.detail,
                                       measured_after=measured_position(placed.object_pose_after))
                    if (release['harness_error'] or placed is None or release['ros_status'] != 4
                            or placed.outcome != 0 or placed.status != 1 or placed.error_code != 0):
                        row['harness_error'] = 'place did not confirm success'
                    else:
                        violation = check_place(placed)
                        if violation is None and release['measured_after'] is None:
                            violation = 'place success has no finite measured pose'
                        if violation:
                            row['harness_error'] = violation
                        else:
                            sleep(args.release_s)
                    terminal = release['terminal_confirmed']
                else:
                    terminal = meta['terminal_confirmed']
                # Never reset while acceptance or action termination is unknown.
                if terminal:
                    cleanup = transport.reset()
                    row['cleanup'] = cleanup
                    if not cleanup['ok']:
                        row['harness_error'] = row['harness_error'] or 'cleanup reset failed'
                else:
                    row['cleanup'] = dict(ok=False, not_run='action termination unknown')
            row['elapsed_s'] = round(time.monotonic() - t0, 3)
            rows.append(row)
            stream.write(json.dumps(row, allow_nan=False) + '\n')
            stream.flush()
            print('trial %d/%d: pick_ok=%s error=%s harness=%s' % (
                trial, args.trials, row.get('pick_ok'), row.get('error_code'), row.get('harness_error')), flush=True)
            if row.get('harness_error'):
                break
            sleep(args.settle_s)
    return rows


class RosProbe:
    def __init__(self, args):
        import rclpy
        from rclpy.action import ActionClient
        from rclpy.executors import SingleThreadedExecutor
        from rclpy.node import Node
        from flexcell_interfaces.action import PickObject, PlaceObject
        from geometry_msgs.msg import PoseStamped
        self.args, self.rclpy = args, rclpy
        self.PickObject, self.PlaceObject, self.PoseStamped = PickObject, PlaceObject, PoseStamped
        rclpy.init()
        self.node = Node('grasp_probe')
        self.executor = SingleThreadedExecutor()
        self.executor.add_node(self.node)
        self.pick_client = ActionClient(self.node, PickObject, '/pick_object')
        self.place_client = ActionClient(self.node, PlaceObject, '/place_object')

    def ready(self):
        return (self.pick_client.wait_for_server(timeout_sec=30.0)
                and self.place_client.wait_for_server(timeout_sec=30.0))

    def reset(self):
        admin = Path(__file__).resolve().with_name('flexcell_admin.py')
        try:
            proc = subprocess.run([sys.executable, str(admin), 'reset'], capture_output=True,
                                  text=True, timeout=self.args.reset_timeout_s)
            try:
                report = json.loads(proc.stdout)
            except ValueError:
                report = None
            return dict(ok=proc.returncode == 0 and isinstance(report, dict) and report.get('ok') is True,
                        rc=proc.returncode, report=report, stdout=proc.stdout, stderr=proc.stderr)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return dict(ok=False, error='reset failed: %s' % type(exc).__name__)

    def prepare(self):
        reset = self.reset()
        if not reset['ok']:
            return dict(ok=False, reset=reset)
        client = Path(__file__).resolve().parents[1] / 'src/flexcell/flexcell_skills/test/w1_client.py'
        try:
            clear = subprocess.run([sys.executable, str(client), '--action', 'inject', '--inject', '',
                                    '--inject-request-id', uuid.uuid4().hex,
                                    '--expect-inject-state', 'cleared'], capture_output=True,
                                   text=True, timeout=60)
            return dict(ok=clear.returncode == 0, reset=reset,
                        injection_clear=dict(rc=clear.returncode, stdout=clear.stdout, stderr=clear.stderr))
        except (OSError, subprocess.TimeoutExpired) as exc:
            return dict(ok=False, reset=reset, error='injection clear failed: %s' % type(exc).__name__)

    def pick(self, object_name):
        goal = self.PickObject.Goal()
        goal.object_name, goal.motion_profile_id = object_name, 'demo_slow'
        return call_action(self.executor, self.pick_client, goal,
                           self.args.timeout_s, self.args.stop_timeout_s)

    def place(self, object_name, position):
        goal = self.PlaceObject.Goal()
        goal.object_name, goal.motion_profile_id = object_name, 'demo_slow'
        goal.place_pose = self.PoseStamped()
        goal.place_pose.header.frame_id = 'world'
        p = goal.place_pose.pose.position
        p.x, p.y, p.z = position
        goal.place_pose.pose.orientation.w = 1.0
        return call_action(self.executor, self.place_client, goal,
                           self.args.timeout_s, self.args.stop_timeout_s)

    def close(self):
        self.executor.shutdown()
        self.node.destroy_node()
        if self.rclpy.ok():
            self.rclpy.shutdown()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--trials', type=int, default=20)
    ap.add_argument('--object', default='target_box_a')
    default_out = Path.home() / '.ros/flexcell/grasp_probe' / (
        'grasp_%s_%s.jsonl' % (time.strftime('%Y%m%d_%H%M%S'), uuid.uuid4().hex[:8]))
    ap.add_argument('--out', default=str(default_out))
    ap.add_argument('--settle-s', type=float, default=2.0)
    ap.add_argument('--timeout-s', type=float, default=60.0)
    ap.add_argument('--release-s', type=float, default=1.5)
    ap.add_argument('--stop-timeout-s', type=float, default=5.0)
    ap.add_argument('--reset-timeout-s', type=float, default=300.0)
    args = ap.parse_args()
    if Path(args.out).exists():
        ap.error('output already exists; use a new evidence path')
    if args.trials < 1 or not args.object.strip():
        ap.error('positive trials and a nonempty object are required')
    if any(not math.isfinite(getattr(args, key)) or getattr(args, key) <= 0
           for key in ('timeout_s', 'stop_timeout_s', 'reset_timeout_s')):
        ap.error('timeouts must be finite and positive')
    if any(not math.isfinite(getattr(args, key)) or getattr(args, key) < 0
           for key in ('settle_s', 'release_s')):
        ap.error('settle/release waits must be finite and nonnegative')
    probe = RosProbe(args)
    try:
        if not probe.ready():
            print('HARNESS_ERROR: pick/place action servers unavailable', file=sys.stderr)
            return 2
        rows = run_probe(args, probe)
        valid = [r for r in rows if 'outcome' in r and not r.get('harness_error')]
        good = [r for r in valid if r['pick_ok']]
        grasp_fail = [r for r in valid if r['error_code'] == 23]
        lo, hi = wilson(len(good), len(valid))
        print('Observed picks: %d/%d succeeded; Wilson95 [%.3f, %.3f]; grasp failures=%d' % (
            len(good), len(valid), lo, hi, len(grasp_fail)))
        rises = [r['rise_m'] for r in valid if r.get('rise_m') is not None]
        if rises:
            print('Measured rise: min=%+.4f median=%+.4f max=%+.4f' % (
                min(rises), statistics.median(rises), max(rises)))
        print('Rows: %s; diagnostic observations only, not benchmark qualification' % args.out)
        return int(any(r.get('harness_error') for r in rows))
    finally:
        probe.close()


if __name__ == '__main__':
    sys.exit(main())
