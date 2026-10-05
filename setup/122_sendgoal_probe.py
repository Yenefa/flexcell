#!/usr/bin/env python3
"""Non-motion ROS probe: delayed acceptance, original-goal cancellation, admission."""
import argparse
import json
from pathlib import Path
import threading
import time

import rclpy
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from flexcell_interfaces.action import Observe
from flexcell_skills.common import JsonlLog
from flexcell_skills.task_fsm_server import TaskFsmServer


class Probe(Node):
    _send_skill_goal = TaskFsmServer._send_skill_goal
    _poll_late_skill_goals = TaskFsmServer._poll_late_skill_goals
    _has_pending_skill_goal = TaskFsmServer._has_pending_skill_goal

    def __init__(self, out):
        super().__init__('flexcell_sendgoal_probe')
        self._send_guard_lock = threading.Lock()
        self._admission = threading.Lock()
        self._pending_skill_sends = {}
        self._active_task_run_id = 'controlled_late_acceptance'
        self._skill_transport_log = JsonlLog(self, str(out.parent), out.stem + '_transport.jsonl')
        self.states, self.goals = [], []
        self.create_timer(.02, self._poll_late_skill_goals,
                          callback_group=ReentrantCallbackGroup())
        self.server = ActionServer(
            self, Observe, '/flexcell_probe/late_observe',
            goal_callback=self.accept, execute_callback=self.execute,
            cancel_callback=lambda handle: CancelResponse.ACCEPT,
            callback_group=ReentrantCallbackGroup())
        self.client = ActionClient(self, Observe, '/flexcell_probe/late_observe',
                                   callback_group=ReentrantCallbackGroup())

    def _publish_task_state(self, value):
        self.states.append(value)

    def accept(self, request):
        # Controlled acceptance delay; no robot, world snapshot, or physical goal.
        time.sleep(.3)
        return GoalResponse.ACCEPT

    def execute(self, handle):
        row = dict(goal_uuid=bytes(handle.goal_id.uuid).hex(), started_ns=time.monotonic_ns())
        self.goals.append(row)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if handle.is_cancel_requested:
                row['canceled_ns'] = time.monotonic_ns()
                handle.canceled()
                result = Observe.Result()
                result.outcome = Observe.Result.OUTCOME_CANCELED
                return result
            time.sleep(.01)
        handle.abort()
        result = Observe.Result()
        result.outcome = Observe.Result.OUTCOME_FAILED
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), 'Preserve prior evidence'
    args.out.parent.mkdir(parents=True, exist_ok=True)
    rclpy.init()
    probe = Probe(args.out)
    executor = MultiThreadedExecutor(num_threads=6)
    executor.add_node(probe)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    try:
        assert probe.client.wait_for_server(timeout_sec=5)
        handle, error = probe._send_skill_goal(probe.client, Observe.Goal(), 'PROBE', timeout_s=.06)
        blocked = probe._has_pending_skill_goal()
        assert handle is None and error == 'PROBE goal send timeout' and blocked
        deadline = time.monotonic() + 6
        while probe._has_pending_skill_goal() and time.monotonic() < deadline:
            time.sleep(.02)
        rows = [json.loads(line) for line in Path(probe._skill_transport_log.path).read_text().splitlines()]
        assert len(probe.goals) == 1 and 'canceled_ns' in probe.goals[0]
        assert not probe._has_pending_skill_goal()
        assert rows[-1]['event'] == 'late_goal_terminal' and rows[-1]['status'] == 5
        assert all(r['goal_uuid'] == probe.goals[0]['goal_uuid'] for r in rows)
        result = dict(ok=True, controlled_acceptance_delay_s=.3, send_deadline_s=.06,
                      timed_out=True, blocked_until_terminal=blocked, physical_dispatches=0,
                      ros_goal_requests=sum(r['event'] == 'goal_send_requested' for r in rows),
                      ros_goals_executed=len(probe.goals), canceled_original_goal=True,
                      resolved=True, goals=probe.goals, events=rows, states=probe.states,
                      scope='Non-motion actual ROS action communication; intentional delayed server acceptance')
        args.out.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))
    finally:
        executor.shutdown(timeout_sec=3)
        thread.join(timeout=3)
        probe.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
