"""Plan with MTC, hand trajectories to the existing single-arm executor.

Only MoveToPose owns actuator goals, admission, cancellation and stop checks.
An unknown terminal state prevents task recovery or subsequent cleanup motion.
"""
import time
import uuid
import hashlib
import math
from rclpy.serialization import serialize_message
from geometry_msgs.msg import PoseStamped
from rclpy.callback_groups import ReentrantCallbackGroup
from flexcell_interfaces.action import MoveToPose
from flexcell_interfaces.srv import PlanManipulation, RegisterMtcTrajectory
from flexcell_skills.common import MoveToPoseClient, dist3, pose_msg, wait_future
from flexcell_skills.contracts.trajectory import validate_arm_trajectory as validate_trajectory


class MotionTerminalUnknown(RuntimeError):
    pass


def stamped(position, orientation=None):
    value = PoseStamped()
    value.header.frame_id = 'world'
    value.pose = pose_msg(position, orientation or [0., 0., 0., 1.])
    return value


class MtcMotionClient:
    planner_service = '/flexcell/mtc/plan'
    registration_service = '/flexcell/mtc/register_trajectory'
    token_prefix = 'mtc-'
    attached_operations = ('PLACE',)

    def __init__(self, node):
        group = ReentrantCallbackGroup()
        self.planner = node.create_client(PlanManipulation, self.planner_service, callback_group=group)
        self.registration = node.create_client(RegisterMtcTrajectory,
            self.registration_service, callback_group=group)
        self.executor = MoveToPoseClient(node, '/move_to_pose')
        self.blocked = False
        self.plans = []
        self.audit = []
        self.planning_audit = []

    def _unknown(self, detail):
        self.blocked = True
        raise MotionTerminalUnknown(detail + '; task must stop; reconcile before further motion')

    def prepare(self, operation, object_name, object_position, targets, profile, deadline_ms,
                *, attached_object_targets=False, object_orientation=None):
        if self.blocked:
            self._unknown('prior motion terminal state is unknown')
        self.plans = []
        self.audit = []
        if not self.planner.wait_for_service(timeout_sec=3.):
            return False, 'planner unavailable: ' + self.planner_service
        request = PlanManipulation.Request()
        request.operation, request.object_name = operation, object_name
        request.object_pose = stamped(object_position, object_orientation)
        request.attached_object_targets = attached_object_targets
        request.targets = [stamped(position) for position in targets]
        request.motion_profile_id = profile
        request.deadline_ms = min(60000, max(1000, int(deadline_ms)))
        response = None
        retries = 2
        for attempt in range(retries + 1):
            future = self.planner.call_async(request)
            status = wait_future(future, request.deadline_ms / 1000 + 8)
            if status == 'done':
                response = future.result()
                if response.success:
                    break
                busy = 'planner busy' in str(getattr(response, 'detail', ''))
                self.planning_audit.append(dict(attempt=attempt + 1, outcome='busy' if busy else 'failed',
                                                detail=str(getattr(response, 'detail', ''))[:120]))
                if not busy or attempt >= retries:
                    return False, response.detail
            else:
                self.planner.remove_pending_request(future)
                self.planning_audit.append(dict(attempt=attempt + 1, outcome='timeout',
                                                detail='planning reply timed out'))
                if attempt >= retries:
                    return False, 'planning reply timed out; no motion dispatched'
            time.sleep(3.)
        if response is None or not response.success:
            return False, getattr(response, 'detail', 'planning failed')
        if len(response.trajectories) != len(targets):
            return False, 'wrong planned stage count'
        if attached_object_targets:
            if operation not in self.attached_operations or len(response.executor_targets) != len(targets):
                return False, 'attached-point targets require explicit end-effector endpoints'
            executor_targets = []
            for endpoint in response.executor_targets:
                p = endpoint.pose.position
                value = [p.x, p.y, p.z]
                if endpoint.header.frame_id != 'world' or not all(math.isfinite(x) for x in value):
                    return False, 'invalid planned end-effector endpoint'
                executor_targets.append(value)
        else:
            executor_targets = targets
        for item in response.trajectories:
            validate_trajectory(item.joint_trajectory)
        self.plans = list(zip(targets, response.trajectories, executor_targets))
        return True, response.detail

    def call(self, position, *, profile, deadline_ms, request_id, cancel_check=None):
        if self.blocked:
            self._unknown('prior motion terminal state is unknown')
        if not self.plans or dist3(position, self.plans[0][0]) > 1e-6:
            raise ValueError('unplanned or out-of-order stage ' + request_id)
        target, trajectory, executor_target = self.plans.pop(0)
        validate_trajectory(trajectory.joint_trajectory)
        if cancel_check and cancel_check():
            return None, 'canceled before trajectory handoff'
        if not self.registration.wait_for_service(timeout_sec=3.):
            return None, 'trajectory handoff unavailable: ' + self.registration_service
        request = RegisterMtcTrajectory.Request()
        request.request_id = self.token_prefix + uuid.uuid4().hex
        request.target = stamped(executor_target)
        request.motion_profile_id = profile
        request.trajectory = trajectory
        self.audit.append(dict(stage=request_id, request_id=request.request_id,
            target=list(position), profile=profile,
            executor_target=list(executor_target),
            trajectory_sha256=hashlib.sha256(serialize_message(trajectory)).hexdigest()))
        future = self.registration.call_async(request)
        if wait_future(future, 3.) != 'done':
            self.registration.remove_pending_request(future)
            return None, 'trajectory registration reply lost; no motion dispatched'
        response = future.result()
        if not response.success:
            return None, response.detail
        result, error = self.executor.call(executor_target, profile=profile, deadline_ms=deadline_ms,
            request_id=request.request_id, cancel_check=cancel_check)
        self.audit[-1].update(terminal_reply_received=result is not None, transport_error=error,
            evidence_id=result.evidence_id if result is not None else None,
            outcome=int(result.outcome) if result is not None else None,
            error_code=int(result.error_code) if result is not None else None)
        if error is not None or result is None:
            self._unknown('motion executor terminal reply unavailable: ' + str(error))
        if (result.outcome == MoveToPose.Result.OUTCOME_STATE_UNKNOWN
                or result.error_code == MoveToPose.Result.ERR_STATE_UNKNOWN):
            self._unknown(result.detail)
        return result, None


class AttachedPointMotionClient(MtcMotionClient):
    """One OMPL point plan per legacy stage; no MTC task or stage sequence."""
    planner_service = '/flexcell/attached_point/plan'
    registration_service = '/flexcell/attached_point/register_trajectory'
    token_prefix = 'point-'
    attached_operations = ('POINT',)

    def prepare_point(self, object_name, measured_pose, target, profile, deadline_ms):
        position, orientation = measured_pose
        audit = self.audit
        try:
            return self.prepare('POINT', object_name, position, [target], profile, deadline_ms,
                                attached_object_targets=True, object_orientation=orientation)
        finally:
            self.audit = audit
