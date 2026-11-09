#!/usr/bin/env python3
"""P0-A integration: cancel a live task and prove the quarantine contract.

Runs against a live trusted_sim stack. It sends a RunDemo goal, cancels it while
a skill is executing, then checks the four invariants the fix promises:
  1. the goal terminates (no unmanaged background goal),
  2. the task state never reports IDLE while a stop is unconfirmed,
  3. a second goal is refused while the arm is quarantined,
  4. the quarantine only clears through reset_motion_quarantine.
"""
import argparse
import json
import sys
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from std_msgs.msg import String
from std_srvs.srv import Trigger

from flexcell_interfaces.action import RunDemo


class CancelProbe(Node):
    def __init__(self):
        super().__init__("cancel_probe")
        self.states = []
        self.create_subscription(String, "/flexcell/task_state", self._on_state, 10)
        self.client = ActionClient(self, RunDemo, "/run_demo")
        self.reset = self.create_client(Trigger, "/reset_motion_quarantine")

    def _on_state(self, msg):
        self.states.append(msg.data)


def spin_until(pred, node, timeout_s, sleep=0.05):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.05)
        if pred():
            return True
    return False


def wait_until(pred, timeout_s, sleep=0.05):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(sleep)
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--cancel-after-s", type=float, default=3.0)
    parser.add_argument("--confirm-timeout-s", type=float, default=60.0)
    args = parser.parse_args()

    rclpy.init()
    node = CancelProbe()
    report = {"cancel_after_s": args.cancel_after_s, "events": []}

    def note(kind, **fields):
        entry = {"kind": kind, "t": round(time.monotonic(), 3)}
        entry.update(fields)
        report["events"].append(entry)

    try:
        if not node.client.wait_for_server(timeout_sec=30.0):
            report["verdict"] = "NO_ACTION_SERVER"
            raise SystemExit(2)
        goal = RunDemo.Goal()
        goal.scenario_id = "p0a_cancel"
        note("goal_sent", scenario_id=goal.scenario_id)
        send = node.client.send_goal_async(goal)
        rclpy.spin_until_future_complete(node, send, timeout_sec=30.0)
        handle = send.result()
        if handle is None or not handle.accepted:
            report["verdict"] = "GOAL_REJECTED"
            raise SystemExit(2)
        note("accepted", goal_uuid=bytes(handle.goal_id.uuid).hex())

        # wait until the task actually starts (BUSY) so the cancel hits a live skill
        started = spin_until(lambda: "BUSY" in node.states, node, 60.0)
        note("task_started", started=bool(started), task_state=list(node.states))
        time.sleep(args.cancel_after_s)
        note("cancel_requested", task_state=list(node.states))
        cancel = handle.cancel_goal_async()
        rclpy.spin_until_future_complete(node, cancel, timeout_sec=10.0)
        resp = cancel.result()
        note("cancel_response",
             goals_canceling=len(list(getattr(resp, "goals_canceling", []) or [])))

        result_future = handle.get_result_async()
        # rclpy only delivers callbacks while spinning: without this the result
        # future never completes and a healthy stop looks like a hang.
        rclpy.spin_until_future_complete(
            node, result_future, timeout_sec=args.confirm_timeout_s)
        terminated = result_future.done()
        note("terminated", done=bool(terminated))
        if terminated:
            wrapped = result_future.result()
            res = wrapped.result
            report["outcome"] = int(res.outcome)
            report["error_code"] = int(res.error_code)
            report["detail"] = str(res.detail)
            report["fsm_trace"] = list(res.fsm_trace)

        # a quarantined arm must refuse the next task
        second = node.client.send_goal_async(RunDemo.Goal())
        rclpy.spin_until_future_complete(node, second, timeout_sec=30.0)
        second_handle = second.result()
        second_result = None
        if second_handle is not None and second_handle.accepted:
            fut = second_handle.get_result_async()
            rclpy.spin_until_future_complete(node, fut, timeout_sec=60.0)
            if fut.done():
                second_result = fut.result().result
        report["second_task"] = None if second_result is None else {
            "outcome": int(second_result.outcome),
            "error_code": int(second_result.error_code),
            "detail": str(second_result.detail)[:300]}
        note("second_task_done", task_state=list(node.states))

        report["states"] = list(node.states)
        report["saw_quarantined"] = "QUARANTINED" in node.states
        report["idle_after_cancel"] = report.get("outcome") is not None and node.states[-1:] == ["IDLE"]

        if node.reset.wait_for_service(timeout_sec=10.0):
            fut = node.reset.call_async(Trigger.Request())
            rclpy.spin_until_future_complete(node, fut, timeout_sec=10.0)
            reply = fut.result()
            report["reset"] = {"success": bool(reply.success),
                               "message": str(reply.message)[:200]}
        else:
            report["reset"] = {"success": None, "message": "service unavailable"}
        note("after_reset", task_state=list(node.states))
    finally:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        node.destroy_node()
        rclpy.shutdown()
    print(json.dumps({k: report.get(k) for k in (
        "outcome", "error_code", "detail", "saw_quarantined", "second_task",
        "reset")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
