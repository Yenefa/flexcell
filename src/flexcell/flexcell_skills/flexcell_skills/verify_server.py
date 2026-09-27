#!/usr/bin/env python3
"""FlexCell Verify skill server (Week 1).

Measures an object's actual (gz ground-truth) pose and compares it with the
expectation. Success is measured, never inherited - same doctrine as Day 2.
"""

import math
import time

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from flexcell_interfaces.action import VerifyObject

from flexcell_skills.common import (
    JsonlLog, crash_detail, dist3, new_evidence, pose_msg, sample_gz_pose)
from flexcell_skills.contracts.skill_result import derive_status

R = VerifyObject.Result


class VerifyServer(Node):

    def __init__(self):
        super().__init__('verify_server')

        self.declare_parameter('default_tolerance_m', 0.05)
        self.declare_parameter('log_dir', '~/.ros/flexcell')
        self.declare_parameter('log_file', 'verify.jsonl')

        gp = self.get_parameter
        self._default_tol = float(gp('default_tolerance_m').value)
        self._log = JsonlLog(self, gp('log_dir').value, gp('log_file').value)
        self._seq = 0

        self._server = ActionServer(
            self, VerifyObject, 'verify_object',
            execute_callback=self._execute,
            goal_callback=lambda req: GoalResponse.ACCEPT,
            cancel_callback=lambda gh: CancelResponse.ACCEPT,
            callback_group=ReentrantCallbackGroup())

        self.get_logger().info(
            'Verify server up | default_tolerance=%.3fm' % self._default_tol)

    def _execute(self, goal_handle):
        t0 = time.monotonic()
        goal = goal_handle.request
        self._seq += 1
        rid, evidence = new_evidence('', self._seq)

        res = R()
        rec = {
            'request_id': rid,
            'evidence_id': evidence,
            'object_name': goal.object_name,
            'tolerance_m': goal.position_tolerance_m or self._default_tol,
        }

        def finish(outcome, error, detail, succeed):
            # single finalization point (SkillResult v2: status derives here)
            res.outcome = outcome
            res.status = derive_status('VERIFY', outcome)
            res.error_code = error
            res.detail = detail
            res.evidence_id = evidence
            rec.update(outcome=str(outcome), error_code=int(error),
                       status=int(res.status), detail=detail,
                       elapsed_ms=int((time.monotonic() - t0) * 1000))
            self._log.write(rec)
            if succeed:
                goal_handle.succeed()
            else:
                goal_handle.abort()
            return res

        try:
            sampled, err = sample_gz_pose(goal.object_name)
            if sampled is None:
                return finish(R.OUTCOME_FAILED, R.ERR_OBJECT_UNKNOWN, err, False)

            position, quat = sampled
            exp = goal.expected_pose
            ep = [exp.position.x, exp.position.y, exp.position.z]
            error = dist3(position, ep)
            tol = goal.position_tolerance_m if goal.position_tolerance_m > 0 else self._default_tol
            verified = error <= tol

            res.measured_pose = pose_msg(position, quat)
            res.has_measured_pose = True
            res.position_error_m = error
            res.verified = verified
            rec.update(measured=position, expected=ep, position_error_m=error,
                       verified=verified)
            if verified:
                return finish(R.OUTCOME_VERIFIED, R.ERR_NONE,
                              'measured within %.3fm of expected (err=%.4f)' % (tol, error),
                              True)
            # a mismatch is a valid, honest verification result
            return finish(R.OUTCOME_MISMATCH, R.ERR_NONE,
                          ('measured [%s] outside %.3fm of expected [%s] (err=%.4f)'
                           % (['%.3f' % v for v in position], tol,
                              ['%.3f' % v for v in ep], error)),
                          True)
        except Exception as exc:  # crash guard (issue #20): a raising execute
            # callback must become a typed FAILURE - rclpy's fallback default
            # Result has outcome=0, which for VerifyObject reads as VERIFIED
            return finish(R.OUTCOME_FAILED, R.ERR_INTERNAL, crash_detail(exc), False)


def main(args=None):
    rclpy.init(args=args)
    node = VerifyServer()
    ex = MultiThreadedExecutor(num_threads=4)
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
