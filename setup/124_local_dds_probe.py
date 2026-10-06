#!/usr/bin/env python3
"""Two-process, non-motion DDS discovery and controller late-acceptance probe."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import rclpy
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from control_msgs.action import FollowJointTrajectory
from moveit_msgs.msg import RobotTrajectory
from std_srvs.srv import Trigger
from flexcell_skills.move_to_pose_server import MoveToPoseServer

ACTION = '/flexcell_probe/local_controller'
SERVICE = '/flexcell_probe/local_ready'


class Peer(Node):
    _send_for_execution = MoveToPoseServer._send_for_execution
    _poll_backend_goals = MoveToPoseServer._poll_backend_goals
    _quarantine_backend = MoveToPoseServer._quarantine_backend
    _backend_event = MoveToPoseServer._backend_event
    _wait = MoveToPoseServer._wait

    def __init__(self, role):
        super().__init__('flexcell_local_probe_' + role)
        self.records, self.goals, self.service_calls = [], [], 0
        self._backend, self._fjt_action = 'controller_action', ACTION
        self._active_motion_ids = ('synthetic', 'synthetic-evidence')
        self._backend_guard, self._pending_backend_goals = threading.Lock(), {}
        group = ReentrantCallbackGroup()
        if role == 'server':
            self.create_service(Trigger, SERVICE, self.ready, callback_group=group)
            self.server = ActionServer(self, FollowJointTrajectory, ACTION,
                goal_callback=self.accept, cancel_callback=lambda h: CancelResponse.ACCEPT,
                execute_callback=self.execute, callback_group=group)
        else:
            self.client = self.create_client(Trigger, SERVICE, callback_group=group)
            self._fjt_client = ActionClient(self, FollowJointTrajectory, ACTION, callback_group=group)
            self.create_timer(.02, self._poll_backend_goals, callback_group=group)

    def _log(self, row):
        self.records.append(row)

    _controller_event_log = _log

    def ready(self, request, response):
        self.service_calls += 1
        response.success, response.message = True, 'synthetic non-motion peer'
        return response

    def accept(self, request):
        time.sleep(.3)
        return GoalResponse.ACCEPT

    def execute(self, handle):
        row = dict(goal_uuid=bytes(handle.goal_id.uuid).hex(), started_ns=time.monotonic_ns())
        self.goals.append(row)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not handle.is_cancel_requested:
            time.sleep(.01)
        row['canceled'] = handle.is_cancel_requested
        if row['canceled']:
            handle.canceled()
        else:
            handle.abort()
        return FollowJointTrajectory.Result()


def child(role, out):
    rclpy.init()
    node = Peer(role)
    executor = MultiThreadedExecutor(num_threads=6)
    executor.add_node(node)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    result = dict(role=role, physical_dispatches=0)
    try:
        if role == 'server':
            deadline = time.monotonic() + 50
            while time.monotonic() < deadline:
                if node.service_calls == 20 and node.goals and node.goals[0].get('canceled'):
                    break
                time.sleep(.05)
            result.update(service_calls=node.service_calls, goals=node.goals)
            result['ok'] = node.service_calls == 20 and len(node.goals) == 1 and node.goals[0].get('canceled')
            # Allow the last RPC result to reach the other process before closing.
            time.sleep(.2)
        else:
            discovered = node.client.wait_for_service(timeout_sec=10)
            rows = []
            if discovered:
                for index in range(20):
                    start = time.monotonic_ns()
                    future = node.client.call_async(Trigger.Request())
                    deadline = time.monotonic() + 2
                    while not future.done() and time.monotonic() < deadline:
                        time.sleep(.005)
                    row = dict(index=index, completed=future.done(), elapsed_ms=(time.monotonic_ns()-start)/1e6)
                    if future.done():
                        try:
                            row['ready'] = future.result().success
                        except Exception as exc:
                            row['error'] = type(exc).__name__
                    rows.append(row)
            assert node._fjt_client.wait_for_server(timeout_sec=5), 'synthetic controller unavailable'
            status, _, _, _ = node._send_for_execution(RobotTrajectory(), time.monotonic()+.06)
            initially_blocked = bool(node._pending_backend_goals)
            deadline = time.monotonic() + 8
            while node._pending_backend_goals and time.monotonic() < deadline:
                time.sleep(.02)
            result.update(discovered=discovered, service_rows=rows, send_status=status,
                          initially_blocked=initially_blocked, resolved=not node._pending_backend_goals,
                          controller_events=node.records)
            result['ok'] = (len(rows)==20 and all(r.get('ready') for r in rows)
                            and status=='send_timeout' and initially_blocked
                            and result['resolved'] and node.records[-1].get('status')==5)
    finally:
        out.write_text(json.dumps(result, indent=2)+'\n')
        executor.shutdown(timeout_sec=3)
        thread.join(timeout=3)
        node.destroy_node()
        rclpy.shutdown()
    return 0 if result.get('ok') else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--role', choices=('run', 'server', 'client'), default='run')
    ap.add_argument('--profile', type=Path)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    assert not args.out.exists(), 'Preserve previous evidence'
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.role != 'run':
        return child(args.role, args.out)
    assert os.environ.get('ROS_DOMAIN_ID') == '45'
    env = dict(os.environ)
    if args.profile:
        env['CYCLONEDDS_URI'] = str(args.profile.resolve())
    children = {}
    server_path = args.out.with_suffix('.server.json')
    client_path = args.out.with_suffix('.client.json')
    with args.out.with_suffix('.server.log').open('w') as server_log:
        server = subprocess.Popen([sys.executable, __file__, '--role', 'server', '--out', str(server_path)],
                                  env=env, stdout=server_log, stderr=subprocess.STDOUT)
        try:
            with args.out.with_suffix('.client.log').open('w') as client_log:
                client = subprocess.run([sys.executable, __file__, '--role', 'client', '--out', str(client_path)],
                                        env=env, stdout=client_log, stderr=subprocess.STDOUT, timeout=45)
            children['client_rc'] = client.returncode
            children['server_rc'] = server.wait(timeout=10)
        finally:
            if server.poll() is None:
                server.terminate()
                children['server_rc'] = server.wait(timeout=5)
    data = dict(children, profile=env.get('CYCLONEDDS_URI'), ros_domain_id=45,
                physical_dispatches=0, scope='Two independent ROS processes; synthetic endpoints only')
    data['ok'] = all(value == 0 for value in children.values())
    args.out.write_text(json.dumps(data, indent=2)+'\n')
    print(json.dumps(data, indent=2))
    return 0 if data['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
