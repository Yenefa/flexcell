#!/usr/bin/env python3
"""Public instruction -> live observation -> Runtime RunComposite -> task claim."""
import argparse
import hashlib
import json
from pathlib import Path
import signal
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from runtime.planner.public_observation import assert_public
from runtime.planner.push_task import plan,goal_satisfied


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('public_task',type=Path);parser.add_argument('out',type=Path)
    parser.add_argument('--backend',choices=('legacy','finger_tcp'),default='finger_tcp')
    args=parser.parse_args();public=json.loads(args.public_task.read_text());assert_public(public)
    args.out.mkdir(exist_ok=False);opened=[]
    def audit(event,fields):
        if event!='open' or not fields or not isinstance(fields[0],(str,bytes)):return
        path=str(fields[0]).replace('\\','/')
        if '/benchmark/tasks/' in path or '/benchmark/evaluators/' in path or '/benchmark/held_out/' in path:
            raise PermissionError('Runtime may not open private task/evaluation paths')
        if path.startswith(('/candidate/','/opt/flexcell/repo/')):opened.append(path)
    sys.addaudithook(audit)
    import rclpy
    from rclpy.action import ActionClient
    from rclpy.node import Node
    from rcl_interfaces.srv import GetParameters
    from std_srvs.srv import Trigger
    from rosidl_runtime_py.convert import message_to_ordereddict
    from flexcell_interfaces.action import Observe,RunComposite
    from flexcell_interfaces.msg import CompositeStage,ObjectPosition
    rclpy.init();node=Node('public_push_task_runtime')
    canceled=[False]
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:canceled.__setitem__(0,True))
    observer=ActionClient(node,Observe,'/observe');runtime=ActionClient(node,RunComposite,'/run_composite')
    started=time.monotonic();wall=float(public['execution_budget']['max_wall_s']);active=None
    task_sent=False;task_terminal=False
    result=dict(kind='PUBLIC_TASK_RUNTIME',agent_claimed_success=False,status='FAILED',model_calls=0)
    def wait(future,timeout):
        end=min(started+wall,time.monotonic()+timeout)
        while not future.done() and time.monotonic()<end:rclpy.spin_once(node,timeout_sec=.02)
        if not future.done():raise TimeoutError('read-only/goal-admission response timeout')
        return future.result()
    def observe(label):
        if not observer.wait_for_server(timeout_sec=10.):raise RuntimeError('Observe unavailable')
        goal=Observe.Goal();goal.refresh=True;goal.max_age_s=.5
        handle=wait(observer.send_goal_async(goal),15.)
        if handle is None or not handle.accepted:raise RuntimeError('Observe rejected')
        wrapped=wait(handle.get_result_async(),20.);reply=wrapped.result
        if wrapped.status!=4 or reply.outcome!=0 or reply.error_code!=0:raise RuntimeError('Observe failed')
        world=message_to_ordereddict(reply.world_state)
        (args.out/(label+'.json')).write_text(json.dumps(world))
        return world
    try:
        params=node.create_client(GetParameters,'/task_fsm_server/get_parameters')
        if not params.wait_for_service(timeout_sec=15.) or not runtime.wait_for_server(timeout_sec=15.):
            raise RuntimeError('Runtime task executor unavailable')
        request=GetParameters.Request();request.names=['push_backend','contact_task_motion_budget','contact_task_wall_s']
        values=wait(params.call_async(request),5.).values
        capabilities=dict(push_backend=values[0].string_value,motion_budget=values[1].integer_value,wall_s=values[2].double_value)
        if capabilities['push_backend']!=args.backend:raise RuntimeError('registered executor backend differs from requested experiment')
        if args.backend=='finger_tcp':
            ready=node.create_client(Trigger,'/contact_push/ready')
            if not ready.wait_for_service(timeout_sec=15.) or not wait(ready.call_async(Trigger.Request()),5.).success:
                raise RuntimeError('registered ContactPush execution owner is unavailable')
        initial=observe('initial_world');recipe,goal,budget=plan(public,initial,capabilities)
        wall=budget['max_wall_s']
        public_bytes=json.dumps(public,sort_keys=True,separators=(',',':')).encode()
        (args.out/'decision.json').write_text(json.dumps(dict(policy='public_push_rule_v1',
            public_input_sha256=hashlib.sha256(public_bytes).hexdigest(),capabilities=capabilities,
            semantic_goal=goal,budget=budget,plan=recipe),indent=2))
        wire=RunComposite.Goal();wire.scenario_id=recipe['scenario_id'];wire.motion_profile_id=recipe['motion_profile_id']
        wire.position_tolerance_m=recipe['position_tolerance_m'];wire.clearance_m=recipe['clearance_m']
        for name,position in recipe['initial_objects'].items():
            obj=ObjectPosition();obj.object_name=name;obj.position.x,obj.position.y,obj.position.z=position;wire.initial_objects.append(obj)
        for entry in recipe['stages']:
            stage=CompositeStage();stage.stage_id=entry['stage_id'];stage.object_name=entry['object_name'];stage.action=entry['action']
            stage.push_direction.x,stage.push_direction.y,stage.push_direction.z=entry['direction'];stage.push_distance_m=entry['distance_m']
            stage.contact_height_m=float('nan');stage.overdrive_m=float('nan');wire.stages.append(stage)
        send=runtime.send_goal_async(wire);task_sent=True
        active=wait(send,15.)
        if active is None or not active.accepted:
            task_terminal=True;raise RuntimeError('Runtime task rejected')
        future=active.get_result_async();cancel_sent=False
        while not future.done():
            rclpy.spin_once(node,timeout_sec=.02)
            if (canceled[0] or time.monotonic()-started>=wall) and not cancel_sent:
                active.cancel_goal_async();cancel_sent=True;stop_end=time.monotonic()+22.
            if cancel_sent and time.monotonic()>stop_end:
                result['status']='STATE_UNKNOWN';raise RuntimeError('Runtime stop unconfirmed; no next goal/cleanup')
        wrapped=future.result();reply=wrapped.result;task_terminal=True
        result.update(runtime_result=message_to_ordereddict(reply),runtime_action_status=wrapped.status,
                      runtime_goal_uuid=bytes(active.goal_id.uuid).hex())
        if wrapped.status==4 and reply.outcome==0 and not cancel_sent:
            final=observe('final_world');ok=goal_satisfied(goal,recipe['initial_objects'],final)
            result.update(agent_claimed_success=ok,status='TASK_COMPLETED' if ok else 'PUBLIC_POSTCONDITION_FAILED')
        else:result['status']='RUNTIME_TASK_FAILED'
    except Exception as exc:
        result['detail']=type(exc).__name__+': '+str(exc)
        if task_sent and not task_terminal:
            result['status']='STATE_UNKNOWN'
            if active is not None and active.accepted:
                try:active.cancel_goal_async()
                except Exception:pass
    finally:
        result['wall_s']=time.monotonic()-started
        (args.out/'runtime_result.json').write_text(json.dumps(result,indent=2,allow_nan=False))
        (args.out/'opened_source_paths.json').write_text(json.dumps(sorted(set(opened)),indent=2))
        node.destroy_node();rclpy.shutdown()
    print(json.dumps(result));return 0 if result['agent_claimed_success'] else 2


if __name__=='__main__':raise SystemExit(main())
