#!/usr/bin/env python3
"""Isolated finger-TCP push with constrained paths and explicit returned-state receipts."""
import argparse
from collections import deque
import json
import math
from pathlib import Path
import signal
import time

import numpy as np
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSProfile,DurabilityPolicy
from rclpy.signals import SignalHandlerOptions
from rosidl_runtime_py.convert import message_to_ordereddict
from sensor_msgs.msg import JointState
from std_msgs.msg import String
from flexcell_interfaces.action import Observe
from flexcell_skills.contact_geometry import ARM,ContactGeometry,apply
from flexcell_skills.contact_motion import ConstrainedMotion,MotionCanceled,MotionFailed,MotionUnknown
from flexcell_skills.contact_receipt import ContactReceipt,ReturnedState
from flexcell_skills.contact_trace import NativeContact,fresh_joint_values
from flexcell_skills.contracts import push,push_recover


def angles(q):
    x,y,z,w=[q[k] for k in ('x','y','z','w')]
    return [math.atan2(2*(w*x+y*z),1-2*(x*x+y*y)),
            math.asin(max(-1.,min(1.,2*(w*y-z*x)))),
            math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task',type=Path);parser.add_argument('out',type=Path)
    parser.add_argument('--model',type=Path,default=Path('/artifacts/model'))
    parser.add_argument('--attempts',type=int,default=2)
    args=parser.parse_args()
    if not 1<=args.attempts<=3:parser.error('attempts must be within 1..3')
    spec=json.loads(args.task.read_text());goals=spec['expected_goal'].get('push',{})
    if len(goals)!=1:parser.error('this isolated adapter supports one push objective')
    target,goal=next(iter(goals.items()))
    if goal['direction']!=[-1.,0.]:parser.error('this registered adapter supports the declared -x task only')
    if any(o['size']!=[.035]*3 for o in spec['objects']):parser.error('only declared 35 mm boxes are supported')
    zone=next(z for z in spec['zones'] if z['name']==goal['zone'])
    declared={o['name']:o['initial_pose'][:3] for o in spec['objects']}
    protected={n:declared[n] for n in spec['constraints']['must_not_move']}
    args.out.mkdir(exist_ok=False)
    model=ContactGeometry(args.model/'robot.urdf',args.model)
    native=NativeContact(args.out.parent,target,protected)
    latest=[None,0.];history=deque(maxlen=200);joint_selection=[None]
    canceled=[False];phase=['IDLE'];registry=[None];expected_target=[None];receipts=[];snapshots=[0]
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:canceled.__setitem__(0,True))
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node=Node('constrained_finger_push',parameter_overrides=[Parameter('use_sim_time',value=True)])
    native.sim_clock=lambda:node.get_clock().now().nanoseconds
    observer=ActionClient(node,Observe,'/observe')
    publisher=node.create_publisher(String,'/flexcell/contact_push_receipt',
        QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
    stream=(args.out/'events.jsonl').open('x')
    def event(kind,**fields):
        missing=[]
        def portable(value,path=''):
            if isinstance(value,float) and not math.isfinite(value):missing.append(path);return None
            if isinstance(value,dict):return {k:portable(v,path+'.'+k) for k,v in value.items()}
            if isinstance(value,(list,tuple)):return [portable(v,path+'[%d]'%i) for i,v in enumerate(value)]
            return value
        fields=portable(fields)
        stream.write(json.dumps(dict(kind=kind,monotonic_ns=time.monotonic_ns(),sim_ns=node.get_clock().now().nanoseconds,
                                     joint_selection=joint_selection[0],unavailable_numeric_fields=missing,**fields),allow_nan=False)+'\n');stream.flush()
    def joints(msg):
        latest[:]=[msg,time.monotonic()];history.append(tuple(latest))
    subscription=node.create_subscription(JointState,'/joint_states',joints,100)
    def pump(timeout=.02):
        rclpy.spin_once(node,timeout_sec=timeout);native.poll()
    def state():
        end=time.monotonic()+3
        while time.monotonic()<end:
            if native.fresh():
                selected=fresh_joint_values(history,native.matched_physics['sim_ns'],time.monotonic())
                if selected is not None:
                    q,g,metadata=selected;joint_selection[0]=metadata
                    return q,g
            pump(.02)
        raise MotionFailed('fresh complete measured joints unavailable')
    def quiet():
        end=time.monotonic()+10.;since=None;stamp=None
        while time.monotonic()<end:
            pump(.03)
            if canceled[0]:raise MotionCanceled('caller canceled while settling')
            msg,received=latest
            if msg is not None and push_recover.arm_quiet(list(msg.name),list(msg.velocity),time.monotonic()-received):
                current=(msg.header.stamp.sec,msg.header.stamp.nanosec)
                if since is None:since,stamp=time.monotonic(),current
                if time.monotonic()-since>=.2 and current!=stamp:return
            else:since=None
        raise MotionFailed('arm settling unconfirmed')
    def motion_guard(check_joint_frame=True):
        if not native.fresh():return native.error or 'native source unavailable: '+json.dumps(native.freshness_info())
        if native.protected_peak>.005:return 'protected motion guard'
        if phase[0] in ('HOVER','APPROACH','RETURN') and expected_target[0] is not None:
            actual=native.latest['targets'][target].get('pose')
            if actual is None or math.dist(actual[:3],expected_target[0])>.001:
                return 'target changed during constrained planning'
        if check_joint_frame and registry[0] is not None:
            _,g=state()
            if max(abs(a-b) for a,b in zip(g,registry[0]['gripper_positions']))>.001:
                return 'registered finger frame changed'
        if phase[0] in ('HOVER','APPROACH','RETURN') and native.steps:return 'unplanned target contact outside stroke/unload'
        if phase[0]=='STROKE':return native.guard()
        return None
    motion=ConstrainedMotion(node,model,state,pump,event,lambda:canceled[0],motion_guard)
    def observe():
        quiet()
        if not observer.wait_for_server(timeout_sec=5.):raise MotionFailed('Observe unavailable')
        request=Observe.Goal();request.refresh=True;request.max_age_s=.5
        handle=motion.wait(observer.send_goal_async(request),15.)
        if handle is None or not handle.accepted:raise MotionFailed('Observe rejected')
        wrapped=motion.wait(handle.get_result_async(),20.);res=wrapped.result
        if wrapped.status!=4 or res.outcome!=0 or res.error_code!=0:raise MotionFailed('canonical Observe failed')
        world=message_to_ordereddict(res.world_state)
        if (world['source']!='SIMULATION_GROUND_TRUTH' or world['header']['frame_id']!='world'
                or world['carry']['engaged'] or not world['robot']['has_gripper_state']
                or any(n.startswith('ee: lookup failed') for n in world['notes'])):
            raise MotionFailed('canonical robot/carry/world state unusable')
        positions={};attitudes={};age=0.
        for obj in world['objects']:
            if not obj['available'] or not 0<=obj['pose_age_s']<=.5:raise MotionFailed('object unavailable/stale')
            p=obj['pose']['position'];positions[obj['name']]=[p['x'],p['y'],p['z']]
            attitudes[obj['name']]=angles(obj['pose']['orientation']);age=max(age,obj['pose_age_s'])
        if any(n not in positions for n in declared):raise MotionFailed('declared object missing')
        stamp=world['header']['stamp']['sec']+world['header']['stamp']['nanosec']/1e9
        age=max(age,node.get_clock().now().nanoseconds/1e9-stamp)
        if not 0<=age<=.5:raise MotionFailed('canonical source stamp stale')
        q,g=state();frame=model.frames(q,g)['end_effector_link'];p=world['robot']['ee_pose']['position']
        if np.linalg.norm(frame[:3,3]-[p['x'],p['y'],p['z']])>.0015:
            raise MotionFailed('pinned FK disagrees with independently composed EE pose')
        index=snapshots[0];snapshots[0]+=1
        (args.out/('state_%03d.json'%index)).write_text(json.dumps(world,allow_nan=False))
        event('CANONICAL_OBSERVATION',index=index,revision=world['revision'],target=positions[target])
        return dict(world=world,positions=positions,attitudes=attitudes,age=float(age),stamp=stamp,
                    source_stamp_ns=world['header']['stamp']['sec']*10**9+world['header']['stamp']['nanosec'],
                    observed_monotonic_ns=time.monotonic_ns())
    def move(tcp,end,pitch,label,avoid=None):
        if canceled[0]:raise MotionCanceled('caller canceled before planning')
        phase[0]=label;expected_target[0]=avoid;q,g=state()
        if registry[0] is not None and max(abs(a-b) for a,b in zip(g,registry[0]['gripper_positions']))>.001:
            raise MotionFailed('gripper state changed; registered finger frame unavailable')
        def planning_guard():
            if native.error:return native.error
            # Math owns no actuator. Temporarily unavailable input can wait
            # until computation completes; execute() then requires fresh scene,
            # joints, unchanged target/gripper and matching measured start.
            # Known scene violations are still latched while data is available.
            if not native.fresh():return None
            return motion_guard(check_joint_frame=False)
        plan=motion.plan_observed(lambda:model.cartesian(q,tcp,end,pitch,list(protected.values()),g,avoid_target=avoid),
                                  guard=planning_guard)
        np.savez_compressed(args.out/('plan_%02d.npz'%motion.calls),**{k:v for k,v in plan.items() if isinstance(v,np.ndarray)})
        motion.execute(plan,label)
    status='STATE_UNAVAILABLE';detail=None;goal_reached=False
    try:
        current=observe()
        if any(math.dist(current['positions'][n],p)>.001 for n,p in declared.items()):
            raise MotionFailed('initial scene differs from declared task')
        for attempt in range(args.attempts):
            decision,payload=push_recover.measured_next_request(declared[target],current['positions'][target],goal,zone,
                args.attempts-attempt,protected_motion_m=native.protected_peak)
            event('DECISION',decision=decision,**payload)
            if decision!='push':
                status=decision.upper();detail=payload;goal_reached=decision=='goal_geometry_reached';break
            if motion.calls>25:status='BUDGET_EXHAUSTED';break
            before=current;start=tuple(before['positions'][target]);requested=float(payload['distance_m'])
            error_code=2;outcome='NOT_EXECUTED';signed=None;post=None;returned=False;physical=None;contact_data={};stroke_classified=False
            try:
                if any(abs(v)>.04 for v in current['attitudes'][target]):
                    raise MotionFailed('object attitude outside registered upright calibration')
                q,g=state();reg=model.register_finger(start,list(protected.values()),g);registry[0]=reg
                (args.out/('contact_frame_%02d.json'%attempt)).write_text(json.dumps(reg,indent=2))
                tcp=reg['tcp'];native.begin(reg)
                hover=list(reg['support_world']['point']);hover[2]=.115
                move(tcp,hover,.5,'HOVER',start)
                move(tcp,reg['support_world']['point'],reg['pitch_rad'],'APPROACH',start)
                current=observe()
                if math.dist(current['positions'][target],start)>.001:
                    raise MotionFailed('approach displaced the object before the registered stroke')
                q,g=state();line_start=apply(model.frames(q,g)['end_effector_link'],np.asarray(tcp))
                native.begin(reg)
                for index in range(1,10):
                    travel=min(index*.004,requested+.005)
                    endpoint=line_start+[-travel,0.,0.]
                    move(tcp,endpoint,reg['pitch_rad'],'STROKE')
                    current=observe()
                    metrics,_=push.contact_metrics(list(start),current['positions'][target],[-1.,0.,0.])
                    signed=float(metrics['along_m']);event('MEASURED_STROKE',index=index,**metrics)
                    if signed<-.001:raise MotionFailed('object moved against the registered stroke')
                    if index>=2 and signed<.001:raise MotionFailed('registered stroke did not establish progress')
                    if signed>=requested or travel>=requested+.005:break
                contact_data=native.summary();physical=contact_data['physical_contact_observed'];native.end()
                verdict=push.judge(metrics,dict(distance_m=requested,contact_height_m=float(model.frames(state()[0])['end_effector_link'][2,3])),
                    push.DEFAULTS,travel,0.,0,False,index)
                outcome=push.outcome_name(verdict['outcome']);error_code=int(verdict['error_code'])
                if physical is not True or contact_data['source_problem'] or motion_guard():
                    raise MotionFailed('registered native contact model was not confirmed')
                stroke_classified=True
                event('STROKE_VERDICT',verdict=verdict,native_contact=contact_data)
                native.begin(reg);q,g=state();now=apply(model.frames(q,g)['end_effector_link'],np.asarray(tcp))
                move(tcp,now+[.003,0.,0.],reg['pitch_rad'],'UNLOAD')
                current=observe();q,g=state();now=apply(model.frames(q,g)['end_effector_link'],np.asarray(tcp));now[2]=.115
                native.begin(reg)
                move(tcp,now,.5,'RETURN',current['positions'][target]);native.end()
                settled=observe();end=time.monotonic()+12.
                while True:
                    next_state=observe()
                    if (next_state['stamp']-settled['stamp']>=.1
                            and math.dist(next_state['positions'][target],settled['positions'][target])<=.0005):
                        current=next_state;break
                    if time.monotonic()>end:raise MotionFailed('object did not provide a stable post-return window')
                    settled=next_state
                q,g=state();tool=model.world_meshes(q,g,tool_only=True)
                clearance=min(float(t[:,:,2].min()) for t in tool.values())
                post=ReturnedState(current['world']['source'],'world',current['age'],True,True,True,True,
                                   clearance,native.protected_peak,tuple(current['positions'][target]),int(current['world']['revision']),
                                   current['source_stamp_ns'],current['observed_monotonic_ns'])
                returned=True
            except MotionCanceled as exc:
                if not stroke_classified:outcome,error_code='CANCELED',32
                detail=str(exc)
            except MotionUnknown as exc:
                if not stroke_classified:outcome,error_code='STATE_UNKNOWN',33
                detail=str(exc)
            except Exception as exc:
                if not stroke_classified:outcome,error_code='FAILED',30
                detail=type(exc).__name__+': '+str(exc)
            finally:
                if physical is None:physical=native.observed()
                contact_data=contact_data or native.summary();native.end()
                receipt=ContactReceipt('contact-%02d'%attempt,outcome,error_code,signed,requested,physical,
                    motion.terminal_known,returned,canceled[0],post,start)
                value=receipt.to_dict();value['native_contact']=contact_data;value['detail']=detail
                (args.out/('receipt_%02d.json'%attempt)).write_text(json.dumps(value,indent=2,allow_nan=False))
                publisher.publish(String(data=json.dumps(value,allow_nan=False)));receipts.append(value)
                event('POST_RETURN_RECEIPT',receipt=value)
            if not receipt.arm_ready:
                status=('CANCELED' if canceled[0] else 'STATE_UNKNOWN' if not motion.terminal_known
                        else 'RETURN_FAILED' if stroke_classified else outcome)
                break
            if outcome!='SUCCEEDED':status='PRIMITIVE_FAILED';break
        else:status='BUDGET_EXHAUSTED'
        if receipts and receipts[-1]['arm_ready']:
            decision,payload=push_recover.measured_next_request(declared[target],current['positions'][target],goal,zone,0,
                                                               protected_motion_m=native.protected_peak)
            goal_reached=decision=='goal_geometry_reached'
            if goal_reached and status!='PRIMITIVE_FAILED':status=decision.upper()
    except Exception as exc:
        status='STATE_UNAVAILABLE';detail=type(exc).__name__+': '+str(exc)
    finally:
        summary=dict(kind='CONSTRAINED_FINGER_PUSH',status=status,detail=detail,attempts=len(receipts),
                     goal_geometry_reached=goal_reached,
                     actuator_goals=motion.calls,independent_acceptance_claim=False,
                     motion_terminal_known=motion.terminal_known)
        (args.out/'contact_summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False))
        event('FINISHED',summary=summary);stream.close();node.destroy_node();rclpy.shutdown()
    print(json.dumps(summary));return 0 if status in ('GOAL_GEOMETRY_REACHED','BUDGET_EXHAUSTED','PRIMITIVE_FAILED') else 2


if __name__=='__main__':raise SystemExit(main())
