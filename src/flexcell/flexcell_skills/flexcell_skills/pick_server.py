#!/usr/bin/env python3
"""FlexCell Pick skill server (Week 1).

observe -> approach (hover, descend) -> close gripper + attach -> lift, with
measured checks at every step. Composition over Day-2 MoveToPose: this server
never plans motions itself.

Grasp mode (declared, not silent): the gz DetachableJoint system on link5
provides a deterministic magnetic anchor - on attach the box is jointed to the
gripper with the relative pose it had at that moment. Contact-pinch grasping
is future hardening. Success is still measured: the box must physically rise
with the arm, otherwise GRASP_FAILED.
"""

import time

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from geometry_msgs.msg import PoseStamped, Vector3
from std_msgs.msg import Empty as EmptyMsg
from std_msgs.msg import String as StringMsg
import json
from tf2_ros import Buffer, TransformListener
from rclpy.duration import Duration
from rclpy.time import Time

from flexcell_interfaces.action import PickObject

from flexcell_skills.common import (
    GripperClient, JsonlLog, MoveToPoseClient, PlanningSceneOps,
    dist3, new_evidence, pose_msg, sample_gz_pose)

R = PickObject.Result
F = PickObject.Feedback

PHASES = {
    'VALIDATING': F.PHASE_VALIDATING,
    'OBSERVING': F.PHASE_OBSERVING,
    'APPROACHING': F.PHASE_APPROACHING,
    'GRASPING': F.PHASE_GRASPING,
    'LIFTING': F.PHASE_LIFTING,
}


class PickServer(Node):

    def __init__(self):
        super().__init__('pick_server')

        self.declare_parameter('move_to_pose_action', '/move_to_pose')
        self.declare_parameter('gripper_action', '/gripper_controller/gripper_cmd')
        self.declare_parameter('gripper_open_position', 0.02)
        self.declare_parameter('gripper_close_position', -0.011)
        self.declare_parameter('approach_hover_m', 0.22)
        self.declare_parameter('grasp_dz_m', 0.16)
        self.declare_parameter('grasp_raise_m', 0.10)
        self.declare_parameter('attach_radius_m', 0.20)
        self.declare_parameter('carry_start_topic', '/flexcell/carry_start')
        self.declare_parameter('carry_stop_topic', '/flexcell/carry_stop')
        self.declare_parameter('inject_topic', '/flexcell/inject')
        self.declare_parameter('box_follow_min_m', 0.03)
        self.declare_parameter('object_size', [0.035, 0.035, 0.035])
        self.declare_parameter('base_frame', 'world')
        self.declare_parameter('end_effector_link', 'end_effector_link')
        self.declare_parameter('default_deadline_ms', 30000)
        self.declare_parameter('motion_profile_names', ['demo_veryslow', 'demo_slow', 'demo_default'])
        self.declare_parameter('default_motion_profile', 'demo_slow')
        self.declare_parameter('log_dir', '~/.ros/flexcell')
        self.declare_parameter('log_file', 'pick.jsonl')

        gp = self.get_parameter
        self._m2p = MoveToPoseClient(self, gp('move_to_pose_action').value)
        self._gripper = GripperClient(self, gp('gripper_action').value)
        self._scene = PlanningSceneOps(self)
        self._gripper_open = float(gp('gripper_open_position').value)
        self._gripper_close = float(gp('gripper_close_position').value)
        self._hover = float(gp('approach_hover_m').value)
        self._grasp_dz = float(gp('grasp_dz_m').value)
        self._raise = float(gp('grasp_raise_m').value)
        self._attach_radius = float(gp('attach_radius_m').value)
        self._carry_start = self.create_publisher(
            StringMsg, gp('carry_start_topic').value, 10)
        self._carry_stop = self.create_publisher(
            EmptyMsg, gp('carry_stop_topic').value, 10)

        # ---- deterministic failure injection (Week-1.5) ----
        # payload "<scenario_id>:<once|always>" or "" to disable; attempts are
        # counted per (scenario, object) so a retry (attempt 2) passes "once".
        self._inject_scenario = ''
        self._inject_mode = ''
        self._inject_counts = {}
        self.create_subscription(
            StringMsg, gp('inject_topic').value, self._on_inject, 10)
        self._follow_min = float(gp('box_follow_min_m').value)
        self._size = list(gp('object_size').value)
        self._base = gp('base_frame').value
        self._ee = gp('end_effector_link').value
        self._deadline = int(gp('default_deadline_ms').value)
        self._profiles = list(gp('motion_profile_names').value)
        self._default_profile = gp('default_motion_profile').value
        self._log = JsonlLog(self, gp('log_dir').value, gp('log_file').value)

        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self, spin_thread=False)

        self._busy = False
        self._seq = 0

        self._server = ActionServer(
            self, PickObject, 'pick_object',
            execute_callback=self._execute,
            goal_callback=lambda req: GoalResponse.ACCEPT,
            cancel_callback=lambda gh: CancelResponse.ACCEPT,
            callback_group=ReentrantCallbackGroup())

        self.get_logger().info(
            'Pick server up | hover=%.2fm grasp_dz=%.2fm raise=%.2fm attach_r=%.2fm'
            % (self._hover, self._grasp_dz, self._raise, self._attach_radius))

    # ------------------------------------------------------------- utilities
    def _ee_position(self):
        try:
            tr = self._tf_buffer.lookup_transform(
                self._base, self._ee, Time(), Duration(seconds=1.0))
            t = tr.transform.translation
            return [t.x, t.y, t.z], None
        except Exception as exc:  # noqa: BLE001
            return None, str(exc)

    def _feedback(self, gh, name, t0):
        fb = F()
        fb.phase = PHASES[name]
        fb.elapsed_ms = int((time.monotonic() - t0) * 1000)
        gh.publish_feedback(fb)

    def _motion(self, position, profile, request_id):
        res, err = self._m2p.call(position, profile=profile,
                                  deadline_ms=self._deadline, request_id=request_id)
        if err is not None:
            return None, 0, err
        return res, int(res.error_code), res.detail

    def _on_inject(self, msg):
        payload = (msg.data or '').strip()
        if not payload:
            self._inject_scenario = ''
            self._inject_mode = ''
            self._inject_counts = {}
            self.get_logger().info('failure injection DISABLED')
            return
        if ':' in payload:
            scenario, mode = payload.split(':', 1)
        else:
            scenario, mode = payload, 'once'
        if mode not in ('once', 'always'):
            self.get_logger().error('bad inject mode %r (payload=%r)' % (mode, payload))
            return
        self._inject_scenario = scenario
        self._inject_mode = mode
        self._inject_counts = {}
        self.get_logger().info(
            'failure injection ARMED scenario=%s mode=%s' % (scenario, mode))

    def _injection_check(self, object_name):
        """Return a detail string when this attempt must fail deterministically."""
        if not self._inject_scenario:
            return None
        key = '%s|%s' % (self._inject_scenario, object_name)
        attempt = self._inject_counts.get(key, 0) + 1
        self._inject_counts[key] = attempt
        if self._inject_mode == 'once' and attempt > 1:
            return None
        return ('injected failure (scenario=%s mode=%s attempt=%d)'
                % (self._inject_scenario, self._inject_mode, attempt))

    def _release_everything(self, name):
        self._carry_stop.publish(EmptyMsg())
        self._gripper.command(self._gripper_open)
        self._scene.remove(name)

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
            res.error_code = error
            res.motion_error_code = motion_err
            res.detail = detail
            res.evidence_id = evidence
            rec.update(outcome=str(outcome), error_code=int(error),
                       motion_error_code=int(motion_err), detail=detail,
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
                          'another pick goal is active')
        self._busy = True
        attached = False
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

            # deterministic failure injection happens BEFORE any motion, so a
            # recoverable injected failure leaves the world untouched
            inj = self._injection_check(goal.object_name)
            if inj is not None:
                rec['injected'] = True
                return finish(R.OUTCOME_FAILED, R.ERR_GRASP_FAILED, inj)

            # ---------- OBSERVING ----------
            self._feedback(goal_handle, 'OBSERVING', t0)
            sampled, err = sample_gz_pose(goal.object_name)
            if sampled is None:
                code = (R.ERR_WORLD_STATE_UNAVAILABLE
                        if 'not flowing' in err else R.ERR_OBJECT_UNKNOWN)
                return finish(R.OUTCOME_FAILED, code,
                              'observe failed: %s' % err)
            box_pos, box_quat = sampled
            res.object_pose_before = pose_msg(box_pos, box_quat)
            rec['box_before'] = box_pos

            # pre-open the gripper so fingers never close on air by accident
            gres, gerr = self._gripper.command(self._gripper_open)
            if gerr is not None:
                return finish(R.OUTCOME_FAILED, R.ERR_MOTION_FAILED,
                              'gripper open failed: %s' % gerr)

            # ---------- APPROACHING ----------
            self._feedback(goal_handle, 'APPROACHING', t0)
            # make the box known to MoveIt so the approach plans AROUND it
            # instead of knocking it (measured 2026-09-26: a blind approach
            # swept the box aside and landed 4.7cm short of the hover target)
            scene_added, serr = self._scene.add_box(
                goal.object_name, box_pos, self._size)
            rec['scene_box_added'] = bool(scene_added)

            def try_approach():
                hover = [box_pos[0], box_pos[1], box_pos[2] + self._hover]
                r1 = self._motion(hover, profile, rid + '-hover')
                if r1[0] is None or int(r1[0].outcome) != R.OUTCOME_SUCCEEDED:
                    return r1
                grasp_t = [box_pos[0], box_pos[1], box_pos[2] + self._grasp_dz]
                return self._motion(grasp_t, profile, rid + '-grasp')

            mres, merr_code, detail = try_approach()
            if (mres is None or int(mres.outcome) != R.OUTCOME_SUCCEEDED) and scene_added:
                # fallback: drop scene awareness and retry once (knock risk
                # accepted, reported in detail)
                self._scene.remove(goal.object_name)
                scene_added = False
                rec['scene_box_fallback'] = True
                mres, merr_code, detail = try_approach()
            if mres is None or int(mres.outcome) != R.OUTCOME_SUCCEEDED:
                return finish(R.OUTCOME_FAILED, R.ERR_MOTION_FAILED,
                              'approach failed: %s' % detail,
                              motion_err=merr_code)
            grasp = [box_pos[0], box_pos[1], box_pos[2] + self._grasp_dz]

            # ---------- GRASPING ----------
            self._feedback(goal_handle, 'GRASPING', t0)
            ee_pos, err = self._ee_position()
            if ee_pos is None:
                return finish(R.OUTCOME_FAILED, R.ERR_MOTION_FAILED,
                              'EE pose unavailable: %s' % err)
            gap = dist3(ee_pos, box_pos)
            rec['attach_gap_m'] = gap
            if gap > self._attach_radius:
                return finish(R.OUTCOME_FAILED, R.ERR_GRASP_FAILED,
                              'EE not at object: gap=%.3fm > radius=%.3fm '
                              '(refusing to fake a grasp)' % (gap, self._attach_radius))

            gres, gerr = self._gripper.command(self._gripper_close)
            if gerr is not None:
                return finish(R.OUTCOME_FAILED, R.ERR_MOTION_FAILED,
                              'gripper close failed: %s' % gerr)

            # engage the carry servo at the MEASURED gripper-to-object offset
            offset = [box_pos[i] - ee_pos[i] for i in range(3)]
            self._carry_start.publish(StringMsg(data=json.dumps({
                'object': goal.object_name,
                'offset': offset,
                'frame': self._base,
            })))
            rec['carry_offset'] = offset
            time.sleep(0.5)   # let the servo pin the object before lifting

            sok, serr = self._scene.attach(goal.object_name)
            if not sok:
                self._carry_stop.publish(EmptyMsg())
                return finish(R.OUTCOME_FAILED, R.ERR_GRASP_FAILED,
                              'planning-scene attach failed: %s' % serr)
            attached = True
            time.sleep(0.5)

            # ---------- LIFTING ----------
            self._feedback(goal_handle, 'LIFTING', t0)
            lift = [grasp[0], grasp[1], grasp[2] + self._raise]
            mres, merr_code, detail = self._motion(lift, profile, rid + '-lift')
            if mres is None or int(mres.outcome) != R.OUTCOME_SUCCEEDED:
                return finish(R.OUTCOME_FAILED, R.ERR_MOTION_FAILED,
                              'lift motion failed: %s' % detail,
                              motion_err=merr_code)

            sampled, err = sample_gz_pose(goal.object_name)
            if sampled is None:
                return finish(R.OUTCOME_FAILED, R.ERR_GRASP_FAILED,
                              'post-lift observe failed: %s' % err)
            box_after, box_quat = sampled
            res.object_pose_after = pose_msg(box_after, box_quat)
            rec['box_after'] = box_after
            rise = box_after[2] - box_pos[2]
            rec['box_rise_m'] = rise
            if rise < self._follow_min:
                # measured dishonesty guard: the box did not come along
                self._release_everything(goal.object_name)
                attached = False
                return finish(R.OUTCOME_FAILED, R.ERR_GRASP_FAILED,
                              'box did not follow the lift (rise=%.3fm < %.3fm); '
                              'released for safety' % (rise, self._follow_min))

            res.grasp_attached = True
            return finish(R.OUTCOME_SUCCEEDED, R.ERR_NONE,
                          'picked %s: attached, measured rise %.3fm'
                          % (goal.object_name, rise))

        finally:
            self._busy = False


def main(args=None):
    rclpy.init(args=args)
    node = PickServer()
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
