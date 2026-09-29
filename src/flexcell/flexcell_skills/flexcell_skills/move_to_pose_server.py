#!/usr/bin/env python3
"""FlexCell MoveToPose action server.

Typed boundary between a caller (Human / FSM / future Runtime Agent) and the
deterministic robot software:

    typed request -> MoveToPose Action -> MoveIt -> Gazebo
                  -> actual state check -> typed result

Everything here must work correctly without an LLM.

Responsibilities (deliberately thin):
  validation | admission | single-arm mutual exclusion | cancellation
  MoveIt request lifecycle | result normalization | structured logging

Explicitly NOT here: Runtime Agent, Jev, benchmarks, pick/place, full WorldState.
"""

import json
import math
import os
import threading
import time
import uuid

import rclpy
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.duration import Duration
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.time import Time

from control_msgs.action import FollowJointTrajectory
from geometry_msgs.msg import Pose, PoseStamped, Vector3
from moveit_msgs.action import ExecuteTrajectory
from moveit_msgs.msg import (
    BoundingVolume,
    Constraints,
    MotionPlanRequest,
    MoveItErrorCodes,
    OrientationConstraint,
    PositionConstraint,
    PositionIKRequest,
    WorkspaceParameters,
)
from moveit_msgs.srv import GetMotionPlan, GetPositionIK
from sensor_msgs.msg import JointState
from shape_msgs.msg import SolidPrimitive
from tf2_ros import Buffer, TransformListener

from flexcell_interfaces.action import MoveToPose
from flexcell_skills.common import crash_detail
from flexcell_skills.contracts.trajectory import trajectory_summary

R = MoveToPose.Result
F = MoveToPose.Feedback

PHASE_NAMES = {
    F.PHASE_VALIDATING: 'VALIDATING',
    F.PHASE_PLANNING: 'PLANNING',
    F.PHASE_EXECUTING: 'EXECUTING',
    F.PHASE_CHECKING: 'CHECKING',
    F.PHASE_STOPPING: 'STOPPING',
}

ARM_JOINTS = ['joint1', 'joint2', 'joint3', 'joint4']


# ---------------------------------------------------------------- quaternion
def q_norm(q):
    return math.sqrt(q.x * q.x + q.y * q.y + q.z * q.z + q.w * q.w)


def q_mul(a, b):
    return (
        a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y,
        a.w * b.y - a.x * b.z + a.y * b.w + a.z * b.x,
        a.w * b.z + a.x * b.y - a.y * b.x + a.z * b.w,
        a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z,
    )


def q_rotate(q, v):
    x, y, z, w = q.x, q.y, q.z, q.w
    vx, vy, vz = v
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return (
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    )


def q_angle_between(a, b):
    d = a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w
    d = max(-1.0, min(1.0, abs(d)))
    return 2.0 * math.acos(d)


class MoveToPoseServer(Node):

    def __init__(self):
        super().__init__('move_to_pose_server')

        # ---------------- parameters ----------------
        self.declare_parameter('planning_group', 'arm')
        self.declare_parameter('end_effector_link', 'end_effector_link')
        self.declare_parameter('base_frame', 'world')
        self.declare_parameter('planning_service', '/plan_kinematic_path')
        self.declare_parameter('ik_service', '/compute_ik')
        self.declare_parameter('ik_timeout_s', 1.0)
        self.declare_parameter('execute_action', '/execute_trajectory')
        # Verified stop path: the ros2_control controller action honours cancel
        # (measured stop latency ~50 ms). MoveIt 2.12.4's /execute_trajectory does
        # not - see docs/DAY2_MOVETOPOSE.md.
        self.declare_parameter('execution_backend', 'controller_action')
        self.declare_parameter('controller_action',
                               '/arm_controller/follow_joint_trajectory')
        self.declare_parameter('joint_states_topic', '/joint_states')

        self.declare_parameter('default_deadline_ms', 20000)
        self.declare_parameter('max_deadline_ms', 60000)
        self.declare_parameter('planning_timeout_s', 5.0)
        self.declare_parameter('execution_timeout_s', 25.0)
        self.declare_parameter('tf_timeout_s', 1.0)
        self.declare_parameter('stop_confirm_timeout_s', 4.0)
        self.declare_parameter('stop_result_timeout_s', 12.0)
        self.declare_parameter('cut_short_threshold_rad', 0.02)
        self.declare_parameter('stop_velocity_epsilon', 0.02)
        self.declare_parameter('joint_state_max_age_s', 1.0)

        self.declare_parameter('position_tolerance_m', 0.02)
        self.declare_parameter('orientation_tolerance_rad', 0.35)
        self.declare_parameter('enforce_orientation', False)
        # IK search sphere. Deliberately tighter than the success tolerance so the
        # achieved pose lands comfortably inside it instead of on the boundary.
        self.declare_parameter('planning_constraint_radius_m', 0.008)

        self.declare_parameter('workspace_min', [-0.45, -0.45, -0.15])
        self.declare_parameter('workspace_max', [0.45, 0.45, 0.75])

        self.declare_parameter('motion_profile_names', ['demo_slow', 'demo_default'])
        self.declare_parameter('default_motion_profile', 'demo_slow')

        self.declare_parameter('log_dir', '~/.ros/flexcell')
        self.declare_parameter('log_file', 'move_to_pose.jsonl')

        # Day 2 fixed-scene mode: the WorldState revision gate is NOT enabled.
        self.declare_parameter('world_revision_gate_enabled', False)

        gp = self.get_parameter
        self._group = gp('planning_group').value
        self._ee_link = gp('end_effector_link').value
        self._base = gp('base_frame').value
        self._plan_srv = gp('planning_service').value
        self._ik_srv = gp('ik_service').value
        self._ik_timeout = float(gp('ik_timeout_s').value)
        self._exec_act = gp('execute_action').value
        self._backend = gp('execution_backend').value
        self._fjt_action = gp('controller_action').value
        self._js_topic = gp('joint_states_topic').value

        self._default_deadline_ms = int(gp('default_deadline_ms').value)
        self._max_deadline_ms = int(gp('max_deadline_ms').value)
        self._plan_timeout = float(gp('planning_timeout_s').value)
        self._exec_timeout = float(gp('execution_timeout_s').value)
        self._tf_timeout = float(gp('tf_timeout_s').value)
        self._stop_timeout = float(gp('stop_confirm_timeout_s').value)
        self._stop_result_timeout = float(gp('stop_result_timeout_s').value)
        self._cut_short_rad = float(gp('cut_short_threshold_rad').value)
        self._stop_eps = float(gp('stop_velocity_epsilon').value)
        self._js_max_age = float(gp('joint_state_max_age_s').value)

        self._pos_tol = float(gp('position_tolerance_m').value)
        self._ori_tol = float(gp('orientation_tolerance_rad').value)
        self._enforce_ori = bool(gp('enforce_orientation').value)
        self._constraint_radius = float(gp('planning_constraint_radius_m').value)

        self._ws_min = list(gp('workspace_min').value)
        self._ws_max = list(gp('workspace_max').value)

        self._profile_names = list(gp('motion_profile_names').value)
        self._default_profile = gp('default_motion_profile').value
        self._profiles = {}
        for name in self._profile_names:
            self.declare_parameter('motion_profile_' + name + '_max_velocity', 0.2)
            self.declare_parameter('motion_profile_' + name + '_max_acceleration', 0.2)
            self._profiles[name] = (
                float(gp('motion_profile_' + name + '_max_velocity').value),
                float(gp('motion_profile_' + name + '_max_acceleration').value),
            )

        log_dir = os.path.expanduser(gp('log_dir').value)
        os.makedirs(log_dir, exist_ok=True)
        self._log_path = os.path.join(log_dir, gp('log_file').value)

        self._world_gate = bool(gp('world_revision_gate_enabled').value)

        # ---------------- state ----------------
        self._js = None
        self._js_wall = 0.0
        self._admission = threading.Lock()
        self._motion_blocked = False
        self._motion_blocked_reason = ''
        self._seq = 0
        self._current_phases = []

        # ---------------- ROS interfaces ----------------
        self._cbg = ReentrantCallbackGroup()

        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self, spin_thread=False)

        self.create_subscription(
            JointState, self._js_topic, self._on_js, 50, callback_group=self._cbg)

        self._plan_client = self.create_client(
            GetMotionPlan, self._plan_srv, callback_group=self._cbg)
        self._ik_client = self.create_client(
            GetPositionIK, self._ik_srv, callback_group=self._cbg)
        self._exec_client = ActionClient(
            self, ExecuteTrajectory, self._exec_act, callback_group=self._cbg)
        self._fjt_client = ActionClient(
            self, FollowJointTrajectory, self._fjt_action, callback_group=self._cbg)

        self._server = ActionServer(
            self,
            MoveToPose,
            'move_to_pose',
            execute_callback=self._execute,
            goal_callback=self._on_goal,
            cancel_callback=self._on_cancel,
            handle_accepted_callback=self._on_accepted,
            callback_group=self._cbg,
        )

        self.get_logger().info(
            'MoveToPose server up | group=%s ee=%s base=%s | pos_tol=%.3fm ori_enforced=%s'
            % (self._group, self._ee_link, self._base, self._pos_tol, self._enforce_ori))
        if not self._enforce_ori:
            self.get_logger().warn(
                'orientation NOT enforced: the active kinematics solver is position-only. '
                'This is reported explicitly in every result (orientation_enforced=false).')
        self.get_logger().info('structured log: %s' % self._log_path)

    # ------------------------------------------------------------- callbacks
    def _on_js(self, msg):
        self._js = msg
        self._js_wall = time.monotonic()

    def _on_goal(self, goal_request):
        return GoalResponse.ACCEPT

    def _on_cancel(self, goal_handle):
        return CancelResponse.ACCEPT

    def _on_accepted(self, goal_handle):
        goal_handle.execute()

    # ------------------------------------------------------------- utilities
    def _new_evidence(self, goal):
        self._seq += 1
        rid = goal.request_id or ('auto-%d-%s' % (self._seq, uuid.uuid4().hex[:8]))
        return rid, '%s-%s' % (rid, uuid.uuid4().hex[:8])

    def _log(self, rec):
        rec['wall_ts'] = time.time()
        rec.setdefault('feedback_phases', list(self._current_phases))
        rec.setdefault('moveit_error_code',
                       rec.get('execution_error_code',
                               rec.get('moveit_planning_error_code', 0)))
        js = self._js
        if js is not None:
            rec.setdefault('final_joint_state', {
                'name': list(js.name),
                'position': list(js.position),
                'velocity': list(js.velocity),
                'age_s': time.monotonic() - self._js_wall,
            })
        try:
            with open(self._log_path, 'a') as fh:
                fh.write(json.dumps(rec, default=str) + '\n')
        except OSError as exc:  # never let logging kill a motion request
            self.get_logger().error('log write failed: %s' % exc)

    def _feedback(self, goal_handle, phase, t_start):
        fb = F()
        fb.phase = phase
        fb.elapsed_ms = int((time.monotonic() - t_start) * 1000)
        goal_handle.publish_feedback(fb)
        name = PHASE_NAMES.get(phase, str(phase))
        if not self._current_phases or self._current_phases[-1] != name:
            self._current_phases.append(name)

    def _result(self, outcome, error_code, moveit_code=0, detail=''):
        r = R()
        r.outcome = outcome
        r.error_code = error_code
        r.moveit_error_code = int(moveit_code)
        r.has_reached_pose = False
        r.position_error_m = float('nan')
        r.orientation_error_rad = float('nan')
        r.orientation_enforced = self._enforce_ori
        r.world_revision_before = 0
        r.world_revision_after = 0
        r.execution_started = False
        r.controller_error_code = 0
        r.preempted = False
        r.stop_confirmed = False
        r.evidence_id = ''
        r.detail = detail
        return r

    def _wait(self, future, goal_handle, deadline_t):
        while not future.done():
            if goal_handle is not None and goal_handle.is_cancel_requested:
                return 'cancel'
            if time.monotonic() > deadline_t:
                return 'timeout'
            time.sleep(0.02)
        return 'done'

    def _joint_state(self):
        if self._js is None:
            return None, None
        age = time.monotonic() - self._js_wall
        return self._js, age

    def _arm_at_rest(self):
        js, age = self._joint_state()
        if js is None or age is None or age > self._js_max_age:
            return False, 'joint state unavailable or stale'
        idx = {n: i for i, n in enumerate(js.name)}
        for j in ARM_JOINTS:
            if j not in idx:
                return False, 'joint %s missing from /joint_states' % j
            if abs(js.velocity[idx[j]]) > self._stop_eps:
                return False, 'joint %s still moving (v=%.4f)' % (j, js.velocity[idx[j]])
        return True, 'at rest'

    def _reconfirm_state(self):
        ok, why = self._arm_at_rest()
        if ok:
            return True
        self.get_logger().warn('state reconfirm failed: %s' % why)
        return False

    def _transform_to_base(self, ps):
        """Transform a PoseStamped into the planning base frame (manual, no extra deps)."""
        src = ps.header.frame_id
        if src == self._base:
            return ps, None
        try:
            tr = self._tf_buffer.lookup_transform(
                self._base, src, Time(), Duration(seconds=self._tf_timeout))
        except Exception as exc:  # noqa: BLE001
            return None, 'TF %s -> %s failed: %s' % (self._base, src, exc)
        t = tr.transform.translation
        q = tr.transform.rotation
        p = ps.pose.position
        rx, ry, rz = q_rotate(q, (p.x, p.y, p.z))
        out = PoseStamped()
        out.header.frame_id = self._base
        out.header.stamp = ps.header.stamp
        out.pose.position.x = rx + t.x
        out.pose.position.y = ry + t.y
        out.pose.position.z = rz + t.z
        qx, qy, qz, qw = q_mul(q, ps.pose.orientation)
        out.pose.orientation.x = qx
        out.pose.orientation.y = qy
        out.pose.orientation.z = qz
        out.pose.orientation.w = qw
        return out, None

    def _ee_pose_now(self):
        try:
            tr = self._tf_buffer.lookup_transform(
                self._base, self._ee_link, Time(), Duration(seconds=self._tf_timeout))
        except Exception as exc:  # noqa: BLE001
            return None, 'TF %s -> %s failed: %s' % (self._base, self._ee_link, exc)
        ps = PoseStamped()
        ps.header.frame_id = self._base
        ps.header.stamp = self.get_clock().now().to_msg()
        ps.pose.position.x = tr.transform.translation.x
        ps.pose.position.y = tr.transform.translation.y
        ps.pose.position.z = tr.transform.translation.z
        ps.pose.orientation = tr.transform.rotation
        return ps, None

    # ------------------------------------------------------------- execution
    def _execute(self, goal_handle):
        t_start = time.monotonic()
        goal = goal_handle.request
        rid, evidence = self._new_evidence(goal)
        self._current_phases = []
        rec = {
            'request_id': rid,
            'evidence_id': evidence,
            'action_goal_id': bytes(goal_handle.goal_id.uuid).hex(),
            'request_timestamp': time.time(),
            'target': {
                'frame_id': goal.target.header.frame_id,
                'position': [goal.target.pose.position.x,
                             goal.target.pose.position.y,
                             goal.target.pose.position.z],
                'orientation': [goal.target.pose.orientation.x,
                                goal.target.pose.orientation.y,
                                goal.target.pose.orientation.z,
                                goal.target.pose.orientation.w],
            },
            'motion_profile': goal.motion_profile_id,
            'expected_world_revision': int(goal.expected_world_revision),
            'deadline_ms': int(goal.deadline_ms),
        }

        # ---------- admission: single-arm mutual exclusion ----------
        # atomic lock (audit P1-3): the old check-then-set flag was a TOCTOU
        # race under the multithreaded executor
        if not self._admission.acquire(blocking=False):
            res = self._result(R.OUTCOME_FAILED, R.ERR_RESOURCE_BUSY,
                               detail='another MoveToPose goal is active')
            res.evidence_id = evidence
            rec.update(outcome='RESOURCE_BUSY', error_code=R.ERR_RESOURCE_BUSY)
            self._log(rec)
            goal_handle.abort()
            return res
        execution_started = False
        try:
            # ================= VALIDATING =================
            self._feedback(goal_handle, F.PHASE_VALIDATING, t_start)

            if self._motion_blocked:
                if self._reconfirm_state():
                    self._motion_blocked = False
                    self._motion_blocked_reason = ''
                    self.get_logger().info('state reconfirmed, motion unblocked')
                else:
                    res = self._result(
                        R.OUTCOME_STATE_UNKNOWN, R.ERR_STATE_UNKNOWN,
                        detail='motion blocked: %s' % self._motion_blocked_reason)
                    res.evidence_id = evidence
                    rec.update(outcome='STATE_UNKNOWN_BLOCKED',
                               error_code=R.ERR_STATE_UNKNOWN)
                    self._log(rec)
                    goal_handle.abort()
                    return res

            err, detail, profile = self._validate(goal)
            rec['validation'] = {'ok': err is None, 'error': err, 'detail': detail}
            if err is not None:
                res = self._result(R.OUTCOME_FAILED, err, detail=detail)
                res.evidence_id = evidence
                rec.update(outcome='FAILED', error_code=err)
                self._log(rec)
                goal_handle.abort()
                return res

            vel, acc = profile
            deadline_ms = self._clamp_deadline(goal.deadline_ms)
            deadline_t = t_start + deadline_ms / 1000.0
            rec['effective_deadline_ms'] = deadline_ms
            rec['profile_scaling'] = {'velocity': vel, 'acceleration': acc}

            target_base, terr = self._transform_to_base(goal.target)
            if target_base is None:
                res = self._result(R.OUTCOME_FAILED, R.ERR_FRAME_UNAVAILABLE, detail=terr)
                res.evidence_id = evidence
                rec.update(outcome='FAILED', error_code=R.ERR_FRAME_UNAVAILABLE)
                self._log(rec)
                goal_handle.abort()
                return res

            # ================= PLANNING =================
            self._feedback(goal_handle, F.PHASE_PLANNING, t_start)
            rec['planning_start'] = time.time()
            plan_t0 = time.monotonic()

            ik_ok, ik_detail = self._ik_feasible(target_base)
            rec['ik_precheck'] = {'ok': ik_ok, 'detail': ik_detail}
            if not ik_ok:
                res = self._result(R.OUTCOME_FAILED, R.ERR_IK_UNREACHABLE,
                                   detail='IK pre-check failed: %s' % ik_detail)
                res.evidence_id = evidence
                rec.update(outcome='FAILED', error_code=R.ERR_IK_UNREACHABLE,
                           planning_latency_ms=int((time.monotonic() - plan_t0) * 1000))
                self._log(rec)
                goal_handle.abort()
                return res

            if not self._plan_client.wait_for_service(timeout_sec=2.0):
                res = self._result(R.OUTCOME_FAILED, R.ERR_STATE_UNAVAILABLE,
                                   detail='planning service %s unavailable' % self._plan_srv)
                res.evidence_id = evidence
                rec.update(outcome='FAILED', error_code=R.ERR_STATE_UNAVAILABLE)
                self._log(rec)
                goal_handle.abort()
                return res

            allowed = min(self._plan_timeout, max(0.5, deadline_t - time.monotonic()))
            srv_req = GetMotionPlan.Request()
            srv_req.motion_plan_request = self._build_request(target_base, vel, acc, allowed)
            fut = self._plan_client.call_async(srv_req)
            # Wait strictly longer than MoveIt's own allowed time so MoveIt's error
            # code wins the race instead of our client-side timeout.
            st = self._wait(fut, goal_handle,
                            min(deadline_t, time.monotonic() + allowed + 2.0))
            rec['planning_latency_ms'] = int((time.monotonic() - plan_t0) * 1000)
            rec['planning_end'] = time.time()

            if st == 'cancel':
                res = self._result(R.OUTCOME_CANCELED, R.ERR_CANCELED,
                                   detail='canceled during planning; no motion commanded')
                res.evidence_id = evidence
                rec.update(outcome='CANCELED', error_code=R.ERR_CANCELED,
                           planning_latency_ms=rec['planning_latency_ms'])
                self._log(rec)
                goal_handle.canceled()
                return res
            if st == 'timeout':
                res = self._result(R.OUTCOME_FAILED, R.ERR_PLANNING_TIMEOUT,
                                   detail='planning exceeded %.1fs' % self._plan_timeout)
                res.evidence_id = evidence
                rec.update(outcome='FAILED', error_code=R.ERR_PLANNING_TIMEOUT)
                self._log(rec)
                goal_handle.abort()
                return res

            mpr = fut.result().motion_plan_response
            mcode = int(mpr.error_code.val)
            rec['moveit_planning_error_code'] = mcode
            rec['moveit_planning_message'] = mpr.error_code.message
            rec['moveit_planning_time_s'] = float(mpr.planning_time)

            if mcode != MoveItErrorCodes.SUCCESS:
                err = self._map_plan_error(mcode)
                res = self._result(R.OUTCOME_FAILED, err, mcode,
                                   detail='MoveIt planning failed: %s (%s)'
                                          % (mpr.error_code.message or 'no message',
                                             self._err_name(err)))
                res.evidence_id = evidence
                rec.update(outcome='FAILED', error_code=err, moveit_error_code=mcode)
                self._log(rec)
                goal_handle.abort()
                return res

            traj = mpr.trajectory
            traj_joint_names = list(traj.joint_trajectory.joint_names)
            # audit P0-1: summarize the trajectory WITHOUT indexing it, then
            # refuse unusable trajectories.  The old code evaluated
            # points[-1] before its own npts == 0 guard - an empty planner
            # trajectory escaped as an unhandled IndexError and rclpy's
            # fallback default Result reported outcome=0 = OUTCOME_SUCCEEDED
            # (the M2.2 Step-0 ghost class, on the one server still missing
            # the guard).
            npts, planned_final_positions, planned_dur = trajectory_summary(traj)
            rec['planning_waypoints'] = npts
            rec['planned_duration_s'] = planned_dur
            if npts == 0 or planned_final_positions is None:
                res = self._result(R.OUTCOME_FAILED, R.ERR_NO_COLLISION_FREE_PLAN, mcode,
                                   detail='planner returned an empty/unreadable trajectory')
                res.evidence_id = evidence
                rec.update(outcome='FAILED', error_code=R.ERR_NO_COLLISION_FREE_PLAN)
                self._log(rec)
                goal_handle.abort()
                return res

            # ================= EXECUTING =================
            self._feedback(goal_handle, F.PHASE_EXECUTING, t_start)
            rec['execution_backend'] = self._backend
            rec['execution_start'] = time.time()
            execution_started = True

            send_status, egh, res_fut, why = self._send_for_execution(traj, deadline_t)
            if send_status != 'sent':
                err = (R.ERR_CONTROLLER_REJECTED if send_status == 'rejected'
                       else R.ERR_STATE_UNAVAILABLE if send_status == 'unavailable'
                       else R.ERR_EXECUTION_TIMEOUT)
                res = self._result(R.OUTCOME_FAILED, err, detail=why)
                res.execution_started = execution_started
                res.evidence_id = evidence
                rec.update(outcome='FAILED', error_code=err,
                           execution_send_status=send_status)
                self._log(rec)
                goal_handle.abort()
                return res

            st = self._wait(res_fut, goal_handle,
                            min(deadline_t, time.monotonic() + self._exec_timeout))
            if st != 'done':
                return self._stop_and_finish(
                    goal_handle, rec, evidence, t_start, execution_started,
                    'cancel' if st == 'cancel' else 'timeout',
                    backend_goal_handle=egh, result_future=res_fut,
                    planned_final_positions=planned_final_positions,
                    traj_joint_names=traj_joint_names)

            ecode = self._backend_result_code(res_fut.result().result)
            rec['execution_end'] = time.time()
            rec['execution_error_code'] = ecode
            if not self._backend_code_is_success(ecode):
                # never auto-resend after a failed motion; re-acquire real state first
                rest, why2 = self._arm_at_rest()
                err = (R.ERR_EXECUTION_TIMEOUT if ecode == MoveItErrorCodes.TIMED_OUT
                       else R.ERR_EXECUTION_FAILED)
                res = self._result(R.OUTCOME_FAILED, err,
                                   detail='execution failed (code %d); arm %s' % (ecode, why2))
                if self._backend == 'controller_action':
                    res.controller_error_code = ecode
                else:
                    res.moveit_error_code = ecode
                res.execution_started = execution_started
                res.evidence_id = evidence
                rec.update(outcome='FAILED', error_code=err, arm_at_rest=rest)
                self._log(rec)
                goal_handle.abort()
                return res

            # ================= CHECKING =================
            self._feedback(goal_handle, F.PHASE_CHECKING, t_start)
            reached, rerr = self._ee_pose_now()
            if reached is None:
                self._motion_blocked = True
                self._motion_blocked_reason = 'end-effector pose unavailable: %s' % rerr
                res = self._result(R.OUTCOME_STATE_UNKNOWN, R.ERR_STATE_UNAVAILABLE,
                                   ecode, detail=rerr)
                res.execution_started = execution_started
                res.evidence_id = evidence
                rec.update(outcome='STATE_UNKNOWN', error_code=R.ERR_STATE_UNAVAILABLE)
                self._log(rec)
                goal_handle.abort()
                return res

            tgt = target_base.pose
            dx = reached.pose.position.x - tgt.position.x
            dy = reached.pose.position.y - tgt.position.y
            dz = reached.pose.position.z - tgt.position.z
            pos_err = math.sqrt(dx * dx + dy * dy + dz * dz)
            ori_err = q_angle_between(reached.pose.orientation, tgt.orientation)

            rec['reached_pose'] = {
                'frame_id': reached.header.frame_id,
                'position': [reached.pose.position.x, reached.pose.position.y,
                             reached.pose.position.z],
                'orientation': [reached.pose.orientation.x, reached.pose.orientation.y,
                                reached.pose.orientation.z, reached.pose.orientation.w],
            }
            rec['position_error_m'] = pos_err
            rec['orientation_error_rad'] = ori_err
            rec['position_tolerance_m'] = self._pos_tol
            rec['orientation_tolerance_rad'] = self._ori_tol
            rec['orientation_enforced'] = self._enforce_ori

            ori_ok = (not self._enforce_ori) or (ori_err <= self._ori_tol)
            if pos_err <= self._pos_tol and ori_ok:
                res = self._result(R.OUTCOME_SUCCEEDED, R.ERR_NONE, ecode,
                                   detail='planning + execution + measured pose within tolerance')
                res.outcome = R.OUTCOME_SUCCEEDED
            else:
                res = self._result(
                    R.OUTCOME_FAILED, R.ERR_POSE_NOT_REACHED, ecode,
                    detail='measured pose outside tolerance: pos=%.4fm (tol %.3f) '
                           'ori=%.4frad (tol %.3f, enforced=%s)'
                           % (pos_err, self._pos_tol, ori_err, self._ori_tol,
                              self._enforce_ori))
            res.reached_pose = reached
            res.has_reached_pose = True
            res.position_error_m = pos_err
            res.orientation_error_rad = ori_err
            res.execution_started = execution_started
            res.evidence_id = evidence
            rec.update(outcome='SUCCEEDED' if res.outcome == R.OUTCOME_SUCCEEDED
                       else 'POSE_NOT_REACHED',
                       error_code=res.error_code,
                       elapsed_ms=int((time.monotonic() - t_start) * 1000))
            self._log(rec)

            if res.outcome == R.OUTCOME_SUCCEEDED:
                goal_handle.succeed()
            else:
                goal_handle.abort()
            return res

        except Exception as exc:  # crash guard (audit P0-1): move_to_pose was
            # the one server still missing it - rclpy's fallback for a raising
            # execute callback is a default Result whose outcome=0 reads as
            # OUTCOME_SUCCEEDED
            rec.update(outcome='FAILED', error_code=R.ERR_INTERNAL,
                       detail=crash_detail(exc),
                       elapsed_ms=int((time.monotonic() - t_start) * 1000))
            self._log(rec)
            res = self._result(R.OUTCOME_FAILED, R.ERR_INTERNAL,
                               detail=crash_detail(exc))
            res.evidence_id = evidence
            goal_handle.abort()
            return res
        finally:
            self._admission.release()

    # ------------------------------------------------------------- stopping
    # ------------------------------------------------------------- execution backends
    def _send_for_execution(self, traj, deadline_t):
        """Hand the planned trajectory to the selected execution backend.

        controller_action  : FlexCell owns the controller goal -> cancel is real
        moveit_execute_trajectory : legacy path; MoveIt 2.12.4 does not preempt
        """
        if self._backend == 'controller_action':
            if not self._fjt_client.wait_for_server(timeout_sec=2.0):
                return ('unavailable', None, None,
                        'controller action %s unavailable' % self._fjt_action)
            g = FollowJointTrajectory.Goal()
            g.trajectory = traj.joint_trajectory
            sf = self._fjt_client.send_goal_async(g)
            st = self._wait(sf, None, min(deadline_t, time.monotonic() + 5.0))
            if st != 'done':
                return ('send_timeout', None, None, 'no response from controller action')
            gh = sf.result()
            if gh is None or not gh.accepted:
                return ('rejected', None, None, 'controller rejected the trajectory')
            return ('sent', gh, gh.get_result_async(), '')

        if not self._exec_client.wait_for_server(timeout_sec=2.0):
            return ('unavailable', None, None,
                    'execute action %s unavailable' % self._exec_act)
        g = ExecuteTrajectory.Goal()
        g.trajectory = traj
        sf = self._exec_client.send_goal_async(g)
        st = self._wait(sf, None, min(deadline_t, time.monotonic() + 5.0))
        if st != 'done':
            return ('send_timeout', None, None, 'no response from execute action')
        gh = sf.result()
        if gh is None or not gh.accepted:
            return ('rejected', None, None, 'trajectory rejected by the controller manager')
        return ('sent', gh, gh.get_result_async(), '')

    def _backend_result_code(self, result):
        if self._backend == 'controller_action':
            return int(result.error_code)  # FollowJointTrajectory: plain int
        return int(result.error_code.val)

    def _backend_code_is_success(self, code):
        if self._backend == 'controller_action':
            return code == 0  # FollowJointTrajectory.SUCCESSFUL
        return code == MoveItErrorCodes.SUCCESS

    def _stop_and_finish(self, goal_handle, rec, evidence, t_start, execution_started,
                         reason, backend_goal_handle=None, result_future=None,
                         planned_final_positions=None, traj_joint_names=None):
        """Cancel/timeout during execution: STOP, then CONFIRM the robot stopped.

        Strict stop confirmation - ALL FIVE required:
          1. a stop request was really sent to the component owning the trajectory
          2. downstream accepted it (goals_canceling >= 1)
          3. joint velocities actually reached rest
          4. the robot did NOT reach the planned trajectory endpoint
          5. the state could be re-read afterwards

        A merely stationary robot is NOT confirmation: it may simply have finished
        the original trajectory.
        """
        self._feedback(goal_handle, F.PHASE_STOPPING, t_start)
        rec['stop_reason'] = reason
        rec['execution_backend'] = self._backend

        # ---- (1)+(2) real stop request, and was it accepted? ----
        stop_request_sent = False
        stop_accepted = False
        if backend_goal_handle is not None:
            try:
                cf = backend_goal_handle.cancel_goal_async()
                stop_request_sent = True
                self._wait(cf, None, time.monotonic() + self._stop_timeout)
                if cf.done() and cf.result() is not None:
                    gc = getattr(cf.result(), 'goals_canceling', None) or []
                    rec['stop_goals_canceling'] = len(gc)
                    stop_accepted = len(gc) > 0
                else:
                    rec['stop_response'] = 'no response within %.1fs' % self._stop_timeout
            except Exception as exc:  # noqa: BLE001
                rec['stop_request_error'] = str(exc)
        else:
            rec['stop_request_error'] = 'no backend goal handle: no stop request could be sent'
        rec['stop_request_sent'] = stop_request_sent
        rec['stop_request_accepted'] = stop_accepted

        # ---- did the backend goal terminate? ----
        terminated = False
        if result_future is not None:
            self._wait(result_future, None, time.monotonic() + self._stop_result_timeout)
            if result_future.done():
                terminated = True
                try:
                    code = self._backend_result_code(result_future.result().result)
                    rec['execution_termination_error_code'] = code
                except Exception as exc:  # noqa: BLE001
                    rec['execution_result_error'] = str(exc)
        rec['execution_terminated'] = terminated

        # ---- (3) velocities actually reached rest ----
        at_rest = False
        why = 'not checked'
        stop_deadline = time.monotonic() + self._stop_timeout
        while time.monotonic() < stop_deadline:
            at_rest, why = self._arm_at_rest()
            if at_rest:
                break
            time.sleep(0.05)
        rec['robot_at_rest'] = at_rest
        rec['robot_at_rest_detail'] = why

        # ---- (4) did the robot avoid the planned endpoint? ----
        cut_short = None
        if planned_final_positions and traj_joint_names:
            js, _age = self._joint_state()
            if js is not None:
                idx = {n: i for i, n in enumerate(js.name)}
                devs = [abs(js.position[idx[n]] - t)
                        for n, t in zip(traj_joint_names, planned_final_positions)
                        if n in idx]
                if devs:
                    cut_short = max(devs)
                    rec['max_deviation_from_planned_end_rad'] = cut_short
        avoided = cut_short is not None and cut_short > self._cut_short_rad
        rec['avoided_planned_endpoint'] = avoided

        # ---- (5) state re-readable ----
        js2, age2 = self._joint_state()
        state_readable = js2 is not None and age2 is not None and age2 <= self._js_max_age
        rec['state_readable'] = state_readable

        preempted = stop_accepted and avoided
        stop_confirmed = (stop_request_sent and stop_accepted and at_rest
                          and avoided and state_readable)
        rec['preempted'] = preempted
        rec['stop_confirmed'] = stop_confirmed

        if stop_confirmed:
            rec['stop_mode'] = 'preempted'
        elif stop_request_sent and at_rest and state_readable and not avoided:
            rec['stop_mode'] = 'already_completed'
        else:
            rec['stop_mode'] = 'unconfirmed'

        if rec['stop_mode'] == 'unconfirmed':
            # Cannot prove what happened -> STATE_UNKNOWN and close the motion gate.
            self._motion_blocked = True
            self._motion_blocked_reason = '%s with unconfirmed stop' % reason
            res = self._result(
                R.OUTCOME_STATE_UNKNOWN, R.ERR_STATE_UNKNOWN,
                detail=('%s: stop NOT confirmed (sent=%s accepted=%s at_rest=%s '
                        'avoided_endpoint=%s state_readable=%s); motion latched off '
                        'until the state is reconfirmed'
                        % (reason, stop_request_sent, stop_accepted, at_rest,
                           avoided, state_readable)))
            res.execution_started = execution_started
            res.preempted = False
            res.stop_confirmed = False
            res.evidence_id = evidence
            rec.update(outcome='STATE_UNKNOWN', error_code=R.ERR_STATE_UNKNOWN)
            self._log(rec)
            goal_handle.abort()
            return res

        err = R.ERR_EXECUTION_TIMEOUT if reason == 'timeout' else R.ERR_CANCELED
        outcome = R.OUTCOME_FAILED if reason == 'timeout' else R.OUTCOME_CANCELED
        if rec['stop_mode'] == 'preempted':
            note = 'preempted; stop confirmed'
        else:
            note = ('the trajectory had already completed before the stop request took '
                    'effect; nothing was preempted')
        res = self._result(outcome, err, detail='%s; %s' % (reason, note))
        res.execution_started = execution_started
        res.preempted = preempted
        res.stop_confirmed = stop_confirmed
        res.evidence_id = evidence
        rec.update(outcome='CANCELED' if outcome == R.OUTCOME_CANCELED else 'FAILED',
                   error_code=err)
        self._log(rec)
        if outcome == R.OUTCOME_CANCELED:
            goal_handle.canceled()
        else:
            goal_handle.abort()
        return res

    # ------------------------------------------------------------- validation
    def _clamp_deadline(self, deadline_ms):
        if deadline_ms == 0:
            return self._default_deadline_ms
        return int(min(deadline_ms, self._max_deadline_ms))

    def _validate(self, goal):
        """Returns (error_code|None, detail, (vel, acc)|None)."""
        p = goal.target.pose.position
        q = goal.target.pose.orientation
        vals = [p.x, p.y, p.z, q.x, q.y, q.z, q.w]
        for v in vals:
            if not math.isfinite(v):
                return R.ERR_INVALID_GOAL, 'non-finite numeric value in target', None

        n = q_norm(q)
        if n < 1e-6:
            return R.ERR_INVALID_GOAL, 'zero-length quaternion', None
        if abs(n - 1.0) > 1e-3:
            return R.ERR_INVALID_GOAL, 'quaternion not normalized (norm=%.6f)' % n, None

        if not goal.target.header.frame_id:
            return R.ERR_INVALID_GOAL, 'target.frame_id is empty', None

        # frame availability
        try:
            self._tf_buffer.lookup_transform(
                self._base, goal.target.header.frame_id, Time(),
                Duration(seconds=self._tf_timeout))
        except Exception as exc:  # noqa: BLE001
            return R.ERR_FRAME_UNAVAILABLE, 'cannot resolve frame %s: %s' % (
                goal.target.header.frame_id, exc), None

        # workspace boundary (in base frame)
        tgt_base, terr = self._transform_to_base(goal.target)
        if tgt_base is None:
            return R.ERR_FRAME_UNAVAILABLE, terr, None
        tp = tgt_base.pose.position
        if not (self._ws_min[0] <= tp.x <= self._ws_max[0]
                and self._ws_min[1] <= tp.y <= self._ws_max[1]
                and self._ws_min[2] <= tp.z <= self._ws_max[2]):
            return (R.ERR_INVALID_GOAL,
                    'target [%.3f %.3f %.3f] outside workspace '
                    '[%.2f..%.2f, %.2f..%.2f, %.2f..%.2f]'
                    % (tp.x, tp.y, tp.z,
                       self._ws_min[0], self._ws_max[0],
                       self._ws_min[1], self._ws_max[1],
                       self._ws_min[2], self._ws_max[2]), None)

        # motion profile whitelist
        pid = goal.motion_profile_id or self._default_profile
        if pid not in self._profiles:
            return (R.ERR_INVALID_GOAL,
                    'motion_profile_id %r not in whitelist %s'
                    % (pid, sorted(self._profiles)), None)

        # world revision gate
        if goal.expected_world_revision != 0 and not self._world_gate:
            return (R.ERR_STALE_WORLD,
                    'expected_world_revision=%d but the world revision gate is not '
                    'enabled in Day 2 fixed-scene mode; refusing rather than faking '
                    'a revision' % goal.expected_world_revision, None)

        return None, '', self._profiles[pid]

    def _build_request(self, target_base, vel, acc, allowed_planning_time):
        req = MotionPlanRequest()
        req.group_name = self._group
        req.num_planning_attempts = 10
        req.allowed_planning_time = allowed_planning_time
        req.max_velocity_scaling_factor = vel
        req.max_acceleration_scaling_factor = acc

        ws = WorkspaceParameters()
        ws.header.frame_id = self._base
        ws.min_corner.x, ws.min_corner.y, ws.min_corner.z = self._ws_min
        ws.max_corner.x, ws.max_corner.y, ws.max_corner.z = self._ws_max
        req.workspace_parameters = ws

        c = Constraints()
        pc = PositionConstraint()
        pc.header.frame_id = self._base
        pc.header.stamp = self.get_clock().now().to_msg()
        pc.link_name = self._ee_link
        pc.target_point_offset = Vector3(x=0.0, y=0.0, z=0.0)
        bv = BoundingVolume()
        sp = SolidPrimitive()
        sp.type = SolidPrimitive.SPHERE
        sp.dimensions = [self._constraint_radius]
        bv.primitives.append(sp)
        sphere_pose = Pose()
        sphere_pose.position = target_base.pose.position
        sphere_pose.orientation.w = 1.0
        bv.primitive_poses.append(sphere_pose)
        pc.constraint_region = bv
        pc.weight = 1.0
        c.position_constraints.append(pc)

        if self._enforce_ori:
            oc = OrientationConstraint()
            oc.header.frame_id = self._base
            oc.header.stamp = self.get_clock().now().to_msg()
            oc.link_name = self._ee_link
            oc.orientation = target_base.pose.orientation
            oc.absolute_x_axis_tolerance = self._ori_tol
            oc.absolute_y_axis_tolerance = self._ori_tol
            oc.absolute_z_axis_tolerance = self._ori_tol
            oc.parameterization = OrientationConstraint.XYZ_EULER_ANGLES
            oc.weight = 1.0
            c.orientation_constraints.append(oc)

        req.goal_constraints.append(c)
        return req

    def _ik_feasible(self, target_base):
        """Explicit IK reachability pre-check.

        Distinguishes 'unreachable target' from 'no collision-free plan' instead of
        burning the whole planning budget inside OMPL and reporting a timeout.
        """
        if not self._ik_client.wait_for_service(timeout_sec=1.0):
            return True, 'ik service %s unavailable; pre-check skipped' % self._ik_srv
        req = GetPositionIK.Request()
        ir = PositionIKRequest()
        ir.group_name = self._group
        ir.ik_link_name = self._ee_link
        ir.pose_stamped = target_base
        ir.avoid_collisions = False
        ir.timeout = Duration(seconds=self._ik_timeout).to_msg()
        req.ik_request = ir
        fut = self._ik_client.call_async(req)
        end = time.monotonic() + self._ik_timeout + 2.0
        while not fut.done() and time.monotonic() < end:
            time.sleep(0.02)
        if not fut.done():
            return True, 'ik pre-check timed out; continuing to planning'
        resp = fut.result()
        code = int(resp.error_code.val)
        if code == MoveItErrorCodes.SUCCESS:
            return True, 'IK solution found'
        if code == MoveItErrorCodes.NO_IK_SOLUTION:
            return False, 'NO_IK_SOLUTION for link %s' % self._ee_link
        return False, 'IK error %d: %s' % (code, resp.error_code.message)

    def _map_plan_error(self, code):
        if code == MoveItErrorCodes.NO_IK_SOLUTION:
            return R.ERR_IK_UNREACHABLE
        if code in (MoveItErrorCodes.GOAL_CONSTRAINTS_VIOLATED,
                    MoveItErrorCodes.GOAL_STATE_INVALID,
                    MoveItErrorCodes.INVALID_GOAL_CONSTRAINTS):
            return R.ERR_IK_UNREACHABLE
        if code == MoveItErrorCodes.TIMED_OUT:
            return R.ERR_PLANNING_TIMEOUT
        if code == MoveItErrorCodes.FRAME_TRANSFORM_FAILURE:
            return R.ERR_FRAME_UNAVAILABLE
        if code in (MoveItErrorCodes.START_STATE_INVALID,
                    MoveItErrorCodes.ROBOT_STATE_STALE,
                    MoveItErrorCodes.INVALID_ROBOT_STATE):
            return R.ERR_STATE_UNAVAILABLE
        if code == MoveItErrorCodes.CONTROL_FAILED:
            return R.ERR_EXECUTION_FAILED
        return R.ERR_NO_COLLISION_FREE_PLAN

    @staticmethod
    def _err_name(code):
        for k, v in vars(R).items():
            if k.startswith('ERR_') and v == code:
                return k
        return 'ERR_%d' % code


def main(args=None):
    rclpy.init(args=args)
    node = MoveToPoseServer()
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
