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

from flexcell_skills.common import JsonlLog, dist3, new_evidence, pose_msg, sample_gz_pose

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

        sampled, err = sample_gz_pose(goal.object_name)
        if sampled is None:
            res.outcome = R.OUTCOME_FAILED
            res.error_code = R.ERR_OBJECT_UNKNOWN
            res.detail = err
            res.evidence_id = evidence
            rec.update(outcome='FAILED', error_code=res.error_code, detail=err)
            self._log.write(rec)
            goal_handle.abort()
            return res

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
        res.evidence_id = evidence
        rec.update(measured=position, expected=ep, position_error_m=error,
                   verified=verified)
        if verified:
            res.outcome = R.OUTCOME_VERIFIED
            res.error_code = R.ERR_NONE
            res.detail = 'measured within %.3fm of expected (err=%.4f)' % (tol, error)
            rec['outcome'] = 'VERIFIED'
            goal_handle.succeed()
        else:
            res.outcome = R.OUTCOME_MISMATCH
            res.error_code = R.ERR_NONE
            res.detail = ('measured [%s] outside %.3fm of expected [%s] (err=%.4f)'
                          % (['%.3f' % v for v in position], tol,
                             ['%.3f' % v for v in ep], error))
            rec['outcome'] = 'MISMATCH'
            goal_handle.succeed()  # a mismatch is a valid, honest verification result
        self._log.write(rec)
        return res


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
