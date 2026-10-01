#!/usr/bin/env python3
"""FlexCell Place skill server (Week 1).

Approach (hover, descend) -> detach + open gripper -> verify drop -> retreat.
Requires the object to be currently attached (planning scene check). The drop
is verified by ground truth: the box must settle within tolerance of the place
pose, otherwise PLACE_FAILED - honest either way.
"""

import threading
import time

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from std_srvs.srv import Trigger

from flexcell_interfaces.action import PlaceObject

from flexcell_skills.contracts.skill_result import derive_status
from flexcell_skills.common import (
    GripperClient, JsonlLog, MoveToPoseClient, PlanningSceneOps,
    crash_detail, dist3, interruptible_sleep, new_evidence, pose_msg,
    sample_gz_pose, wait_future)

R = PlaceObject.Result
F = PlaceObject.Feedback

PHASES = {
    'VALIDATING': F.PHASE_VALIDATING,
    'APPROACHING': F.PHASE_APPROACHING,
    'RELEASING': F.PHASE_RELEASING,
    'VERIFYING': F.PHASE_VERIFYING,
    'RETREATING': F.PHASE_RETREATING,
}


class PlaceServer(Node):

    def __init__(self):
        super().__init__('place_server')

        self.declare_parameter('move_to_pose_action', '/move_to_pose')
        self.declare_parameter('gripper_action', '/gripper_controller/gripper_cmd')
        self.declare_parameter('gripper_open_position', 0.02)
        self.declare_parameter('release_hover_m', 0.10)
        self.declare_parameter('release_clearance_m', 0.012)
        self.declare_parameter('carry_offset_m', 0.16)
        self.declare_parameter('place_tolerance_m', 0.06)
        self.declare_parameter('settle_time_s', 1.0)
        self.declare_parameter('retreat_m', 0.10)
        self.declare_parameter('carry_stop_topic', '/flexcell/carry_stop')
        self.declare_parameter('carry_release_service', '/flexcell/carry_release')
        self.declare_parameter('object_size', [0.035, 0.035, 0.035])
        self.declare_parameter('default_deadline_ms', 30000)
        self.declare_parameter('motion_profile_names', ['demo_veryslow', 'demo_slow', 'demo_default'])
        self.declare_parameter('default_motion_profile', 'demo_slow')
        self.declare_parameter('log_dir', '~/.ros/flexcell')
        self.declare_parameter('log_file', 'place.jsonl')

        gp = self.get_parameter
        self._m2p = MoveToPoseClient(self, gp('move_to_pose_action').value)
        self._gripper = GripperClient(self, gp('gripper_action').value)
        self._scene = PlanningSceneOps(self)
        self._gripper_open = float(gp('gripper_open_position').value)
        self._hover = float(gp('release_hover_m').value)
        self._clearance = float(gp('release_clearance_m').value)
        self._carry = float(gp('carry_offset_m').value)
        self._tol = float(gp('place_tolerance_m').value)
        self._settle = float(gp('settle_time_s').value)
        self._retreat = float(gp('retreat_m').value)
        self._carry_release = self.create_client(
            Trigger, gp('carry_release_service').value,
            callback_group=ReentrantCallbackGroup())
        self.create_service(Trigger, '/flexcell/place_ready', self._on_ready)
        self._size = list(gp('object_size').value)
        self._deadline = int(gp('default_deadline_ms').value)
        self._profiles = list(gp('motion_profile_names').value)
        self._default_profile = gp('default_motion_profile').value
        self._log = JsonlLog(self, gp('log_dir').value, gp('log_file').value)

        self._admission = threading.Lock()
        self._seq = 0

        self._server = ActionServer(
            self, PlaceObject, 'place_object',
            execute_callback=self._execute,
            goal_callback=lambda req: GoalResponse.ACCEPT,
            cancel_callback=lambda gh: CancelResponse.ACCEPT,
            callback_group=ReentrantCallbackGroup())

        self.get_logger().info(
            'Place server up | hover=%.2fm carry_offset=%.2fm tol=%.3fm'
            % (self._hover, self._carry, self._tol))

    def _feedback(self, gh, name, t0):
        fb = F()
        fb.phase = PHASES[name]
        fb.elapsed_ms = int((time.monotonic() - t0) * 1000)
        gh.publish_feedback(fb)

    def _motion(self, position, profile, request_id, cancel_check=None):
        res, err = self._m2p.call(position, profile=profile,
                                  deadline_ms=self._deadline, request_id=request_id,
                                  cancel_check=cancel_check)
        if err is not None:
            return None, 0, err
        return res, int(res.error_code), res.detail

    def _on_ready(self, _request, response):
        # Readiness is checked from THIS participant, using the client's graph.
        # An external node discovering the task action is not sufficient.
        response.success = self._carry_release.wait_for_service(timeout_sec=2.0)
        response.message = ('PLACE release dependency ready' if response.success
                            else 'PLACE cannot discover carry release service')
        return response

    def _execute(self, goal_handle):
        t0 = time.monotonic()
        goal = goal_handle.request
        self._seq += 1
        rid, evidence = new_evidence(goal.object_name, self._seq)
        res = R()
        rec = {
            'request_id': rid, 'evidence_id': evidence,
            'object_name': goal.object_name,
            'profile': goal.motion_profile_id or self._default_profile,
        }

        def finish(outcome, error, detail, motion_err=0):
            res.outcome = outcome
            res.status = derive_status('PLACE', outcome)
            res.error_code = error
            res.motion_error_code = motion_err
            res.detail = detail
            res.evidence_id = evidence
            rec.update(outcome=str(outcome), error_code=int(error),
                       motion_error_code=int(motion_err), detail=detail,
                       released=bool(res.released),
                       status=int(res.status),
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
        if not self._admission.acquire(blocking=False):
            return finish(R.OUTCOME_FAILED, R.ERR_RESOURCE_BUSY,
                          'another place goal is active')
        try:
            # ---------- VALIDATING ----------
            self._feedback(goal_handle, 'VALIDATING', t0)
            profile = goal.motion_profile_id or self._default_profile
            if not goal.object_name:
                return finish(R.OUTCOME_FAILED, R.ERR_INVALID_GOAL,
                              'object_name is empty')
            if profile not in self._profiles:
                return finish(R.OUTCOME_FAILED, R.ERR_INVALID_GOAL,
                              'motion_profile_id %r not in whitelist %s'
                              % (profile, self._profiles))
            frame = goal.place_pose.header.frame_id or 'world'
            if frame != 'world':
                return finish(R.OUTCOME_FAILED, R.ERR_INVALID_GOAL,
                              'place_pose frame must be world (got %r)' % frame)
            pp = goal.place_pose.pose.position

            # carried check (planning scene is the source of truth for carries)
            carried, err = self._scene.is_attached(goal.object_name)
            if not carried:
                return finish(R.OUTCOME_FAILED, R.ERR_NOT_CARRIED,
                              'object %r is not attached to the arm: %s'
                              % (goal.object_name, err or 'not in attached state'))

            place_pos = [pp.x, pp.y, pp.z]
            cancel_requested = lambda: goal_handle.is_cancel_requested  # noqa: E731

            # ---------- APPROACHING ----------
            self._feedback(goal_handle, 'APPROACHING', t0)
            # the carried box hangs carry_offset below the EE; place the box
            # (not the EE) at place_pos + release_clearance
            box_target_z = place_pos[2] + self._clearance
            ee_z = box_target_z + self._carry
            hover = [pp.x, pp.y, ee_z + self._hover]
            mres, merr_code, detail = self._motion(hover, profile, rid + '-hover',
                                                   cancel_check=cancel_requested)
            if mres is None or int(mres.outcome) != R.OUTCOME_SUCCEEDED:
                if goal_handle.is_cancel_requested:
                    return finish(R.OUTCOME_CANCELED, R.ERR_CANCELED,
                                  'canceled during hover (motion stopped; box '
                                  'still carried)')
                return finish(R.OUTCOME_FAILED, R.ERR_MOTION_FAILED,
                              'hover motion failed: %s' % detail,
                              motion_err=merr_code)
            descend = [pp.x, pp.y, ee_z]
            mres, merr_code, detail = self._motion(descend, profile, rid + '-descend',
                                                   cancel_check=cancel_requested)
            if mres is None or int(mres.outcome) != R.OUTCOME_SUCCEEDED:
                if goal_handle.is_cancel_requested:
                    return finish(R.OUTCOME_CANCELED, R.ERR_CANCELED,
                                  'canceled during descend (motion stopped; box '
                                  'still carried)')
                return finish(R.OUTCOME_FAILED, R.ERR_MOTION_FAILED,
                              'descend motion failed: %s' % detail,
                              motion_err=merr_code)

            # ---------- RELEASING ----------
            if goal_handle.is_cancel_requested:
                return finish(R.OUTCOME_CANCELED, R.ERR_CANCELED,
                              'canceled before RELEASING (box still carried)')
            self._feedback(goal_handle, 'RELEASING', t0)
            # release: stop the carry servo first, then free the planning scene
            if not self._carry_release.wait_for_service(timeout_sec=5.0):
                return finish(R.OUTCOME_FAILED, R.ERR_PLACE_FAILED,
                              'carry release service unavailable; object remains attached')
            release_future = self._carry_release.call_async(Trigger.Request())
            if wait_future(release_future, 5.0) != 'done':
                return finish(R.OUTCOME_FAILED, R.ERR_PLACE_FAILED,
                              'carry release acknowledgement timed out')
            release = release_future.result()
            if not release.success:
                return finish(R.OUTCOME_FAILED, R.ERR_PLACE_FAILED,
                              'carry release failed: %s' % release.message)
            rec['carry_release_confirmed'] = True
            sok, serr = self._scene.detach_to_world(
                goal.object_name, place_pos, self._size)
            if not sok:
                return finish(R.OUTCOME_FAILED, R.ERR_PLACE_FAILED,
                              'planning-scene detach failed: %s' % serr)
            gres, gerr = self._gripper.command(self._gripper_open)
            if gerr is not None:
                return finish(R.OUTCOME_FAILED, R.ERR_PLACE_FAILED,
                              'gripper open failed: %s' % gerr)
            res.released = True

            # ---------- VERIFYING (internal, ground truth) ----------
            self._feedback(goal_handle, 'VERIFYING', t0)
            if interruptible_sleep(self._settle, cancel_requested):
                return finish(R.OUTCOME_CANCELED, R.ERR_CANCELED,
                              'canceled during settle (object already released)')
            sampled, err = sample_gz_pose(goal.object_name)
            if sampled is None:
                return finish(R.OUTCOME_FAILED, R.ERR_PLACE_FAILED,
                              'post-drop observe failed: %s' % err)
            box_after, box_quat = sampled
            res.object_pose_after = pose_msg(box_after, box_quat)
            rec['box_after'] = box_after
            drop_err = dist3(box_after, place_pos)
            rec['place_error_m'] = drop_err

            # ---------- RETREATING ----------
            self._feedback(goal_handle, 'RETREATING', t0)
            up = [descend[0], descend[1], descend[2] + self._retreat]
            mres, merr_code, detail = self._motion(up, profile, rid + '-retreat',
                                                   cancel_check=cancel_requested)
            if mres is None or int(mres.outcome) != R.OUTCOME_SUCCEEDED:
                if goal_handle.is_cancel_requested:
                    return finish(R.OUTCOME_CANCELED, R.ERR_CANCELED,
                                  'canceled during retreat (object already '
                                  'placed at %.3fm error)' % drop_err)
                # object is already placed; report the retreat failure honestly
                return finish(R.OUTCOME_FAILED, R.ERR_MOTION_FAILED,
                              'object dropped (place_err=%.3f) but retreat failed: %s'
                              % (drop_err, detail), motion_err=merr_code)

            if drop_err > self._tol:
                return finish(R.OUTCOME_FAILED, R.ERR_PLACE_FAILED,
                              'box settled %.3fm from place pose (tol %.3f)'
                              % (drop_err, self._tol))
            return finish(R.OUTCOME_SUCCEEDED, R.ERR_NONE,
                          'placed %s: drop error %.3fm' % (goal.object_name, drop_err))

        except Exception as exc:  # crash guard (issue #20): a raising execute
            # callback must become a typed FAILURE - rclpy's fallback default
            # Result has outcome=0, which reads as OUTCOME_SUCCEEDED
            return finish(R.OUTCOME_FAILED, R.ERR_INTERNAL, crash_detail(exc))
        finally:
            self._admission.release()



def main(args=None):
    rclpy.init(args=args)
    node = PlaceServer()
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
