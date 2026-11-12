"""Contact geometry, native evidence and post-return refusal invariants."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock
import json
import math
import time
import threading

import numpy as np
import pytest

from flexcell_skills.contact_geometry import ContactGeometry,clip,box_intersects,apply
from flexcell_skills.contact_receipt import ContactReceipt,ReturnedState,ready_for_next
from flexcell_skills.contact_trace import JsonTail,NativeContact,patch_distance,fresh_joint_values


def arm():
    model=ContactGeometry.__new__(ContactGeometry)
    model.limits=[(-math.pi,math.pi),(-1.5,1.5),(-1.5,1.4),(-1.7,1.97)]
    return model


def test_fk_matches_archived_independent_tf_composition():
    references=json.loads((Path(__file__).parent/'data/contact_reference_states.json').read_text())
    model=arm()
    for row in references:
        pose=model.frames(row['joints'])['end_effector_link']
        assert np.linalg.norm(pose[:3,3]-row['ee_position'])<.001


def test_fixed_pitch_ik_preserves_the_measured_configuration_branch():
    model=arm()
    for q in [[0.,0.,0.,0.],[-.1,.8,-.95,1.63],[.2,.4,-.3,1.0]]:
        point=model.frames(q)['end_effector_link'][:3,3]
        solved=model.inverse(point,sum(q[1:]),q)
        assert np.max(np.abs(solved-q))<1e-7


def test_lateral_finger_tcp_is_not_the_virtual_end_effector_origin():
    model=arm();q=[-.1,.8,-.95,1.63];tcp=[-.013,.0216,-.0157]
    pose=model.frames(q)['end_effector_link'];point=apply(pose,tcp)
    recovered=model.tcp_inverse(point,sum(q[1:]),tcp,q)
    assert np.max(np.abs(recovered-q))<1e-7
    assert np.linalg.norm(point-pose[:3,3])>.02


def test_unreachable_fixed_orientation_is_refused_instead_of_relaxed():
    with pytest.raises(ValueError,match='unreachable'):
        arm().inverse([.6,0.,.1],math.pi/2,[0.]*4)


def test_real_triangle_distance_refuses_an_invented_bounding_box_corner():
    triangle=[[[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]]]
    assert patch_distance([.2,.2,.001],triangle)==pytest.approx(.001)
    assert patch_distance([1.,1.,0.],triangle)==pytest.approx(math.sqrt(.5))
    assert patch_distance([2.,0.,0.],triangle)==pytest.approx(1.)


def test_clipped_surface_points_stay_on_the_actual_triangle():
    tri=np.array([[0.,-2.,0.],[0.,2.,0.],[0.,0.,2.]])
    poly=clip(clip(list(tri),1,-.5,True),1,.5,False)
    for point in poly:assert patch_distance(point,[tri])<1e-12


def test_collision_detection_catches_edges_when_all_vertices_are_outside():
    tri=np.array([[[-2.,0.,0.],[2.,0.,0.],[0.,2.,0.]]])
    assert box_intersects(tri,[0.,0.,0.],.1)
    tri=np.array([[[.2,0.,0.],[0.,.2,0.],[.2,.2,0.]]])
    assert not box_intersects(tri,[0.,0.,0.],.05)


def returned():
    return ReturnedState('SIMULATION_GROUND_TRUTH','world',.01,True,True,True,True,.08,0.,(.19,0.,.0175),5,
                         10_000_000_000,time.monotonic_ns())


def receipt(post=None,**fields):
    values=dict(request_id='one',primitive_outcome='SUCCEEDED',primitive_error_code=0,stroke_signed_m=.03,
        requested_m=.03,physical_contact_observed=True,motion_terminal_known=True,return_completed=True,
        canceled=False,post_return=post or returned(),attempt_start=(.22,0.,.0175))
    values.update(fields);return ContactReceipt(**values)


def test_returned_receipt_keeps_motion_readiness_separate_from_task_acceptance():
    r=receipt();value=r.to_dict()
    assert r.arm_ready and value['returned_request_geometry_satisfied']
    assert value['independent_acceptance_claim'] is False


@pytest.mark.parametrize('patch',[dict(source_age_s=.6),dict(arm_quiet=False),dict(object_stable=False),
    dict(carry_disengaged=False),dict(gripper_state_known=False),dict(tool_clearance_m=.04),
    dict(protected_excursion_m=.006),dict(source='UNKNOWN')])
def test_missing_or_unsafe_post_state_cannot_become_ready(patch):
    r=receipt(replace(returned(),**patch))
    assert not r.arm_ready
    assert r.to_dict()['returned_request_geometry_satisfied'] is None


def test_pre_return_stroke_success_does_not_hide_lost_progress():
    r=receipt(replace(returned(),position=(.23,0.,.0175)))
    value=r.to_dict()
    assert r.arm_ready  # physically safe to reconsider the task, not a successful push
    assert value['returned_signed_m']==pytest.approx(-.01)
    assert value['return_loss_m']==pytest.approx(.04)
    assert value['progress_preserved'] is False and value['returned_request_geometry_satisfied'] is False


def test_returned_distance_cannot_hide_an_off_axis_motion():
    r=receipt(replace(returned(),position=(.19,.019,.0175)))
    assert r.arm_ready
    assert r.to_dict()['returned_request_geometry_satisfied'] is False


@pytest.mark.parametrize('patch',[dict(motion_terminal_known=False),dict(return_completed=False),dict(canceled=True)])
def test_unknown_motion_or_incomplete_return_never_dispatches_as_ready(patch):
    assert not receipt(**patch).arm_ready


def test_success_cannot_use_a_missing_physical_contact_observation():
    with pytest.raises(ValueError):receipt(physical_contact_observed=None)


def test_latched_ready_requires_current_clock_and_world_revision():
    value=receipt().to_dict();post=value['post_return']
    assert ready_for_next(value,post['source_stamp_ns'],5,post['observed_monotonic_ns'])
    assert not ready_for_next(value,post['source_stamp_ns'],6,post['observed_monotonic_ns'])
    assert not ready_for_next(value,post['source_stamp_ns']+600_000_000,5,post['observed_monotonic_ns'])
    assert not ready_for_next(value,post['source_stamp_ns'],5,post['observed_monotonic_ns']+300_000_000)


def test_json_tail_does_not_treat_a_partial_native_record_as_no_contact(tmp_path):
    path=tmp_path/'stream';path.write_text('{"x"');tail=JsonTail(path)
    assert tail.read()==[]
    with path.open('a') as f:f.write(':1}\n')
    assert tail.read()==[{'x':1}]


def test_absent_native_files_remain_unknown(tmp_path):
    native=NativeContact(tmp_path,'a',{})
    native.poll();assert native.observed() is None


def test_paused_physics_is_distinct_from_clock_advancing_without_telemetry(tmp_path):
    native=NativeContact(tmp_path,'a',{});now=time.monotonic_ns()
    native.latest=dict(monotonic_ns=now-500_000_000,sim_ns=10_000_000_000,
                       targets={'a':dict(component_present=True)})
    native.latest_physics=dict(monotonic_ns=now-500_000_000,sim_ns=10_000_000_000)
    native.matched_physics=native.latest_physics
    native.sim_clock=lambda:10_000_000_000
    assert native.fresh()
    native.sim_clock=lambda:9_990_000_000  # /clock transport can lag native ECM.
    assert native.fresh()
    native.sim_clock=lambda:9_955_000_000  # Measured F1 counterexample: 45ms lag.
    assert native.fresh()
    native.sim_clock=lambda:10_050_000_000
    assert not native.fresh()
    native.sim_clock=lambda:10_000_000_000
    native.latest['monotonic_ns']=now-3_000_000_000
    assert not native.fresh()


def test_sequential_native_tails_pair_the_same_step_before_testing_freshness(tmp_path):
    native=NativeContact(tmp_path,'a',{});old=time.monotonic_ns()-500_000_000
    def physics(ns):return dict(monotonic_ns=old,sim_ns=ns)
    def contact(ns):return dict(monotonic_ns=old,sim_ns=ns,
        targets={'a':dict(component_present=True,pose=[0.,0.,0.],contacts={})})
    steps=[10_000_000_000+i*5_000_000 for i in range(5)]
    (tmp_path/'physics.jsonl').write_text(''.join(json.dumps(physics(ns))+'\n' for ns in steps[:3]))
    (tmp_path/'contacts.jsonl').write_text(''.join(json.dumps(contact(ns))+'\n' for ns in steps))
    native.sim_clock=lambda:steps[2];native.poll()
    assert native.latest['sim_ns']==native.matched_physics['sim_ns']==steps[2]
    assert len(native.pending)==2 and native.fresh()
    with (tmp_path/'physics.jsonl').open('a') as f:
        f.write(''.join(json.dumps(physics(ns))+'\n' for ns in steps[3:]))
    native.sim_clock=lambda:steps[-1];native.poll()
    assert native.latest['sim_ns']==native.matched_physics['sim_ns']==steps[-1]
    assert not native.pending and native.fresh()
    with (tmp_path/'physics.jsonl').open('a') as f:f.write(json.dumps(physics(steps[-1]+50_000_000))+'\n')
    native.poll()
    assert not native.fresh()  # Physics advancing without matching contacts.


def test_native_contact_uses_physical_parent_plus_fixed_tcp_transform(tmp_path):
    native=NativeContact(tmp_path,'a',{})
    now=time.monotonic_ns();physics=dict(sim_ns=1,monotonic_ns=now,parent_pose=[0.,0.,0.,0.,0.,0.,1.])
    reg=dict(finger='gripper_left_link',patch_in_ee=[[[0.,0.,0.],[.001,0.,0.],[0.,.001,0.]]])
    native.begin(reg)
    row=dict(sim_ns=1,monotonic_ns=time.monotonic_ns(),targets={'a':dict(component_present=True,
        pose=[.1085,0.,0.,0.,0.,0.,1.],contacts={'contact':[dict(collision1={'name':'a::link::col'},
        collision2={'name':'open_manipulator_x::gripper_left_link::gripper_left_link_collision'},
        position=[dict(x=.126,y=0.,z=0.)],normal=[dict(x=1.,y=0.,z=0.)])]} )})
    (tmp_path/'physics.jsonl').write_text(json.dumps(physics)+'\n')
    (tmp_path/'contacts.jsonl').write_text(json.dumps(row)+'\n')
    native.poll();assert native.observed() is True
    assert native.max_patch_error<1e-12


def test_native_bootstrap_prefix_is_counted_but_later_expired_steps_refuse(tmp_path):
    native=NativeContact(tmp_path,'a',{});now=time.monotonic_ns()
    def physics(ns):return dict(monotonic_ns=now,sim_ns=ns)
    def contact(ns):return dict(monotonic_ns=now,sim_ns=ns,
        targets={'a':dict(component_present=True,pose=[0.,0.,0.],contacts={})})
    (tmp_path/'physics.jsonl').write_text(''.join(json.dumps(physics(ns))+'\n' for ns in [10,15,20]))
    (tmp_path/'contacts.jsonl').write_text(''.join(json.dumps(contact(ns))+'\n' for ns in [5,10,15,20]))
    native.poll()
    assert native.error is None and native.pre_robot_contact_prefix_records==1
    assert native.latest['sim_ns']==20 and native.fresh()
    native.frames.pop(10);native.order.popleft()
    with (tmp_path/'contacts.jsonl').open('a') as f:f.write(json.dumps(contact(10))+'\n')
    native.poll()
    assert native.error=='native contact step expired without a physics match'
    assert not native.fresh()


def test_joint_window_selects_a_coherent_measured_frame_without_relaxing_age():
    names=['joint1','joint2','joint3','joint4','gripper_left_joint','gripper_right_joint']
    def sample(ns,value=0.):
        return NS(header=NS(stamp=NS(sec=ns//10**9,nanosec=ns%10**9)),name=names,position=[value]*6)
    samples=[(sample(9_990_000_000,.1),100.),(sample(10_010_000_000,.2),100.01)]
    selected=fresh_joint_values(samples,10_000_000_000,100.02)
    assert selected is not None and selected[0].tolist()==[.1]*4
    assert selected[2]['source_age_s']==pytest.approx(.01)
    # Consumer ROS /clock could be9.980s; it does not replace native physics time.
    assert fresh_joint_values(samples,10_020_000_000,100.02)[0].tolist()==[.2]*4
    assert fresh_joint_values(samples,9_980_000_000,100.02) is None
    assert fresh_joint_values(samples,10_500_000_000,100.02) is None
    assert fresh_joint_values(samples,10_020_000_000,100.5) is None


def test_unknown_goal_response_latches_before_any_cleanup_goal(monkeypatch):
    import flexcell_skills.contact_motion as module
    monkeypatch.setattr(module,'ActionClient',Mock())
    node=Mock();motion=module.ConstrainedMotion(node,Mock(),Mock(),lambda _:None,Mock(),lambda:False)
    future=Mock();future.done.return_value=False
    with pytest.raises(module.MotionUnknown):motion.wait(future,.001,physical=True)
    assert motion.blocked and not motion.terminal_known
    with pytest.raises(module.MotionUnknown):motion.execute({},'RETURN')
    motion.action.send_goal_async.assert_not_called()


def test_self_collision_refusal_cannot_register_or_dispatch(monkeypatch):
    import flexcell_skills.contact_motion as module
    monkeypatch.setattr(module,'ActionClient',Mock())
    node=Mock();node.create_client.side_effect=[Mock(),Mock()];q=np.zeros(4)
    motion=module.ConstrainedMotion(node,arm(),lambda:(q,(0.,0.)),lambda _:None,Mock(),lambda:False)
    motion.action.wait_for_server.return_value=True
    motion.registration.wait_for_service.return_value=True;motion.validity.wait_for_service.return_value=True
    future=Mock();future.done.return_value=True;future.result.return_value=NS(valid=False)
    motion.validity.call_async.return_value=future
    with pytest.raises(module.MotionFailed,match='self-collision'):
        motion.execute(dict(positions=np.array([q,q])),'STROKE')
    motion.registration.call_async.assert_not_called();motion.action.send_goal_async.assert_not_called()


def test_geometry_planning_keeps_observation_callbacks_running_without_dispatch(monkeypatch):
    import flexcell_skills.contact_motion as module
    monkeypatch.setattr(module,'ActionClient',Mock())
    ready=threading.Event();callbacks=[]
    def pump(_):
        callbacks.append('observation')
        if len(callbacks)>=3:ready.set()
    def planner():
        assert ready.wait(timeout=1.)
        return 'validated geometry'
    motion=module.ConstrainedMotion(Mock(),arm(),Mock(),pump,Mock(),lambda:False)
    assert motion.plan_observed(planner)=='validated geometry'
    assert len(callbacks)>=3
    motion.action.send_goal_async.assert_not_called()


def test_changed_observation_while_planning_never_dispatches(monkeypatch):
    import flexcell_skills.contact_motion as module
    monkeypatch.setattr(module,'ActionClient',Mock())
    release=threading.Event()
    def pump(_):release.set()
    def guard():return 'target moved'
    motion=module.ConstrainedMotion(Mock(),arm(),Mock(),pump,Mock(),lambda:False,guard)
    with pytest.raises(module.MotionFailed,match='target moved'):
        motion.plan_observed(lambda:release.wait(timeout=1.))
    motion.action.send_goal_async.assert_not_called()


def test_read_only_planning_cannot_bypass_the_fresh_state_gate_before_motion(monkeypatch):
    import flexcell_skills.contact_motion as module
    monkeypatch.setattr(module,'ActionClient',Mock())
    state=Mock(side_effect=module.MotionFailed('fresh measured joints unavailable'))
    motion=module.ConstrainedMotion(Mock(),arm(),state,lambda _:None,Mock(),lambda:False)
    assert motion.plan_observed(lambda:'geometry only',guard=lambda:None)=='geometry only'
    state.assert_not_called()
    with pytest.raises(module.MotionFailed,match='fresh measured joints'):
        motion.execute({},'APPROACH')
    motion.action.send_goal_async.assert_not_called();motion.registration.call_async.assert_not_called()
