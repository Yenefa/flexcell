#!/usr/bin/env python3
"""FlexCell Push skill server (T08, contact push - no grasp).

WHAT THIS IS
    The thin ROS adapter around contracts/push.py. It owns NO decisions: it
    measures the object, commands end-effector poses, reads the carry state and
    publishes what happened. Every threshold and every verdict lives in the
    pure contract, so the whole skill can be tested without a robot.

WHY IT EXISTS (measured, not argued)
    T08 Step-0 (ci-public-window/evidence/evobot_t08_push_step0_20261111/)
    showed that end-effector contact does push the box along a commanded
    direction (23.02 mm, direction cosine 0.9965, 1.9 mm lateral, dz 0), and
    that the displacement SATURATES at 23 mm: the arm advanced a further 16 mm
    and the box did not move at all. So the failure mode is contact LOSS, not
    "pushing slowly". A skill that reported success on "the arm reached its
    target" would have called that run a success. This one reports
    ERR_CONTACT_LOST instead.

WHY THE GRIPPER IS NEVER COMMANDED
    A push must be distinguishable from a carry. This server does not even
    construct a gripper client: the gripper stays wherever it was, and the
    measured carry state must stay disengaged for the whole motion. If the
    carry backend engages, the object's motion is explained by being pinned to
    the arm and the evidence is worthless, so the skill fails with
    ERR_PUSH_BLOCKED regardless of how good the numbers look.

WHY contact_height_m IS A REQUEST FIELD *AND* A PARAMETER
    The correct contact height depends on the arm configuration, not on a
    constant: this stack runs position-only IK, so the wrist attitude (and
    therefore where the fingers sit relative to end_effector_link) is whatever
    the solver returns. At EE z = 0.1775 the fingers passed 145 mm ABOVE the
    box and nothing moved; at z = 0.030 the box moved. A hard-coded constant
    would have been wrong in both directions, so the height is declarable per
    request and defaults to a node parameter that is NaN (refuse) rather than
    a guess.

WHY THE MOTION IS OPEN LOOP WITH OVERDRIVE
    The arm is sent past the object's far face. If the object yields, the arm
    arrives and position_error_m is small. If the object does not yield, the
    arm is blocked and position_error_m is large. That is what turns the arm's
    own measured reach error into an honest "I could not get through" signal
    instead of a self-report.
"""

import math
import threading
import time

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from flexcell_interfaces.action import PushObject
from flexcell_interfaces.srv import QueryCarry

from flexcell_skills import known_objects
from flexcell_skills.contracts import push as contract
from flexcell_skills.contracts.skill_result import derive_status
from flexcell_skills.common import (
    JsonlLog, MoveToPoseClient, crash_detail, new_evidence, sample_gz_pose,
    wait_future)

R = PushObject.Result
F = PushObject.Feedback


def _finite_json(value):
    """Recursively replace non-finite floats with None so json.dumps accepts it.

    NaN/inf are Python-only JSON extensions; a reader that follows the spec
    (or a strict loader) rejects the whole line, turning measured evidence into
    an unreadable record. None says "not measurable", which is the truth.
    """
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _finite_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite_json(v) for v in value]
    return value

PHASES = {
    'VALIDATING': F.PHASE_VALIDATING,
    'OBSERVING': F.PHASE_OBSERVING,
    'APPROACH': F.PHASE_APPROACH,
    'PUSHING': F.PHASE_PUSHING,
    'VERIFYING': F.PHASE_VERIFYING,
    'RETREATING': F.PHASE_RETREATING,
}

# Node parameters that the pure contract also understands. Declared with the
# contract's own defaults so there is exactly one place a baseline is written.
_CONTRACT_PARAMS = ('contact_floor_m', 'increment_floor_m', 'direction_cos_min',
                    'lateral_max_m', 'delta_z_max_m', 'arm_reach_tolerance_m',
                    'displacement_tolerance_m', 'increments', 'max_increments',
                    'approach_clearance_m', 'retreat_clearance_m',
                    'push_min_distance_m', 'push_max_distance_m',
                    'push_min_overdrive_m', 'push_max_overdrive_m')


class PushServer(Node):

    def __init__(self):
        super().__init__('push_server')

        self.declare_parameter('move_to_pose_action', '/move_to_pose')
        self.declare_parameter('carry_query_service', '/flexcell/carry_snapshot')
        self.declare_parameter('object_size', [0.035, 0.035, 0.035])
        self.declare_parameter('base_frame', 'world')
        self.declare_parameter('default_deadline_ms', 30000)
        self.declare_parameter('motion_profile_names',
                               ['demo_veryslow', 'demo_slow', 'demo_default'])
        self.declare_parameter('default_motion_profile', 'demo_slow')
        # NaN default: a stack that never declares a contact height must refuse
        # rather than silently push at some height nobody measured.
        self.declare_parameter('contact_height_m', float('nan'))
        for name in _CONTRACT_PARAMS:
            self.declare_parameter(name, contract.DEFAULTS[name])
        self.declare_parameter('sample_max_age_s', 0.5)
        self.declare_parameter('sample_timeout_s', 8.0)
        self.declare_parameter('log_dir', '~/.ros/flexcell')
        self.declare_parameter('log_file', 'push.jsonl')
        self.declare_parameter('admission_wait_s', 5.0)
        self.declare_parameter('tracked_objects',
                               list(known_objects.DEFAULT_OBJECTS))

        gp = self.get_parameter
        self._objects = known_objects.Registry(gp('tracked_objects').value)
        self._m2p = MoveToPoseClient(self, gp('move_to_pose_action').value)
        self._carry_query = self.create_client(
            QueryCarry, gp('carry_query_service').value,
            callback_group=ReentrantCallbackGroup())
        self._base = gp('base_frame').value
        self._size = list(gp('object_size').value)
        self._deadline = int(gp('default_deadline_ms').value)
        self._profiles = list(gp('motion_profile_names').value)
        self._default_profile = gp('default_motion_profile').value
        self._sample_age = float(gp('sample_max_age_s').value)
        self._sample_timeout = float(gp('sample_timeout_s').value)
        self._log = JsonlLog(self, gp('log_dir').value, gp('log_file').value)
        self._admission = threading.Lock()
        self._admission_wait_s = float(gp('admission_wait_s').value)
        self._seq = 0

        # Snapshot the contract parameters ONCE at startup. A parameter edited
        # mid-run would make two pushes in the same batch incomparable.
        self._params = {name: gp(name).value for name in _CONTRACT_PARAMS}
        height = float(gp('contact_height_m').value)
        self._params['contact_height_m'] = height

        self._server = ActionServer(
            self, PushObject, 'push_object',
            execute_callback=self._execute,
            goal_callback=lambda req: GoalResponse.ACCEPT,
            cancel_callback=lambda gh: CancelResponse.ACCEPT,
            callback_group=ReentrantCallbackGroup())

        self.get_logger().info(
            'Push server up | contact_height=%s increments=%s '
            'contact_floor=%.4fm' % (
                'UNSET (request must declare it)'
                if not math.isfinite(height) else '%.4fm' % height,
                self._params['increments'], self._params['contact_floor_m']))

    # ------------------------------------------------------------- evidence
    def _measure(self, name):
        """Ground-truth object position, or (None, reason).

        Same sampler the rest of the stack uses, so this is not a second
        opinion about where the box is.
        """
        pose, error = sample_gz_pose(name, timeout_s=self._sample_timeout,
                                     max_age_s=self._sample_age)
        if pose is None:
            return None, error
        return [float(v) for v in pose[0]], None

    def _carry_engaged(self):
        """(engaged, reason). Read-only snapshot; never inferred from logs."""
        if not self._carry_query.wait_for_service(timeout_sec=2.0):
            return None, 'carry snapshot service unavailable'
        future = self._carry_query.call_async(QueryCarry.Request())
        if wait_future(future, 2.0) != 'done':
            return None, 'carry snapshot timed out'
        reply = future.result()
        if reply is None or not reply.success:
            return None, 'carry snapshot rejected: %s' % getattr(
                reply, 'detail', 'no reply')
        return bool(reply.state.engaged), None

    # ------------------------------------------------------------- adapter
    def _execute(self, goal_handle):
        t0 = time.monotonic()
        goal = goal_handle.request
        self._seq += 1
        rid, evidence = new_evidence(goal.request_id or goal.object_name,
                                     self._seq)
        res = R()
        rec = {'request_id': rid, 'evidence_id': evidence,
               'object_name': goal.object_name,
               'profile': goal.motion_profile_id or self._default_profile}
        phases = []
        terminal = {}
        # Running measured displacement, so a caller can watch saturation happen
        # instead of only learning about it at the end. Filled from the
        # contract's own INCREMENT_MEASURED events - not recomputed here, so
        # there is one arithmetic path.
        progress = {'displacement_m': 0.0}

        def finish(outcome, error_code, detail, **extra):
            res.outcome = int(outcome)
            res.status = derive_status('PUSH', int(outcome))
            res.error_code = int(error_code)
            res.detail = detail
            res.evidence_id = evidence
            for field, value in extra.items():
                if hasattr(res, field):
                    if field in ('measured_before', 'measured_after'):
                        # Wire type is geometry_msgs/Pose; the contract speaks
                        # xyz lists. Convert instead of raising, which would
                        # turn a measured push into ERR_INTERNAL.
                        pose = getattr(res, field)
                        pose.position.x, pose.position.y, pose.position.z = value
                        pose.orientation.w = 1.0
                    else:
                        setattr(res, field, value)
                rec[field] = value
            rec.update(outcome=str(int(outcome)), error_code=int(error_code),
                       status=int(res.status), detail=detail,
                       feedback_phases=list(phases),
                       elapsed_ms=int((time.monotonic() - t0) * 1000))
            # A direction cosine is NaN when the object did not move, and the
            # same NaN rides inside the emitted events. NaN is not valid JSON
            # and the log reader rejects such a line, i.e. a real measurement
            # would be lost as unreadable evidence. Replace recursively; the
            # detail string still says why it was undefined.
            rec.update(_finite_json(rec))
            self._log.write(rec)
            if int(outcome) == contract.OUTCOME_SUCCEEDED:
                goal_handle.succeed()
            elif int(outcome) == contract.OUTCOME_CANCELED:
                goal_handle.canceled()
            else:
                goal_handle.abort()
            return res

        def feedback(phase):
            phases.append(phase)
            fb = F()
            fb.phase = PHASES.get(phase, F.PHASE_VALIDATING)
            fb.elapsed_ms = int((time.monotonic() - t0) * 1000)
            fb.displacement_m = float(progress.get('displacement_m') or 0.0)
            goal_handle.publish_feedback(fb)

        def emit(event, **data):
            rec.setdefault('events', []).append(dict(event=event, **data))

        class _IO:
            """Binds the contract's abstract world to this node."""

            def measure(_self):
                return self._measure(goal.object_name)

            def move_to(_self, target):
                position = [float(v) for v in target]
                result, error = self._m2p.call(
                    position, profile=rec['profile'],
                    deadline_ms=self._deadline, request_id=rid,
                    cancel_check=lambda: goal_handle.is_cancel_requested)
                if result is None:
                    return False, float('nan'), error or 'move_to_pose failed'
                error_code = int(getattr(result, 'error_code', 0))
                reach = getattr(result, 'position_error_m', float('nan'))
                ok = (int(getattr(result, 'outcome', 1)) == 0
                      and error_code == 0 and math.isfinite(float(reach))
                      and float(reach) <= self._params['arm_reach_tolerance_m'])
                return ok, float(reach), str(getattr(result, 'detail', ''))

            def carry_engaged(_self):
                return self._carry_engaged()

            def cancelled(_self):
                return goal_handle.is_cancel_requested

            def phase(_self, name):
                feedback(name)

            def emit(_self, event, **data):
                if event == 'INCREMENT_MEASURED':
                    measured = data.get('displacement_m')
                    if isinstance(measured, float) and math.isfinite(measured):
                        progress['displacement_m'] = measured
                emit(event, **data)

        if not self._admission.acquire(timeout=self._admission_wait_s):
            return finish(contract.OUTCOME_FAILED, contract.ERR_RESOURCE_BUSY,
                          'another push goal is active')
        try:
            if not goal.object_name:
                return finish(contract.OUTCOME_FAILED,
                              contract.ERR_INVALID_GOAL, 'object_name is empty')
            if goal.object_name not in self._objects.known():
                return finish(contract.OUTCOME_FAILED,
                              contract.ERR_OBJECT_NOT_FOUND,
                              'object %r is not in tracked_objects'
                              % goal.object_name)
            if rec['profile'] not in self._profiles:
                return finish(contract.OUTCOME_FAILED,
                              contract.ERR_INVALID_GOAL,
                              'motion_profile_id %r not in whitelist %s'
                              % (rec['profile'], self._profiles))
            half = max(self._size[0], self._size[1]) / 2.0
            outcome = contract.execute_push(
                _IO(), dict(
                    object_name=goal.object_name,
                    direction=[goal.direction.x, goal.direction.y,
                               goal.direction.z],
                    distance_m=goal.distance_m,
                    contact_height_m=goal.contact_height_m,
                    overdrive_m=goal.overdrive_m,
                    max_increments=int(goal.max_increments)),
                self._params, half_extent_m=half)
            terminal.update(outcome)
            extra = {k: v for k, v in outcome.items()
                     if k not in ('outcome', 'error_code', 'detail')}
            return finish(outcome['outcome'], outcome['error_code'],
                          outcome['detail'], **extra)
        except Exception as exc:  # crash guard: a raising execute callback
            # would leave rclpy's default Result with outcome=0 = SUCCEEDED
            return finish(contract.OUTCOME_FAILED, contract.ERR_INTERNAL,
                          crash_detail(exc))
        finally:
            self._admission.release()


def main(args=None):
    rclpy.init(args=args)
    node = PushServer()
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
