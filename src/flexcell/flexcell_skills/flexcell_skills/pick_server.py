#!/usr/bin/env python3
"""FlexCell Pick skill server (Week 1).

observe -> approach (hover, descend) -> close gripper + attach -> lift, with
measured checks at every step. Composition over Day-2 MoveToPose: this server
never plans motions itself.

Grasp mode: simulation-only magnetic carry at the measured gripper offset.
The teleport baseline pins pose periodically; velocity_servo constrains pose
and velocity each physics step and confirms engage before lifting. Success
still requires an observed physical rise, otherwise GRASP_FAILED.
"""

import threading
import time
import uuid
import math

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from flexcell_skills import known_objects
from geometry_msgs.msg import PoseStamped, Vector3
from std_msgs.msg import Empty as EmptyMsg
from std_msgs.msg import String as StringMsg
from std_srvs.srv import Trigger
import json
from tf2_ros import Buffer, TransformListener
from rclpy.duration import Duration
from rclpy.time import Time
from rcl_interfaces.srv import GetParameters
from rcl_interfaces.msg import ParameterDescriptor

from flexcell_interfaces.action import PickObject
from flexcell_interfaces.srv import EngageCarry, QueryCarry

from flexcell_skills.contracts.injection import InjectionLifecycle
from flexcell_skills.contracts.skill_result import derive_status
from flexcell_skills.joint_follow import SnapshotWatch, follow_failure_detail, check_backend_parameter
from flexcell_skills.common import (
    GripperClient, JsonlLog, MoveToPoseClient, PlanningSceneOps,
    crash_detail, dist3, gripper_outcome, interruptible_sleep, new_evidence,
    pose_msg, sample_gz_pose, wait_future)

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
        self.declare_parameter('carry_backend', 'teleport', ParameterDescriptor(read_only=True))
        self.declare_parameter('skill_backend', 'legacy')
        self.declare_parameter('record_execution_commands', False)
        self.declare_parameter('carry_engage_service', '/flexcell/carry_engage')
        self.declare_parameter('carry_release_service', '/flexcell/carry_release')
        self.declare_parameter('carry_query_service', '/flexcell/carry_snapshot')
        self.declare_parameter('carry_parameters_service', '/carry_server/get_parameters')
        self.declare_parameter('inject_topic', '/flexcell/inject')
        self.declare_parameter('box_follow_min_m', 0.03)
        self.declare_parameter('joint_follow_hold_sim_s', 0.0, ParameterDescriptor(read_only=True))
        self.declare_parameter('object_size', [0.035, 0.035, 0.035])
        self.declare_parameter('base_frame', 'world')
        self.declare_parameter('end_effector_link', 'end_effector_link')
        self.declare_parameter('default_deadline_ms', 30000)
        self.declare_parameter('motion_profile_names', ['demo_veryslow', 'demo_slow', 'demo_default'])
        self.declare_parameter('default_motion_profile', 'demo_slow')
        self.declare_parameter('log_dir', '~/.ros/flexcell')
        from flexcell_skills import known_objects
        # P1-E: a node-scoped registry, not the shared module-level set
        self._objects = known_objects.Registry(self.declare_parameter(
            'tracked_objects', list(known_objects.DEFAULT_OBJECTS)).value)
        self.declare_parameter('log_file', 'pick.jsonl')

        gp = self.get_parameter
        self._mtc = None
        skill_backend = gp('skill_backend').value
        if skill_backend not in ('legacy', 'mtc'):
            raise ValueError('unsupported skill_backend %r' % skill_backend)
        if skill_backend == 'mtc':
            from flexcell_skills.mtc_motion import MtcMotionClient
            self._mtc = MtcMotionClient(self)
        self._m2p = MoveToPoseClient(self, gp('move_to_pose_action').value)
        self._gripper = GripperClient(self, gp('gripper_action').value,
                                      telemetry=gp('record_execution_commands').value)
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
        self._carry_backend = gp('carry_backend').value
        self._carry_engage = self.create_client(
            EngageCarry, gp('carry_engage_service').value,
            callback_group=ReentrantCallbackGroup())
        self._carry_release = self.create_client(
            Trigger, gp('carry_release_service').value,
            callback_group=ReentrantCallbackGroup())
        self._carry_query = self.create_client(
            QueryCarry, gp('carry_query_service').value,
            callback_group=ReentrantCallbackGroup())
        self._carry_parameters = self.create_client(
            GetParameters, gp('carry_parameters_service').value,
            callback_group=ReentrantCallbackGroup())

        # ---- deterministic failure injection (Week-1.5; lifecycle T6) ----
        # payload "<scenario_id>:<once|always>[#request_id]" arms, "" clears.
        # The four-state lifecycle (requested/armed/applied/cleared) lives in
        # the pure contract module so it is unit-testable; this node only
        # publishes a snapshot on every transition so a requester can SEAL the
        # step instead of firing and hoping (2026-09-29: a request that was
        # never delivered silently ran a cell under the wrong condition).
        self._inject = InjectionLifecycle()
        self.declare_parameter('inject_status_topic', '/flexcell/inject_status')
        self.create_subscription(
            StringMsg, gp('inject_topic').value, self._on_inject, 10)
        self._inject_status = self.create_publisher(
            StringMsg, gp('inject_status_topic').value, self._status_qos())
        self._publish_inject_status()
        self._follow_min = float(gp('box_follow_min_m').value)
        self._joint_hold_sim_s = float(gp('joint_follow_hold_sim_s').value)
        if not math.isfinite(self._joint_hold_sim_s) or not 0. <= self._joint_hold_sim_s <= 20.:
            raise ValueError('joint follow hold must be finite and between 0 and 20 simulation seconds')
        self._size = list(gp('object_size').value)
        self._base = gp('base_frame').value
        self._ee = gp('end_effector_link').value
        self._deadline = int(gp('default_deadline_ms').value)
        self._profiles = list(gp('motion_profile_names').value)
        self._default_profile = gp('default_motion_profile').value
        self._log = JsonlLog(self, gp('log_dir').value, gp('log_file').value)

        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self, spin_thread=False)

        self._admission = threading.Lock()
        self.declare_parameter('admission_wait_s', 5.0)
        self._admission_wait_s = float(self.get_parameter('admission_wait_s').value)
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
    def _sync_scene_objects(self, attached_name):
        """Upsert every configured box into the planning scene at its measured pose.

        Only the grasp target used to be registered, so the planner was blind to the
        other boxes and could sweep straight through them (measured 2026-11-04: a
        carry knocked the third box 0.18 m away).
        """
        synced, skipped = [], []
        for name in known_objects.for_owner(self).known():
            if name == attached_name:
                continue
            measured, error = sample_gz_pose(name, max_age_s=.5)
            if measured is None:
                skipped.append([name, str(error)])
                continue
            position, quaternion = measured
            ok, scene_error = self._scene.add_box(
                name, position, self._size, frame='world', orientation=quaternion)
            (synced if ok else skipped).append(name if ok else [name, scene_error])
        return synced, skipped

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

    def _motion(self, position, profile, request_id, cancel_check=None):
        client = getattr(self, '_mtc', None) or self._m2p
        res, err = client.call(position, profile=profile,
                                  deadline_ms=self._deadline, request_id=request_id,
                                  cancel_check=cancel_check)
        if err is not None:
            return None, 0, err
        return res, int(res.error_code), res.detail

    def _status_qos(self):
        """Latched (TRANSIENT_LOCAL) status QoS.

        The requester is a short-lived process that connects long after this
        node started, so the current state has to be latched - a VOLATILE
        publisher is QoS-INCOMPATIBLE with a TRANSIENT_LOCAL subscriber and the
        seal would then never see the transition (measured 2026-09-29: every
        arm/clear reported "state not observed", surfacing as HARNESS_ERROR).
        """
        from rclpy.qos import (QoSDurabilityPolicy, QoSProfile,
                               QoSReliabilityPolicy)
        qos = QoSProfile(depth=5)
        qos.reliability = QoSReliabilityPolicy.RELIABLE
        qos.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL
        return qos

    def _publish_inject_status(self):
        """Publish the current injection state (latched for late joiners)."""
        try:
            self._inject_status.publish(
                StringMsg(data=json.dumps(self._inject.snapshot(),
                                          sort_keys=True)))
        except Exception as exc:  # noqa: BLE001 - status is observability
            self.get_logger().error('inject status publish failed: %s' % exc)

    def _on_inject(self, msg):
        state = self._inject.on_request(msg.data)
        snap = self._inject.snapshot()
        if snap['error']:
            self.get_logger().error('injection request refused: %s'
                                    % snap['error'])
        elif state == 'armed':
            self.get_logger().info(
                'failure injection ARMED scenario=%s mode=%s request_id=%s'
                % (snap['scenario'], snap['mode'], snap['request_id'] or '-'))
        elif state == 'cleared':
            self.get_logger().info('failure injection DISABLED')
        self._publish_inject_status()

    def _injection_check(self, object_name):
        """Return a detail string when this attempt must fail deterministically."""
        detail = self._inject.on_pick_attempt(object_name)
        if detail:
            self._publish_inject_status()
        return detail

    def _release_everything(self, name):
        """Request physical release and require scene/gripper cleanup responses."""
        if getattr(self, '_carry_backend', 'teleport') in ('velocity_servo', 'detachable_joint'):
            if not self._carry_release.wait_for_service(timeout_sec=2.0):
                return False, 'carry release dependency unavailable; no cleanup motion sent'
            future = self._carry_release.call_async(Trigger.Request())
            if wait_future(future, 5.0) != 'done' or not future.result().success:
                return False, 'physical release not confirmed; no cleanup motion sent'
        else:
            self._carry_stop.publish(EmptyMsg())
        _, gripper_error = self._gripper.command(self._gripper_open)
        removed, scene_error = self._scene.remove(name, detach_attached=True)
        errors = []
        if gripper_error is not None:
            errors.append('gripper open: %s' % gripper_error)
        if not removed:
            errors.append('planning-scene cleanup: %s' % (scene_error or 'rejected'))
        return not errors, '; '.join(errors)

    def _engage_carry(self, object_id, offset):
        if not self._carry_engage.wait_for_service(timeout_sec=2.0):
            return False, 'carry engage service unavailable'
        request = EngageCarry.Request()
        request.request_id = uuid.uuid4().hex
        request.object_id = object_id
        request.reference_frame = self._base
        request.offset = offset
        # A lost service response may be retried with the same ownership token.
        # The server returns the existing session instead of engaging twice.
        for _ in range(2):
            future = self._carry_engage.call_async(request)
            if wait_future(future, 2.0) == 'done':
                result = future.result()
                if result.success and result.session == request.request_id:
                    self._engaged_carry_session = result.session
                return bool(result.success and result.session == request.request_id), result.message
            self._carry_engage.remove_pending_request(future)
        return False, 'carry engage acknowledgement timed out; lift was not started'

    def _joint_carry_released(self):
        if not self._carry_query.wait_for_service(timeout_sec=2.):
            return False, 'carry snapshot unavailable before approach'
        future = self._carry_query.call_async(QueryCarry.Request())
        if wait_future(future, 2.) != 'done':
            self._carry_query.remove_pending_request(future)
            return False, 'carry snapshot timed out before approach'
        response = future.result()
        if response is None or not response.success or response.state.engaged or response.session:
            return False, 'carry is engaged or its state is unknown before approach'
        return True, ''

    def _backend_consistent(self):
        return check_backend_parameter(self._carry_parameters, GetParameters, self._carry_backend)

    def _hold_joint_sim_time(self, seconds, cancel_check, timeout_s=60.):
        """Bounded hold with advancing simulation clock and an active follow check."""
        start_sim = self.get_clock().now().nanoseconds
        deadline = time.monotonic() + timeout_s
        last_sim = start_sim
        while time.monotonic() < deadline:
            if cancel_check():
                return False, 'interrupted'
            current_sim = self.get_clock().now().nanoseconds
            if current_sim < last_sim:
                return False, 'simulation clock moved backwards during follow hold'
            if current_sim - start_sim >= int(seconds * 1e9):
                return True, ''
            last_sim = current_sim
            time.sleep(.05)
        return False, 'simulation clock did not complete the declared hold within the wall deadline'

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
        follow = None

        def finish(outcome, error, detail, motion_err=0):
            if follow is not None:
                rec['joint_follow_watch'] = follow.summary()
            if getattr(self, '_mtc', None) is not None:
                rec['mtc_stages'] = list(self._mtc.audit)
            res.outcome = outcome
            res.status = derive_status('PICK', outcome)
            res.error_code = error
            res.motion_error_code = motion_err
            res.detail = detail
            res.evidence_id = evidence
            rec.update(outcome=str(outcome), error_code=int(error),
                       motion_error_code=int(motion_err), detail=detail,
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
        # Bounded WAIT, not an instant refusal.
        #
        # A composite chain dispatches the next native stage immediately after the
        # previous one reports its terminal result. The previous goal handle is released
        # a moment later, so a non-blocking acquire failed with ERR_RESOURCE_BUSY
        # ("another pick goal is active") on a plan that was entirely valid - a relay
        # task failed at its second stage for this reason in three of six runs.
        #
        # Waiting is bounded and still refuses: if the lock is genuinely held by a
        # different task, the caller gets the same typed error after the deadline.
        if not self._admission.acquire(timeout=self._admission_wait_s):
            return finish(R.OUTCOME_FAILED, R.ERR_RESOURCE_BUSY,
                          'another pick goal is active (waited %.1fs)'
                          % self._admission_wait_s)
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

            consistent, reason = self._backend_consistent()
            if not consistent:
                return finish(R.OUTCOME_FAILED, R.ERR_INTERNAL, reason)

            if self._carry_backend == 'detachable_joint':
                released, reason = self._joint_carry_released()
                if not released:
                    return finish(R.OUTCOME_FAILED, R.ERR_INTERNAL, reason)

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

            # A scene that declares additional boxes must show every one of them
            # to the planner before the approach. Historical two-box profiles keep
            # their exact existing scene sequence.
            if len(known_objects.for_owner(self).known()) > len(known_objects.DEFAULT_OBJECTS):
                synced, skipped = self._sync_scene_objects(goal.object_name)
                rec['scene_synced'] = synced
                rec['scene_sync_skipped'] = skipped
                if skipped:
                    code = (R.ERR_WORLD_STATE_UNAVAILABLE
                            if any('not flowing' in str(reason) for _name, reason in skipped)
                            else R.ERR_OBJECT_UNKNOWN)
                    return finish(R.OUTCOME_FAILED, code,
                                  'configured objects not observable before PICK: %s' % skipped)

            mtc = getattr(self, '_mtc', None)
            if mtc is not None:
                targets = [[box_pos[0], box_pos[1], box_pos[2] + dz]
                           for dz in (self._hover, self._grasp_dz, self._grasp_dz + self._raise)]
                planned, message = mtc.prepare('PICK', goal.object_name, box_pos,
                                               targets, profile, self._deadline,
                                               object_orientation=box_quat)
                rec.update(skill_backend='mtc', planning_detail=message)
                if not planned:
                    return finish(R.OUTCOME_FAILED, R.ERR_MOTION_FAILED,
                                  'MTC planning failed before execution: ' + message)

            # pre-open the gripper so fingers never close on air by accident
            gres, gerr = self._gripper.command(self._gripper_open)
            if gerr is not None:
                return finish(R.OUTCOME_FAILED, R.ERR_MOTION_FAILED,
                              'gripper open failed: %s' % gerr)

            # ---------- APPROACHING ----------
            self._feedback(goal_handle, 'APPROACHING', t0)
            # make the grasped box known to MoveIt at its measured pose so the
            # approach plans AROUND it (measured 2026-09-26: a blind approach
            # swept the box aside and landed 4.7cm short of the hover target)
            scene_added, serr = self._scene.add_box(
                goal.object_name, box_pos, self._size, orientation=box_quat)
            rec['scene_box_added'] = bool(scene_added)

            cancel_requested = lambda: goal_handle.is_cancel_requested  # noqa: E731

            def try_approach():
                hover = [box_pos[0], box_pos[1], box_pos[2] + self._hover]
                r1 = self._motion(hover, profile, rid + '-hover',
                                  cancel_check=cancel_requested)
                if r1[0] is None or int(r1[0].outcome) != R.OUTCOME_SUCCEEDED:
                    return r1
                grasp_t = [box_pos[0], box_pos[1], box_pos[2] + self._grasp_dz]
                return self._motion(grasp_t, profile, rid + '-grasp',
                                    cancel_check=cancel_requested)

            mres, merr_code, detail = try_approach()
            if (mres is None or int(mres.outcome) != R.OUTCOME_SUCCEEDED) \
                    and scene_added and not goal_handle.is_cancel_requested and mtc is None:
                # fallback: drop scene awareness and retry once (knock risk
                # accepted, reported in detail)
                self._scene.remove(goal.object_name)
                scene_added = False
                rec['scene_box_fallback'] = True
                mres, merr_code, detail = try_approach()
            if mres is None or int(mres.outcome) != R.OUTCOME_SUCCEEDED:
                if goal_handle.is_cancel_requested:
                    return finish(R.OUTCOME_CANCELED, R.ERR_CANCELED,
                                  'canceled during approach (motion stopped)')
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
            # P1-D: a completed GripperCommand is not a grasp. Record what the
            # controller actually reported; a close that reports NO_CONTACT is
            # a failed grasp even when the action succeeded.
            close_state = gripper_outcome(gres, requested=self._gripper_close)
            rec['gripper_close'] = close_state
            if close_state["classification"] == "NO_CONTACT":
                cleaned, cleanup_error = self._release_everything(goal.object_name)
                return finish(
                    R.OUTCOME_FAILED,
                    R.ERR_GRASP_FAILED if cleaned else R.ERR_INTERNAL,
                    'gripper closed without contact (position=%r stalled=%r)'
                    % (close_state["position"], close_state["stalled"])
                    if cleaned else 'gripper closed without contact; cleanup failed: %s'
                    % cleanup_error)

            # engage the carry servo at the MEASURED gripper-to-object offset
            offset = [box_pos[i] - ee_pos[i] for i in range(3)]
            rec['carry_offset'] = offset
            if self._carry_backend in ('velocity_servo', 'detachable_joint'):
                confirmed, message = self._engage_carry(goal.object_name, offset)
                rec['carry_engage_confirmed'] = confirmed
                if not confirmed:
                    cleaned, cleanup_error = self._release_everything(goal.object_name)
                    return finish(R.OUTCOME_FAILED,
                                  R.ERR_GRASP_FAILED if cleaned else R.ERR_INTERNAL,
                                  message if cleaned else
                                  message + '; cleanup failed: ' + cleanup_error)
                if self._carry_backend == 'detachable_joint':
                    follow = SnapshotWatch(self._carry_query, QueryCarry, goal.object_name,
                                           self._engaged_carry_session)
                    if not follow.start():
                        return finish(R.OUTCOME_FAILED, R.ERR_INTERNAL,
                                      follow_failure_detail(follow.problem()))
                    cancel_requested = lambda: goal_handle.is_cancel_requested or bool(follow.problem())
            else:
                self._carry_start.publish(StringMsg(data=json.dumps({
                    'object': goal.object_name, 'offset': offset, 'frame': self._base,
                })))
            if interruptible_sleep(0.5, cancel_requested):
                if follow is not None and follow.problem():
                    return finish(R.OUTCOME_FAILED, R.ERR_INTERNAL,
                                  follow_failure_detail(follow.problem()))
                # cancel while the carry servo pins the object: leave the
                # servo engaged (the box hangs from the EE) - releasing here
                # would drop it uncontrolled
                return finish(R.OUTCOME_CANCELED, R.ERR_CANCELED,
                              'canceled while engaging carry (box pinned to '
                              'EE; servo left engaged)')
            # time.sleep replaced by interruptible_sleep (audit P0-3)

            if follow is not None and follow.problem():
                return finish(R.OUTCOME_FAILED, R.ERR_INTERNAL,
                              follow_failure_detail(follow.problem()))

            # Carry engagement can rotate the box. MoveIt derives the attached
            # shape from the world object at attach time, so refresh its FULL
            # measured pose instead of attaching the pre-approach belief.
            sampled, err = sample_gz_pose(goal.object_name, max_age_s=.5)
            if sampled is None:
                return finish(R.OUTCOME_FAILED, R.ERR_INTERNAL,
                              'pre-attach observation unavailable; carry held: %s' % err)
            attach_pos, attach_quat = sampled
            rec['object_before_attach'] = list(attach_pos) + list(attach_quat)
            sok, serr = self._scene.add_box(
                goal.object_name, attach_pos, self._size, orientation=attach_quat)
            if not sok:
                return finish(R.OUTCOME_FAILED, R.ERR_INTERNAL,
                              'pre-attach scene refresh failed; carry held: %s' % serr)
            if follow is not None and follow.problem():
                return finish(R.OUTCOME_FAILED, R.ERR_INTERNAL,
                              follow_failure_detail(follow.problem()))
            sok, serr = self._scene.attach(goal.object_name)
            if not sok:
                if follow is not None:
                    return finish(R.OUTCOME_FAILED, R.ERR_INTERNAL,
                                  'planning-scene attach failed: %s; carry held for reconciliation' % serr)
                self._carry_stop.publish(EmptyMsg())
                return finish(R.OUTCOME_FAILED, R.ERR_GRASP_FAILED,
                              'planning-scene attach failed: %s' % serr)
            if interruptible_sleep(0.5, cancel_requested):
                if follow is not None and follow.problem():
                    return finish(R.OUTCOME_FAILED, R.ERR_INTERNAL,
                                  follow_failure_detail(follow.problem()))
                return finish(R.OUTCOME_CANCELED, R.ERR_CANCELED,
                              'canceled after attach (box attached and '
                              'carried; not released)')

            # ---------- LIFTING ----------
            self._feedback(goal_handle, 'LIFTING', t0)
            lift = [grasp[0], grasp[1], grasp[2] + self._raise]
            mres, merr_code, detail = self._motion(lift, profile, rid + '-lift',
                                                   cancel_check=cancel_requested)
            if follow is not None and follow.problem():
                return finish(R.OUTCOME_FAILED, R.ERR_INTERNAL,
                              follow_failure_detail(follow.problem(), mres, motion_may_be_active=True),
                              motion_err=merr_code)
            if mres is None or int(mres.outcome) != R.OUTCOME_SUCCEEDED:
                if goal_handle.is_cancel_requested:
                    return finish(R.OUTCOME_CANCELED, R.ERR_CANCELED,
                                  'canceled during lift (motion stopped; box '
                                  'attached and carried)')
                # ERR_MOTION_FAILED (30) is a RECOVERABLE pick class, so the
                # policy will retry this pick. Leaving the carry servo engaged
                # made that retry inadmissible (safety gate: already_carried)
                # and masked the typed failure as ERR_SAFETY_REJECTED. Release
                # here so recovery can re-observe the released object
                # (measured: S7 seed 20260931, lift NO_IK_SOLUTION). This
                # helper requests release; it does not confirm a table pose.
                cleaned, cleanup_error = self._release_everything(goal.object_name)
                return finish(R.OUTCOME_FAILED,
                              R.ERR_MOTION_FAILED if cleaned else R.ERR_INTERNAL,
                              'lift motion failed: %s; %s' % (
                                  detail, 'carry release requested for the recovery retry'
                                  if cleaned else 'cleanup failed: ' + cleanup_error),
                              motion_err=merr_code)

            sampled, err = sample_gz_pose(goal.object_name)
            if sampled is None:
                if follow is not None:
                    return finish(R.OUTCOME_FAILED, R.ERR_INTERNAL,
                                  'post-lift observation unavailable; carry held: %s' % err)
                return finish(R.OUTCOME_FAILED, R.ERR_GRASP_FAILED,
                              'post-lift observe failed: %s' % err)
            # sample AFTER a settle: at motion end the carry servo (10Hz
            # set_pose) may not have pulled the box to its pinned height yet,
            # so an immediate sample understates the true rise (audit
            # referee finding: rise 4.9cm reported vs 9.6cm true plateau;
            # 0.5s still undershot at 5.7cm - the servo pulls the box up in
            # steps, ~2s reaches the plateau)
            if follow is not None and self._joint_hold_sim_s > 0:
                held, hold_error = self._hold_joint_sim_time(self._joint_hold_sim_s, cancel_requested)
                rec['joint_follow_hold_sim_s'] = self._joint_hold_sim_s
                if not held:
                    if goal_handle.is_cancel_requested and not follow.problem():
                        return finish(R.OUTCOME_CANCELED, R.ERR_CANCELED,
                                      'canceled during simulation hold (box still carried)')
                    return finish(R.OUTCOME_FAILED, R.ERR_INTERNAL,
                                  follow_failure_detail(follow.problem() or hold_error, mres,
                                                        motion_may_be_active=True))
            elif interruptible_sleep(2.0, cancel_requested):
                if follow is not None and follow.problem():
                    return finish(R.OUTCOME_FAILED, R.ERR_INTERNAL,
                                  follow_failure_detail(follow.problem(), mres, motion_may_be_active=True))
                return finish(R.OUTCOME_CANCELED, R.ERR_CANCELED,
                              'canceled during lift settle (box still carried)')
            sampled, err = sample_gz_pose(goal.object_name)
            if sampled is None:
                if follow is not None:
                    return finish(R.OUTCOME_FAILED, R.ERR_INTERNAL,
                                  'post-settle observation unavailable; carry held: %s' % err)
                return finish(R.OUTCOME_FAILED, R.ERR_GRASP_FAILED,
                              'post-settle observe failed: %s' % err)
            box_after, box_quat = sampled
            res.object_pose_after = pose_msg(box_after, box_quat)
            rec['box_after'] = box_after
            rise = box_after[2] - box_pos[2]
            rec['box_rise_m'] = rise
            if follow is not None and follow.problem():
                return finish(R.OUTCOME_FAILED, R.ERR_INTERNAL,
                              follow_failure_detail(follow.problem(), mres, motion_may_be_active=True))
            if rise < self._follow_min:
                # measured dishonesty guard: the box did not come along
                cleaned, cleanup_error = self._release_everything(goal.object_name)
                return finish(R.OUTCOME_FAILED,
                              R.ERR_GRASP_FAILED if cleaned else R.ERR_INTERNAL,
                              'box did not follow the lift (rise=%.3fm < %.3fm); '
                              '%s' % (rise, self._follow_min,
                                      'carry release requested' if cleaned else
                                      'cleanup failed: ' + cleanup_error))

            if follow is not None and not follow.confirm_now():
                return finish(R.OUTCOME_FAILED, R.ERR_INTERNAL,
                              follow_failure_detail(follow.problem(), mres, motion_may_be_active=True))

            res.grasp_attached = True
            return finish(R.OUTCOME_SUCCEEDED, R.ERR_NONE,
                          'picked %s: attached, measured rise %.3fm'
                          % (goal.object_name, rise))

        except Exception as exc:  # crash guard (issue #20): a raising execute
            # callback must become a typed FAILURE - rclpy's fallback default
            # Result has outcome=0, which reads as OUTCOME_SUCCEEDED
            return finish(R.OUTCOME_FAILED, R.ERR_INTERNAL, crash_detail(exc))
        finally:
            if follow is not None:
                follow.close()
            self._admission.release()



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
