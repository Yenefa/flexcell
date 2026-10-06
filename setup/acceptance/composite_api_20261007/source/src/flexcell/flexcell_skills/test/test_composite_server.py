"""Real ROS callback admission, cancellation forwarding and typed failures."""
import threading
from types import SimpleNamespace
from unittest.mock import Mock

from flexcell_interfaces.action import Observe, RunComposite, RunPickPlace
from flexcell_interfaces.msg import CompositeStage, ObjectPosition, WorldObject
from flexcell_skills.task_fsm_server import ComponentGoal, TaskFsmServer


def goal():
    request=RunComposite.Goal();request.scenario_id='one';request.motion_profile_id='demo_slow'
    request.position_tolerance_m=.06;request.clearance_m=.05
    obj=ObjectPosition();obj.object_name='a';obj.position.x=.22;obj.position.z=.0175
    request.initial_objects=[obj]
    stage=CompositeStage();stage.stage_id='one';stage.object_name='a'
    stage.place_pose.header.frame_id='world';stage.place_pose.pose.orientation.w=1.
    stage.place_pose.pose.position.x=.12;stage.place_pose.pose.position.y=-.15;stage.place_pose.pose.position.z=.0175
    request.stages=[stage]
    return SimpleNamespace(request=request,goal_id=SimpleNamespace(uuid=[1]*16),is_cancel_requested=False,
                           publish_feedback=Mock(),succeed=Mock(),abort=Mock(),canceled=Mock())


def server(tmp_path):
    n=TaskFsmServer.__new__(TaskFsmServer)
    n._composite_dir=str(tmp_path);n._admission=threading.Lock();n._skill_wait=20
    n._policy=SimpleNamespace(name='fsm',version='test');n._publish_task_state=Mock()
    n._has_pending_skill_goal=lambda:False;n._cli_observe=Mock();n.get_logger=lambda:Mock()
    n._demo_call=Mock();n._execute_plan=Mock()
    return n


def test_parent_keeps_admission_across_observation_and_native_callback(tmp_path):
    n=server(tmp_path);h=goal();actual=[.22,0.,.0175]
    def observe(*args):
        assert n._admission.locked()
        reply=Observe.Result();reply.evidence_id='fresh';reply.world_state.source='SIMULATION_GROUND_TRUTH'
        o=WorldObject();o.name='a';o.available=True
        o.pose.position.x,o.pose.position.y,o.pose.position.z=actual
        reply.world_state.objects=[o]
        return reply,None
    def native(view, single, admission_held, component):
        assert single and admission_held and n._admission.locked()
        # A concurrent parent cannot dispatch anything while this child owns the arm.
        blocked=goal();r=n._execute_composite(blocked)
        assert r.error_code==41;blocked.abort.assert_called_once()
        assert n._admission.locked()
        view.publish_feedback(SimpleNamespace(state='PICK_A'))
        actual[:]=[.12,-.15,.0175]
        result=RunPickPlace.Result();result.object_at_place=True;result.final_position_error_m=.001
        component.update(run_id='native-one',episode_path='test-native.json',final_state=dict(goal_uuid=bytes(view.goal_id.uuid).hex(),outcome='0',error_code=0,
                                                            object_at_place=True,final_position_error_m=.001))
        view.succeed();return result
    n._demo_call.side_effect=observe;n._execute_plan.side_effect=native
    result=n._execute_composite(h)
    assert result.outcome==0 and result.completed_stage_ids==['one'] and result.component_run_ids==['native-one']
    assert not n._admission.locked();h.succeed.assert_called_once()
    assert isinstance(h.publish_feedback.call_args.args[0],RunComposite.Feedback)
    assert n._publish_task_state.call_args.args==('IDLE',)


def test_pending_skill_ownership_blocks_all_composite_dispatch(tmp_path):
    n=server(tmp_path);n._has_pending_skill_goal=lambda:True;h=goal()
    result=n._execute_composite(h)
    assert result.error_code==41 and result.outcome==1
    n._demo_call.assert_not_called();n._execute_plan.assert_not_called()
    assert n._publish_task_state.call_args.args==('BUSY',)


def test_invalid_pose_or_duplicate_initial_objects_no_motion(tmp_path):
    for invalid in ('pose','duplicate'):
        n=server(tmp_path);h=goal()
        if invalid=='pose':h.request.stages[0].place_pose.header.frame_id='camera'
        else:h.request.initial_objects*=2
        r=n._execute_composite(h)
        assert r.outcome==1 and r.error_code==60 and not n._admission.locked()
        n._execute_plan.assert_not_called();n._demo_call.assert_not_called()


def test_cancel_before_observation_no_motion(tmp_path):
    n=server(tmp_path);h=goal();h.is_cancel_requested=True
    result=n._execute_composite(h)
    assert result.outcome==2 and result.error_code==32
    h.canceled.assert_called_once();n._demo_call.assert_not_called();n._execute_plan.assert_not_called()


def test_child_forwards_cancel_without_terminating_parent():
    h=goal();view=ComponentGoal(h,RunPickPlace.Goal(),'12'*16,'one',0)
    h.is_cancel_requested=True;assert view.is_cancel_requested
    view.canceled();assert view.terminal_status=='CANCELED'
    h.canceled.assert_not_called();h.succeed.assert_not_called()


def test_receipt_open_failure_is_typed_failure(tmp_path):
    n=server(tmp_path);p=tmp_path/'file';p.write_text('cannot be directory');n._composite_dir=str(p)
    h=goal();r=n._execute_composite(h)
    assert r.outcome==1 and r.error_code==2 and not n._admission.locked()
    h.abort.assert_called_once();n._execute_plan.assert_not_called()


def test_native_callback_preserves_parent_lease_and_episode_identity(tmp_path):
    n=server(tmp_path);del n._execute_plan
    n._seq=0;n._zones={};n._episodes=Mock();n._log=Mock()
    n.get_parameter=lambda name:SimpleNamespace(value='')
    n._has_pending_skill_goal=lambda:True
    n._admission.acquire()
    context=dict(parent_run_id='parent-one',stage_id='one')
    h=ComponentGoal(goal(),RunPickPlace.Goal(),'34'*16,'one',0)
    try:
        result=n._execute_plan(h,single=True,admission_held=True,component=context)
        assert result.error_code==41 and n._admission.locked()
        episode=n._episodes.write.call_args.args[0]
        assert episode['run_id']==context['run_id'] and episode['final_state']['parent_run_id']=='parent-one'
        assert episode['final_state']['goal_uuid']=='34'*16
        assert episode['final_state']['execution_kind']=='IN_PROCESS_COMPONENT'
        assert episode['final_state']['component_execution_id']=='34'*16
        assert n._publish_task_state.call_args_list==[__import__('unittest.mock').mock.call('BUSY')]
    finally:n._admission.release()
