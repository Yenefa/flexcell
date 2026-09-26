#!/usr/bin/env python3
"""FlexCell deterministic pick-and-place task FSM (Week 1).

Strict sequential FSM over the four skills:

    OBSERVE -> PICK -> PLACE -> VERIFY

No LLM, no Jev, no planning policy - exactly the deterministic baseline the
upstream roadmap requires before any Task Policy work. One task at a time
(single-arm mutual exclusion). Cancellation is honoured between states; a
canceled mid-task leaves the robot in the state the skills left it in and
reports honestly.
"""

import time

import rclpy
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from geometry_msgs.msg import PoseStamped

from flexcell_interfaces.action import (
    Observe, PickObject, PlaceObject, RunPickPlace, VerifyObject)

from flexcell_skills.common import JsonlLog, new_evidence

R = RunPickPlace.Result


def err_name(cls, prefix, value):
    for k, v in vars(cls).items():
        if k.startswith(prefix) and isinstance(v, int) and v == value:
            return k
    return str(value)


class TaskFsmServer(Node):

    def __init__(self):
        super().__init__('task_fsm_server')

        self.declare_parameter('observe_action', '/observe')
        self.declare_parameter('pick_action', '/pick_object')
        self.declare_parameter('place_action', '/place_object')
        self.declare_parameter('verify_action', '/verify_object')
        self.declare_parameter('default_place_tolerance_m', 0.05)
        self.declare_parameter('skill_wait_s', 90.0)
        self.declare_parameter('log_dir', '~/.ros/flexcell')
        self.declare_parameter('log_file', 'task_fsm.jsonl')

        gp = self.get_parameter
        self._cli_observe = ActionClient(self, Observe, gp('observe_action').value,
                                         callback_group=ReentrantCallbackGroup())
        self._cli_pick = ActionClient(self, PickObject, gp('pick_action').value,
                                      callback_group=ReentrantCallbackGroup())
        self._cli_place = ActionClient(self, PlaceObject, gp('place_action').value,
                                       callback_group=ReentrantCallbackGroup())
        self._cli_verify = ActionClient(self, VerifyObject, gp('verify_action').value,
                                        callback_group=ReentrantCallbackGroup())
        self._tol = float(gp('default_place_tolerance_m').value)
        self._skill_wait = float(gp('skill_wait_s').value)
        self._log = JsonlLog(self, gp('log_dir').value, gp('log_file').value)

        self._busy = False
        self._seq = 0

        self._server = ActionServer(
            self, RunPickPlace, 'run_pick_place',
            execute_callback=self._execute,
            goal_callback=lambda req: GoalResponse.ACCEPT,
            cancel_callback=lambda gh: CancelResponse.ACCEPT,
            callback_group=ReentrantCallbackGroup())

        self.get_logger().info('Task FSM server up | OBSERVE->PICK->PLACE->VERIFY')

    def _call_skill(self, cli, goal, state, trace, rec, deadline_s, goal_handle=None, t0=None):
        """Call one skill; returns (result, None) or (None, detail)."""
        trace.append(state)
        if goal_handle is not None:
            fb = RunPickPlace.Feedback()
            fb.state = state
            fb.elapsed_ms = int((time.monotonic() - t0) * 1000) if t0 else 0
            goal_handle.publish_feedback(fb)
        if not cli.wait_for_server(timeout_sec=10.0):
            return None, '%s skill server unavailable' % state
        send = cli.send_goal_async(goal)
        t0 = time.monotonic()
        while not send.done():
            if time.monotonic() - t0 > 15.0:
                return None, '%s goal send timeout' % state
            time.sleep(0.02)
        gh = send.result()
        if gh is None or not gh.accepted:
            return None, '%s goal rejected' % state
        rf = gh.get_result_async()
        while not rf.done():
            if time.monotonic() - t0 > deadline_s:
                gh.cancel_goal_async()
                return None, '%s result timeout (cancel sent)' % state
            time.sleep(0.05)
        result = rf.result().result
        rec['%s_result' % state.lower()] = {
            'outcome': int(result.outcome),
            'error_code': int(getattr(result, 'error_code', 0)),
            'detail': getattr(result, 'detail', ''),
        }
        return result, None

    def _execute(self, goal_handle):
        t0 = time.monotonic()
        goal = goal_handle.request
        self._seq += 1
        rid, evidence = new_evidence(goal.object_name, self._seq)
        res = R()
        trace = []
        rec = {
            'request_id': rid, 'evidence_id': evidence,
            'object_name': goal.object_name,
            'place': [goal.place_pose.pose.position.x,
                      goal.place_pose.pose.position.y,
                      goal.place_pose.pose.position.z],
        }

        def finish(outcome, error, detail):
            res.outcome = outcome
            res.error_code = error
            res.detail = detail
            res.fsm_trace = trace
            res.evidence_id = evidence
            rec.update(outcome=str(outcome), error_code=int(error), detail=detail,
                       trace=list(trace),
                       elapsed_ms=int((time.monotonic() - t0) * 1000))
            self._log.write(rec)
            if outcome == R.OUTCOME_SUCCEEDED:
                goal_handle.succeed()
            elif outcome == R.OUTCOME_CANCELED:
                goal_handle.canceled()
            else:
                goal_handle.abort()
            return res

        # ---------- admission ----------
        if self._busy:
            return finish(R.OUTCOME_FAILED, R.ERR_RESOURCE_BUSY,
                          'another task is active')
        self._busy = True
        try:
            if not goal.object_name:
                return finish(R.OUTCOME_FAILED, R.ERR_OBJECT_UNKNOWN,
                              'object_name is empty')
            pp = goal.place_pose.pose.position
            deadline_s = self._skill_wait

            # ---------- OBSERVE ----------
            if goal_handle.is_cancel_requested:
                return finish(R.OUTCOME_CANCELED, R.ERR_CANCELED,
                              'canceled before OBSERVE')
            g = Observe.Goal()
            g.refresh = True
            result, err = self._call_skill(self._cli_observe, g, 'OBSERVE', trace, rec, 30.0, goal_handle=goal_handle, t0=t0)
            if err:
                return finish(R.OUTCOME_FAILED, R.ERR_SKILL_FAILED,
                              'OBSERVE failed: %s' % err)
            if int(result.outcome) != Observe.Result.OUTCOME_SUCCEEDED:
                return finish(R.OUTCOME_FAILED, R.ERR_SKILL_FAILED,
                              'OBSERVE failed: %s' % result.detail)
            res.detail = result.detail

            # ---------- PICK ----------
            if goal_handle.is_cancel_requested:
                return finish(R.OUTCOME_CANCELED, R.ERR_CANCELED,
                              'canceled before PICK (trace=%s)' % ','.join(trace))
            g = PickObject.Goal()
            g.object_name = goal.object_name
            g.motion_profile_id = goal.motion_profile_id
            result, err = self._call_skill(self._cli_pick, g, 'PICK', trace, rec, deadline_s, goal_handle=goal_handle, t0=t0)
            if err:
                return finish(R.OUTCOME_FAILED, R.ERR_SKILL_FAILED,
                              'PICK failed: %s' % err)
            if int(result.outcome) != PickObject.Result.OUTCOME_SUCCEEDED:
                return finish(R.OUTCOME_FAILED, R.ERR_SKILL_FAILED,
                              'PICK failed: %s (%s)' % (err_name(
                                  PickObject.Result, 'ERR_', int(result.error_code)),
                                  result.detail))

            # ---------- PLACE ----------
            if goal_handle.is_cancel_requested:
                return finish(R.OUTCOME_CANCELED, R.ERR_CANCELED,
                              'canceled before PLACE (box is attached; robot left '
                              'holding the object - trace=%s)' % ','.join(trace))
            g = PlaceObject.Goal()
            g.object_name = goal.object_name
            g.place_pose = PoseStamped()
            g.place_pose.header.frame_id = 'world'
            g.place_pose.pose.position = pp
            g.place_pose.pose.orientation.w = 1.0
            g.motion_profile_id = goal.motion_profile_id
            result, err = self._call_skill(self._cli_place, g, 'PLACE', trace, rec, deadline_s, goal_handle=goal_handle, t0=t0)
            if err:
                return finish(R.OUTCOME_FAILED, R.ERR_SKILL_FAILED,
                              'PLACE failed: %s' % err)
            if int(result.outcome) != PlaceObject.Result.OUTCOME_SUCCEEDED:
                return finish(R.OUTCOME_FAILED, R.ERR_SKILL_FAILED,
                              'PLACE failed: %s (%s)' % (err_name(
                                  PlaceObject.Result, 'ERR_', int(result.error_code)),
                                  result.detail))

            # ---------- VERIFY ----------
            res.object_at_place = False
            if goal.skip_verify:
                trace.append('VERIFY(skipped)')
                res.object_at_place = True   # PLACE already verified internally
                return finish(R.OUTCOME_SUCCEEDED, R.ERR_NONE,
                              'task done (VERIFY skipped; PLACE drop check passed)')

            if goal_handle.is_cancel_requested:
                return finish(R.OUTCOME_CANCELED, R.ERR_CANCELED,
                              'canceled before VERIFY (trace=%s)' % ','.join(trace))
            g = VerifyObject.Goal()
            g.object_name = goal.object_name
            g.expected_pose = goal.place_pose.pose
            g.position_tolerance_m = self._tol
            result, err = self._call_skill(self._cli_verify, g, 'VERIFY', trace, rec, 30.0, goal_handle=goal_handle, t0=t0)
            if err:
                return finish(R.OUTCOME_FAILED, R.ERR_SKILL_FAILED,
                              'VERIFY failed: %s' % err)
            if int(result.outcome) == VerifyObject.Result.OUTCOME_VERIFIED:
                res.object_at_place = True
                res.final_position_error_m = result.position_error_m
                return finish(R.OUTCOME_SUCCEEDED, R.ERR_NONE,
                              'task done: object verified at place (err=%.4f)'
                              % result.position_error_m)
            res.final_position_error_m = result.position_error_m
            return finish(R.OUTCOME_FAILED, R.ERR_SKILL_FAILED,
                          'VERIFY mismatch: %s' % result.detail)

        finally:
            self._busy = False


def main(args=None):
    rclpy.init(args=args)
    node = TaskFsmServer()
    ex = MultiThreadedExecutor(num_threads=6)
    ex.add_node(node)
    try:
        ex.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
