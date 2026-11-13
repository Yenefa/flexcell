"""Opt-in ContactPush action backed by the measured finger-TCP engine."""
import json
import math
from pathlib import Path
import queue
import re
import threading
import time

import rclpy
from rclpy.action import ActionServer,CancelResponse,GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from std_srvs.srv import Trigger
from flexcell_interfaces.action import ContactPush
from flexcell_skills.contact_executor import execute_contact_push
from flexcell_capabilities.contact_geometry import ContactGeometry
from flexcell_capabilities.contact_trace import NativeContact
from flexcell_skills.contracts import push


def validate_request(request):
    if (not re.fullmatch(r'[A-Za-z0-9_-]{1,96}',request.request_id)
            or not request.object_name or len(request.object_name)>128
            or [request.direction.x,request.direction.y,request.direction.z]!=[-1.,0.,0.]
            or not math.isfinite(request.distance_m) or abs(request.distance_m-.03)>1e-12
            or request.motion_profile_id!='demo_veryslow'
            or request.deadline_ms>300000
            or request.max_motion_goals not in (0,*range(13,41))
            or len(request.preserve_objects)!=len(set(request.preserve_objects))):
        return 'unsupported goal; validated capability is one30mm world-x stroke'
    return None


def succeeded_return(value):
    return (isinstance(value,dict) and value.get('primitive_outcome')=='SUCCEEDED'
            and value.get('primitive_error_code')==0
            and value.get('motion_terminal_known') is True
            and value.get('return_completed') is True and value.get('arm_ready') is True
            and value.get('returned_request_geometry_satisfied') is True
            and value.get('physical_contact_observed') is True)


class ContactPushServer(Node):
    def __init__(self):
        super().__init__('contact_push_server',parameter_overrides=[Parameter('use_sim_time',value=False)])
        for name,value in [('model_directory','/artifacts/model'),('native_directory','/artifacts/current'),
                           ('evidence_directory','/artifacts/contact_goals'),
                           ('tracked_objects',['target_box_a','target_box_b'])]:
            self.declare_parameter(name,value)
        self.root=Path(self.get_parameter('evidence_directory').value);self.root.mkdir(parents=True,exist_ok=True)
        self._admission=threading.Lock();self._quarantined=False;self._ready=False
        self._queue=queue.Queue();self._shutdown=threading.Event();self._worker_error=None
        self._thread=threading.Thread(target=self._worker,name='contact_execution_owner',daemon=True)
        self._thread.start()
        group=ReentrantCallbackGroup()
        self._action=ActionServer(self,ContactPush,'/contact_push',self._execute,
            goal_callback=self._goal,cancel_callback=lambda _:CancelResponse.ACCEPT,callback_group=group)
        self._ready_service=self.create_service(Trigger,'/contact_push/ready',self._readiness,callback_group=group)

    def _goal(self,request):
        error=validate_request(request)
        if error or not self._ready or self._quarantined:return GoalResponse.REJECT
        if not self._admission.acquire(blocking=False):return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def _readiness(self,request,response):
        response.success=self._ready and not self._quarantined and not self._admission.locked()
        response.message=self._worker_error or ('QUARANTINED' if self._quarantined else 'ready' if response.success else 'busy/starting')
        return response

    def _worker(self):
        node=None
        try:
            # Do not inherit the coordinator's __node remap or wall-clock file.
            node=Node('contact_execution_worker',use_global_arguments=False,
                      parameter_overrides=[Parameter('use_sim_time',value=True)])
            directory=Path(self.get_parameter('model_directory').value)
            model=ContactGeometry(directory/'robot.urdf',directory)
            native=NativeContact(self.get_parameter('native_directory').value,
                                 self.get_parameter('tracked_objects').value[0],{})
            native.sim_clock=lambda:node.get_clock().now().nanoseconds
            self._ready=True
            while not self._shutdown.is_set():
                try:work=self._queue.get_nowait()
                except queue.Empty:
                    rclpy.spin_once(node,timeout_sec=.02);native.poll();continue
                handle,out,done,box,deadline=work
                try:
                    request=handle.request
                    box['execution']=execute_contact_push(node,model,native,out,request.request_id,
                        request.object_name,request.distance_m,list(request.preserve_objects),
                        lambda:handle.is_cancel_requested or time.monotonic()>=deadline,
                        min(13,request.max_motion_goals or 13))
                except Exception as exc:
                    self._quarantined=True;box['exception']=str(exc)
                finally:done.set()
        except Exception as exc:
            self._worker_error=type(exc).__name__+': '+str(exc);self._quarantined=True
        finally:
            self._ready=False
            if node is not None:node.destroy_node()

    def _execute(self,handle):
        request=handle.request;result=ContactPush.Result()
        result.outcome=1;result.error_code=2;result.stroke_outcome=255
        result.request_id=request.request_id;result.goal_uuid=bytes(handle.goal_id.uuid).hex()
        result.requested_distance_m=request.distance_m
        for field in ('stroke_displacement_m','stroke_along_m','displacement_m',
                      'displacement_along_direction_m','direction_cos','lateral_m','delta_z_m'):
            setattr(result,field,float('nan'))
        out=self.root/(request.request_id+'-'+result.goal_uuid[:8]);result.evidence_id=str(out)
        done=threading.Event();box={};deadline=time.monotonic()+(request.deadline_ms or 300000)/1000
        self._queue.put((handle,out,done,box,deadline))
        try:
            while not done.wait(.05):
                if not self._thread.is_alive():raise RuntimeError('execution owner terminated without a result')
            execution=box.get('execution')
            if execution is None:raise RuntimeError(box.get('exception','execution result unavailable'))
            result.motion_goals_used=execution['motion_goals'];result.execution_started=execution['execution_started']
            result.carry_engaged_during=execution['carry_engaged_during']
            result.motion_terminal_known=execution['terminal_known'];result.detail=execution.get('detail') or ''
            value=execution.get('receipt')
            if value:
                result.receipt_json=json.dumps(value,allow_nan=False)
                result.stroke_outcome={'SUCCEEDED':0,'FAILED':1,'CANCELED':2,'STATE_UNKNOWN':3,'NOT_EXECUTED':255}[value['primitive_outcome']]
                result.stroke_error_code=value['primitive_error_code']
                metrics=execution.get('stroke_metrics')
                if metrics:
                    result.stroke_displacement_m=float(metrics['displacement_m']);result.stroke_along_m=float(metrics['along_m'])
                    result.contact_made=metrics['displacement_m']>=push.DEFAULTS['contact_floor_m']
                result.physical_contact_known=value['physical_contact_observed'] is not None
                result.physical_contact_observed=value['physical_contact_observed'] is True
                result.contact_lost=False
                result.return_completed=value['return_completed'];result.arm_ready=value['arm_ready']
                result.has_returned_state=value['post_return'] is not None
                if result.has_returned_state:
                    result.returned_state=execution['current']['world_message']
                    result.observed_monotonic_ns=value['post_return']['observed_monotonic_ns']
                    before=execution['before'];current=execution['current']
                    before_obj=next(o for o in before['world_message'].objects if o.name==request.object_name)
                    after_obj=next(o for o in current['world_message'].objects if o.name==request.object_name)
                    result.measured_before=before_obj.pose;result.measured_after=after_obj.pose
                    metrics,_=push.contact_metrics(before['positions'][request.object_name],current['positions'][request.object_name],[-1.,0.,0.])
                    for field,key in [('displacement_m','displacement_m'),('displacement_along_direction_m','along_m'),
                                      ('direction_cos','direction_cos'),('lateral_m','lateral_m'),('delta_z_m','delta_z_m')]:
                        setattr(result,field,float(metrics[key]))
                if succeeded_return(value):result.outcome=0;result.error_code=0
                else:result.error_code=value['primitive_error_code'] or 30
            if not result.motion_terminal_known:
                result.outcome=3;result.error_code=33;self._quarantined=True
            elif handle.is_cancel_requested:
                result.outcome=2;result.error_code=32
            elif time.monotonic()>=deadline:
                result.outcome=1;result.error_code=30;result.detail='contact goal wall budget exhausted; '+result.detail
            last=execution.get('last_motion_result')
            result.stop_confirmed=result.motion_terminal_known and (
                not result.execution_started or result.return_completed or
                last is not None and bool(last.stop_confirmed))
            (out/'action_result.json').write_text(json.dumps(dict(outcome=result.outcome,error_code=result.error_code,
                request_id=result.request_id,goal_uuid=result.goal_uuid,arm_ready=result.arm_ready,
                return_completed=result.return_completed,motion_terminal_known=result.motion_terminal_known,
                motion_goals_used=result.motion_goals_used,detail=result.detail),indent=2))
        except Exception as exc:
            self._quarantined=True;result.outcome=3;result.error_code=33
            result.motion_terminal_known=False;result.detail='execution ownership/result unknown: '+str(exc)
        finally:
            if not self._quarantined:self._admission.release()
        if result.outcome==0:handle.succeed()
        elif result.outcome==2:handle.canceled()
        else:handle.abort()
        return result

    def close(self):
        self._shutdown.set();self._thread.join(timeout=3.)


def main(args=None):
    rclpy.init(args=args);node=ContactPushServer();executor=MultiThreadedExecutor(num_threads=3);executor.add_node(node)
    try:executor.spin()
    finally:
        node.close();executor.shutdown();node.destroy_node();rclpy.shutdown()
