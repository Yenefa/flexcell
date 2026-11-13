"""One-use constrained trajectory handoff to the existing MoveToPose owner."""
import hashlib
import math
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from geometry_msgs.msg import PoseStamped
from moveit_msgs.msg import RobotTrajectory,RobotState
from moveit_msgs.srv import GetStateValidity
from rclpy.action import ActionClient
from rclpy.serialization import serialize_message
from trajectory_msgs.msg import JointTrajectoryPoint
from flexcell_interfaces.action import MoveToPose
from flexcell_interfaces.srv import RegisterMtcTrajectory
from flexcell_capabilities.contact_geometry import ARM


class MotionFailed(RuntimeError):pass
class MotionUnknown(RuntimeError):pass
class MotionCanceled(RuntimeError):pass


class ConstrainedMotion:
    def __init__(self,node,model,state,pump,event,canceled,guard=lambda:None):
        self.node,self.model,self.state,self.pump,self.event=node,model,state,pump,event
        self.canceled,self.guard=canceled,guard
        self.action=ActionClient(node,MoveToPose,'/move_to_pose')
        self.registration=node.create_client(RegisterMtcTrajectory,'/flexcell/attached_point/register_trajectory')
        self.validity=node.create_client(GetStateValidity,'/check_state_validity')
        self.blocked=False;self.terminal_known=True;self.calls=0;self.last_result=None
        self.any_execution_started=False

    def unknown(self,detail):
        self.blocked=True;self.terminal_known=False
        self.event('MOTION_TERMINAL_UNKNOWN',detail=detail)
        raise MotionUnknown(detail)

    def wait(self,future,timeout,physical=False):
        end=time.monotonic()+timeout
        while not future.done() and time.monotonic()<end:self.pump(.02)
        if not future.done():
            if physical:self.unknown('motion goal response unavailable; no further goal or cleanup allowed')
            raise MotionFailed('read-only/registration response timeout; no actuator goal dispatched')
        try:return future.result()
        except Exception as exc:
            if physical:self.unknown('motion transport failed: '+str(exc))
            raise MotionFailed('read-only/registration transport failed: '+str(exc))

    def plan_observed(self,planner,timeout=90.,guard=None):
        """Keep ROS/clock/contact callbacks alive during expensive pure geometry.

        The worker owns no ROS client or actuator. Start state is checked again
        by execute(); cancellation or stale/changed observations never dispatch
        the completed path.
        """
        if self.blocked or not self.terminal_known:self.unknown('planning refused after prior unknown terminal')
        if self.canceled():raise MotionCanceled('caller canceled before planning')
        planning_guard=self.guard if guard is None else guard
        end=time.monotonic()+timeout
        with ThreadPoolExecutor(max_workers=1,thread_name_prefix='contact_geometry') as worker:
            future=worker.submit(planner)
            while not future.done():
                self.pump(.02)
                if self.canceled():raise MotionCanceled('caller canceled during read-only planning')
                reason=planning_guard()
                if reason:raise MotionFailed('observation guard during planning: '+str(reason))
                if time.monotonic()>end:raise MotionFailed('read-only planning budget exhausted; no goal dispatched')
            if self.canceled():raise MotionCanceled('caller canceled while geometry completed')
            return future.result()

    def execute(self,plan,phase):
        if self.blocked or not self.terminal_known:self.unknown('executor latched after prior unknown terminal')
        if self.canceled():raise MotionCanceled('caller canceled before dispatch')
        if self.calls>=min(40,getattr(self,'call_limit',40)):raise MotionFailed('frozen task motion budget exhausted')
        if (not self.action.wait_for_server(timeout_sec=5.)
                or not self.registration.wait_for_service(timeout_sec=3.)
                or not self.validity.wait_for_service(timeout_sec=3.)):
            raise MotionFailed('required executor/registration/collision service unavailable')
        q,gripper=self.state()
        if np.max(np.abs(q-plan['positions'][0]))>.005:
            raise MotionFailed('measured start differs from constrained path; refuse handoff')
        # The private handoff does not plan; check self collision explicitly here.
        samples=list(range(0,len(plan['positions']),max(1,len(plan['positions'])//12)))
        samples.append(len(plan['positions'])-1)
        for index in samples:
            request=GetStateValidity.Request();request.group_name='arm'
            request.robot_state=RobotState();request.robot_state.is_diff=True
            request.robot_state.joint_state.name=list(ARM)+['gripper_left_joint','gripper_right_joint']
            request.robot_state.joint_state.position=[*map(float,plan['positions'][index]),*map(float,gripper)]
            response=self.wait(self.validity.call_async(request),4.)
            if not response.valid:raise MotionFailed('MoveIt rejects a constrained-path self-collision state')
        trajectory=RobotTrajectory();trajectory.joint_trajectory.joint_names=list(ARM)
        for q,v,a,t in zip(plan['positions'],plan['velocities'],plan['accelerations'],plan['times']):
            point=JointTrajectoryPoint();point.positions=list(map(float,q))
            point.velocities=list(map(float,v));point.accelerations=list(map(float,a))
            ns=int(round(float(t)*1e9));point.time_from_start.sec=ns//10**9;point.time_from_start.nanosec=ns%10**9
            trajectory.joint_trajectory.points.append(point)
        qnow,_=self.state()
        if np.max(np.abs(qnow-plan['positions'][0]))>.005:
            raise MotionFailed('state changed during planning; no motion dispatched')
        reason=self.guard()
        if reason:raise MotionFailed('guard refuses actuator dispatch: '+str(reason))
        endpoint=self.model.frames(plan['positions'][-1],gripper)['end_effector_link']
        yaw=float(plan['positions'][-1][0]);pitch=float(sum(plan['positions'][-1][1:]))
        target=PoseStamped();target.header.frame_id='world'
        target.pose.position.x,target.pose.position.y,target.pose.position.z=map(float,endpoint[:3,3])
        cy,sy,cp,sp=math.cos(yaw/2),math.sin(yaw/2),math.cos(pitch/2),math.sin(pitch/2)
        target.pose.orientation.x=-sy*sp;target.pose.orientation.y=cy*sp
        target.pose.orientation.z=sy*cp;target.pose.orientation.w=cy*cp
        registration=RegisterMtcTrajectory.Request();registration.request_id='point-'+uuid.uuid4().hex
        registration.target=target;registration.motion_profile_id='demo_veryslow';registration.trajectory=trajectory
        response=self.wait(self.registration.call_async(registration),4.)
        if not response.success:raise MotionFailed('handoff refused: '+response.detail)
        if self.canceled():raise MotionCanceled('caller canceled before actuator goal')
        current_q,_=self.state()
        if np.max(np.abs(current_q-plan['positions'][0]))>.005:
            raise MotionFailed('state changed during registration; no actuator goal dispatched')
        reason=self.guard()
        if reason:raise MotionFailed('guard refuses registered actuator dispatch: '+str(reason))
        goal=MoveToPose.Goal(request_id=registration.request_id,target=target,
                             motion_profile_id='demo_veryslow',deadline_ms=60000)
        self.calls+=1;self.terminal_known=False
        self.event('CONSTRAINED_DISPATCH',phase=phase,request_id=registration.request_id,
                   trajectory_sha256=hashlib.sha256(serialize_message(trajectory)).hexdigest(),
                   points=len(plan['positions']),duration_s=float(plan['times'][-1]),
                   tcp_start=plan['tcp_start'],tcp_end=plan['tcp_end'],pitch_start=plan['pitch_start'],
                   pitch_end=plan['pitch_end'],self_collision_samples=len(samples))
        try:send=self.action.send_goal_async(goal)
        except Exception as exc:self.unknown('actuator send failed with unknown acceptance: '+str(exc))
        handle=self.wait(send,15.,physical=True)
        if handle is None:self.unknown('empty goal response')
        if not handle.accepted:
            self.terminal_known=True;raise MotionFailed('constrained actuator goal rejected')
        future=handle.get_result_async();end=time.monotonic()+80.;stop_reason=None
        while not future.done() and time.monotonic()<end:
            try:
                self.pump(.02)
                reason='caller canceled' if self.canceled() else self.guard()
            except Exception as exc:
                reason='motion guard unavailable: '+str(exc)
            if reason and stop_reason is None:
                stop_reason=reason;handle.cancel_goal_async();end=min(end,time.monotonic()+18.)
                self.event('CONSTRAINED_CANCEL_SENT',reason=reason,phase=phase)
        if not future.done():self.unknown('accepted goal did not produce a terminal reply after bounded stop wait')
        wrapped=future.result()
        if wrapped is None or wrapped.status not in (4,5,6):self.unknown('unconfirmed action terminal status')
        result=wrapped.result;self.last_result=result
        self.any_execution_started=self.any_execution_started or bool(result.execution_started)
        if result.outcome==3 or result.error_code==33:self.unknown(result.detail)
        if wrapped.status in (5,6) and result.execution_started and not result.stop_confirmed:
            self.unknown('canceled/aborted motion has no strict stop confirmation')
        self.terminal_known=True
        self.event('CONSTRAINED_TERMINAL',phase=phase,action_status=wrapped.status,
                   outcome=int(result.outcome),error_code=int(result.error_code),
                   stop_confirmed=bool(result.stop_confirmed),execution_started=bool(result.execution_started),
                   evidence_id=result.evidence_id,detail=result.detail)
        if self.canceled():raise MotionCanceled('caller canceled; no cleanup motion dispatched')
        if stop_reason:raise MotionFailed('motion guard stopped path: '+str(stop_reason))
        if (wrapped.status!=4 or result.outcome!=0 or result.error_code!=0
                or not result.execution_started or not result.has_reached_pose
                or not math.isfinite(result.position_error_m)):
            raise MotionFailed('constrained executor failed: '+result.detail)
        self.pump(.05);qafter,gafter=self.state()
        actual=self.model.frames(qafter,gafter)['end_effector_link']
        if (np.linalg.norm(actual[:3,3]-endpoint[:3,3])>.0015
                or abs(float(sum(qafter[1:]))-pitch)>.015):
            raise MotionFailed('measured constrained endpoint violates local contact tracking guard')
        return result
