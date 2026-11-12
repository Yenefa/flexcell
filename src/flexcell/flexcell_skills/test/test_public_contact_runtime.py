"""Public input isolation and returned-state admission; not physical evidence."""
import copy
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace as NS
from unittest.mock import Mock

import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from runtime.planner.public_observation import reduce_to_public,LeakError
from runtime.planner.push_task import plan,PushTaskRejected
from flexcell_skills.contracts.composite import push_native_success
from flexcell_skills.contracts.contact_task import returned_component_ready


def inputs():
    task=reduce_to_public(json.loads((ROOT/'benchmark/tasks/t08_dev/T08-push-seed2000.json').read_text()))
    world=dict(source='SIMULATION_GROUND_TRUTH',header=dict(frame_id='world'),carry=dict(engaged=False),
        objects=[dict(name=o['name'],available=True,pose_age_s=.01,
            pose=dict(position=dict(zip(('x','y','z'),o['initial_pose'][:3])))) for o in task['objects']])
    return task,world,dict(push_backend='finger_tcp',motion_budget=40,wall_s=600.)


def test_public_goal_uses_live_geometry_and_instruction_not_task_answers():
    task,world,cap=inputs();recipe,goal,_=plan(task,world,cap)
    assert goal['target']=='target_box_a' and len(recipe['stages'])==2
    world['objects'][0]['pose']['position']['x']=.18
    changed,_,_=plan(task,world,cap)
    assert len(changed['stages'])==1 and changed['initial_objects']['target_box_a'][0]==.18
    assert task['objects'][0]['initial_pose'][0]==.22


def test_private_task_keys_are_rejected_before_planning():
    task,world,cap=inputs();task['expected_goal']={}
    with pytest.raises(LeakError):plan(task,world,cap)


def test_another_colour_identity_and_zone_are_not_hardcoded():
    task,world,cap=inputs()
    task['instruction']='Push the blue block into the marked zone. Do not move the red block.'
    world['objects'][1]['pose']['position'].update(x=.215,y=.01)
    task['zones'][0].update(name='other_goal',pose=[.115,.01,.0175])
    recipe,goal,_=plan(task,world,cap)
    assert goal['target']=='target_box_b' and goal['preserve']==['target_box_a']
    assert goal['zone']['name']=='other_goal' and all(s['object_name']=='target_box_b' for s in recipe['stages'])


@pytest.mark.parametrize('mutation',[lambda t,w,c:t['objects'].append(copy.deepcopy(t['objects'][0])),
    lambda t,w,c:t.update(instruction='Push the red block into the marked zone. Do not move the red block.'),
    lambda t,w,c:t['execution_budget'].update(max_steps=12),
    lambda t,w,c:t['zones'][0].update(pose=[.5,0.,.0175]),
    lambda t,w,c:w['objects'][0].update(pose_age_s=2.),
    lambda t,w,c:c.update(push_backend='unavailable')])
def test_ambiguous_unreachable_stale_or_overbudget_goals_refuse(mutation):
    task,world,cap=inputs();mutation(task,world,cap)
    with pytest.raises(PushTaskRejected):plan(task,world,cap)


def test_done_transport_future_exception_still_latches_unknown():
    from flexcell_skills.contact_motion import ConstrainedMotion,MotionUnknown
    motion=ConstrainedMotion.__new__(ConstrainedMotion);motion.blocked=False;motion.terminal_known=False
    motion.event=Mock();motion.pump=Mock();motion.action=Mock()
    future=Mock();future.done.return_value=True;future.result.side_effect=RuntimeError('lost acceptance reply')
    with pytest.raises(MotionUnknown):motion.wait(future,1.,physical=True)
    with pytest.raises(MotionUnknown):motion.execute({},'RETURN')
    motion.action.send_goal_async.assert_not_called()


@pytest.mark.parametrize('bad_field',[None,'arm_ready','return_completed','motion_terminal_known',
                                    'has_returned_state','physical_contact_observed','expired','wrong_uuid'])
def test_runtime_consumes_correlated_typed_return_instead_of_stroke_only(bad_field):
    from flexcell_interfaces.action import ContactPush
    from flexcell_interfaces.msg import WorldObject
    from flexcell_skills.task_fsm_server import TaskFsmServer
    from flexcell_skills.skill_lifecycle import MotionQuarantine
    server=TaskFsmServer.__new__(TaskFsmServer);server._contact_type=ContactPush
    server._contact_remaining=40;server._contact_wall=600.;server._cli_contact=Mock()
    server._motion_quarantine=MotionQuarantine();server._quarantine_skill=Mock()
    goal_uuid='a'*32;stage=dict(stage_id='one',object_name='red_id',direction=[-1.,0.,0.],distance_m=.03)
    recipe=dict(initial_objects={'red_id':[.22,0.,.0175],'blue_id':[.2,-.18,.0175]},motion_profile_id='demo_veryslow')
    def respond(cli,request,*args,**kwargs):
        assert list(request.preserve_objects)==['blue_id'] and request.max_motion_goals==13
        assert bytes(kwargs['goal_uuid'].uuid).hex()==goal_uuid
        r=ContactPush.Result();r.request_id=request.request_id;r.goal_uuid=goal_uuid
        r.receipt_json=json.dumps(dict(request_id=request.request_id));r.motion_goals_used=12
        r.evidence_id='synthetic-typed-return';r.displacement_m=.0305;r.direction_cos=1.
        r.contact_made=True;r.motion_terminal_known=True;r.return_completed=True;r.arm_ready=True
        r.has_returned_state=True;r.physical_contact_observed=True;r.observed_monotonic_ns=time.monotonic_ns()
        r.returned_state.source='SIMULATION_GROUND_TRUTH';r.returned_state.header.frame_id='world'
        r.returned_state.robot.has_gripper_state=True
        for name in recipe['initial_objects']:
            o=WorldObject();o.name=name;o.available=True;o.pose_age_s=.01;r.returned_state.objects.append(o)
        if bad_field=='expired':r.observed_monotonic_ns-=500_000_000
        elif bad_field=='wrong_uuid':r.goal_uuid='b'*32
        elif bad_field:setattr(r,bad_field,False)
        return r,None
    server._demo_call=respond
    value=server._native_contact_push(stage,goal_uuid,NS(run_id='parent'),NS(is_cancel_requested=False),
                                      time.monotonic(),recipe,[])
    assert server._contact_remaining==28
    if bad_field is None:
        assert returned_component_ready(value) and push_native_success(value,goal_uuid,.005,stage)
    else:
        assert not push_native_success(value,goal_uuid,.005,stage)


def test_registration_cannot_hide_changed_state_before_actual_send(monkeypatch):
    from flexcell_skills import contact_motion as module
    from flexcell_skills.contact_geometry import ContactGeometry
    monkeypatch.setattr(module,'ActionClient',Mock());node=Mock();node.create_client.side_effect=[Mock(),Mock()]
    q=np.zeros(4);model=ContactGeometry.__new__(ContactGeometry)
    motion=module.ConstrainedMotion(node,model,lambda:(q,(0.,0.)),lambda _:None,Mock(),lambda:False,
                                   Mock(side_effect=[None,'gripper changed']))
    future=Mock();future.done.return_value=True;future.result.return_value=NS(valid=True,success=True,detail='')
    motion.validity.call_async.return_value=future;motion.registration.call_async.return_value=future
    trajectory=dict(positions=np.array([q,q]),velocities=np.zeros((2,4)),accelerations=np.zeros((2,4)),
        times=np.array([0.,1.]),tcp_start=[0.,0.,0.],tcp_end=[0.,0.,0.],pitch_start=0.,pitch_end=0.)
    with pytest.raises(module.MotionFailed,match='gripper changed'):motion.execute(trajectory,'STROKE')
    motion.action.send_goal_async.assert_not_called()


def test_contact_transport_exception_preserves_arm_quarantine():
    from flexcell_interfaces.action import ContactPush
    from flexcell_skills.task_fsm_server import TaskFsmServer
    from flexcell_skills.skill_lifecycle import MotionQuarantine
    server=TaskFsmServer.__new__(TaskFsmServer);server._contact_type=ContactPush
    server._contact_remaining=40;server._contact_wall=600.;server._cli_contact=Mock()
    server._motion_quarantine=MotionQuarantine();server._publish_task_state=Mock();server.get_logger=Mock()
    server._demo_call=Mock(side_effect=RuntimeError('accepted result transport lost'))
    value=server._native_contact_push(dict(stage_id='one',object_name='red',direction=[-1.,0.,0.],distance_m=.03),
        'a'*32,NS(run_id='parent'),NS(is_cancel_requested=False),time.monotonic(),
        dict(initial_objects={'red':[.22,0.,.0175],'blue':[.2,-.18,.0175]},motion_profile_id='demo_veryslow'),[])
    assert server._quarantine.active and value['outcome']==3 and value['error_code']==33
    assert not push_native_success(value,'a'*32,.005,dict(distance_m=.03))
