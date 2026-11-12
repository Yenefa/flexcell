"""Synthetic real-ROS handoff/cancel protocol checks; no physical evidence."""
import json
import argparse
from pathlib import Path
import threading
import time

import numpy as np
import rclpy
from rclpy.action import ActionServer,CancelResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from flexcell_interfaces.action import MoveToPose
from flexcell_interfaces.srv import RegisterMtcTrajectory
from moveit_msgs.srv import GetStateValidity
from flexcell_skills.contact_geometry import ContactGeometry
from flexcell_skills.contact_motion import ConstrainedMotion,MotionFailed,MotionUnknown,MotionCanceled


class Fixture(Node):
    def __init__(self):
        super().__init__('SYNTHETIC_contact_protocol_fixture')
        self.q=np.zeros(4);self.mode='success';self.valid=True;self.registered=None;self.goals=0
        group=ReentrantCallbackGroup()
        self.check=self.create_service(GetStateValidity,'/check_state_validity',self.check_state,callback_group=group)
        self.register=self.create_service(RegisterMtcTrajectory,'/flexcell/attached_point/register_trajectory',self.reg,callback_group=group)
        self.server=ActionServer(self,MoveToPose,'/move_to_pose',self.execute,callback_group=group,
                                 cancel_callback=lambda _:CancelResponse.ACCEPT)
    def check_state(self,request,response):response.valid=self.valid;return response
    def reg(self,request,response):self.registered=request;response.success=True;return response
    def execute(self,handle):
        self.goals+=1
        assert self.registered.request_id==handle.request.request_id
        result=MoveToPose.Result()
        if self.mode=='slow':
            end=time.monotonic()+5
            while not handle.is_cancel_requested and time.monotonic()<end:time.sleep(.01)
            result.execution_started=True;result.stop_confirmed=True;result.preempted=True
            result.outcome=2;result.error_code=32;handle.canceled();return result
        self.q=np.array(self.registered.trajectory.joint_trajectory.points[-1].positions)
        if self.mode=='default':handle.succeed();return result
        result.execution_started=True;result.has_reached_pose=True;result.position_error_m=0.
        if self.mode=='unknown':result.outcome=3;result.error_code=33;handle.abort()
        else:handle.succeed()
        return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=Path('/artifacts/protocol_checks'))
    out=parser.parse_args().out;out.mkdir(exist_ok=False)
    rclpy.init();fixture=Fixture();executor=MultiThreadedExecutor(num_threads=4);executor.add_node(fixture)
    thread=threading.Thread(target=executor.spin);thread.start();node=Node('synthetic_contact_client')
    model=ContactGeometry.__new__(ContactGeometry)
    def plan():
        start=fixture.q.copy();end=start+np.array([.01,.01,.01,.01])
        return dict(positions=np.array([start,end]),velocities=np.zeros((2,4)),accelerations=np.zeros((2,4)),
                    times=np.array([0.,1.]),tcp_start=model.frames(start)['end_effector_link'][:3,3].tolist(),
                    tcp_end=model.frames(end)['end_effector_link'][:3,3].tolist(),pitch_start=float(sum(start[1:])),pitch_end=float(sum(end[1:])))
    canceled=[False];events=[]
    def client():
        return ConstrainedMotion(node,model,lambda:(fixture.q.copy(),(0.,0.)),
            lambda t:rclpy.spin_once(node,timeout_sec=t),lambda kind,**fields:events.append(dict(kind=kind,**fields)),lambda:canceled[0])
    checks=dict(kind='SYNTHETIC_REAL_ROS_PROTOCOL',physical_evidence=False)
    try:
        motion=client()
        assert motion.validity.wait_for_service(timeout_sec=5.)
        response=motion.validity.call_async(GetStateValidity.Request())
        def read_only_planning():
            end=time.monotonic()+3.
            while not response.done() and time.monotonic()<end:time.sleep(.01)
            assert response.done() and response.result().valid
            return plan()
        planned=motion.plan_observed(read_only_planning)
        checks['read_only_planning_keeps_ros_service_callbacks_alive']='PASS'
        motion.execute(planned,'STROKE')
        assert fixture.goals==1 and motion.terminal_known
        checks['typed_trajectory_handoff']='PASS'
        motion=client();motion.guard=lambda:'scene telemetry unavailable'
        planned=motion.plan_observed(plan,guard=lambda:None);before=fixture.goals
        registered_before=fixture.registered.request_id
        try:motion.execute(planned,'RETURN')
        except MotionFailed:pass
        else:raise AssertionError('read-only plan bypassed the fresh scene gate')
        assert fixture.goals==before and fixture.registered.request_id==registered_before
        checks['stale_scene_after_readonly_plan_dispatches_no_goal']='PASS'
        fixture.valid=False;before=fixture.goals
        try:client().execute(plan(),'STROKE')
        except MotionFailed:pass
        else:raise AssertionError('self collision did not refuse')
        assert fixture.goals==before;fixture.valid=True;checks['collision_refusal_dispatches_no_goal']='PASS'
        fixture.mode='unknown';motion=client()
        try:motion.execute(plan(),'STROKE')
        except MotionUnknown:pass
        else:raise AssertionError('unknown terminal accepted')
        before=fixture.goals
        try:motion.execute(plan(),'RETURN')
        except MotionUnknown:pass
        else:raise AssertionError('cleanup allowed after unknown terminal')
        assert fixture.goals==before;checks['unknown_terminal_blocks_cleanup']='PASS'
        fixture.mode='default'
        try:client().execute(plan(),'STROKE')
        except MotionFailed:pass
        else:raise AssertionError('default success without measured fields accepted')
        checks['default_result_cannot_masquerade_as_motion_success']='PASS'
        fixture.mode='slow';motion=client();timer=threading.Timer(1.,lambda:canceled.__setitem__(0,True));timer.start()
        try:motion.execute(plan(),'STROKE')
        except MotionCanceled:pass
        else:raise AssertionError('cancel was not propagated')
        timer.join();before=fixture.goals
        try:motion.execute(plan(),'RETURN')
        except MotionCanceled:pass
        else:raise AssertionError('new motion after caller cancel')
        assert fixture.goals==before;checks['cancel_propagates_and_blocks_next_goal']='PASS'
    finally:
        executor.shutdown(timeout_sec=3.);thread.join(timeout=3.);fixture.destroy_node();node.destroy_node();rclpy.shutdown()
        (out/'checks.json').write_text(json.dumps(checks,indent=2));(out/'events.json').write_text(json.dumps(events,indent=2))
    print(json.dumps(checks))


if __name__=='__main__':main()
