"""A CompositeStage with action=PUSH must reach the push skill, not a place.

WHY THIS TEST EXISTS SEPARATELY FROM test_push_server.py
    Everything can be individually correct and still wired wrong: the contract
    can judge a push, the server can execute one, and the composite chain can
    still hand a push stage to RunPickPlace because the stage->plan mapping
    dropped the new fields. That is the failure this file rules out, by driving
    the REAL TaskFsmServer._execute_composite with only the action clients faked.

LEGACY COMPATIBILITY IS ASSERTED HERE TOO
    The same path, with a stage that has no action field, must produce a
    RunPickPlace goal exactly as before. If someone makes the push branch the
    default, that test fails.
"""
import threading
from types import SimpleNamespace
from unittest.mock import Mock

from flexcell_interfaces.action import (
    Observe, PushObject, RunComposite, RunPickPlace)
from flexcell_interfaces.msg import CompositeStage, ObjectPosition, WorldObject

from flexcell_skills.task_fsm_server import TaskFsmServer
from flexcell_skills.contracts.composite import ACTION_PUSH

BOX_A = [0.220, 0.0, 0.0175]


def server():
    n = TaskFsmServer.__new__(TaskFsmServer)
    n._composite_dir = '/tmp/t08-dispatch'
    n._admission = threading.Lock()
    n._skill_wait = 20
    n._policy = SimpleNamespace(name='fsm', version='test')
    n._publish_task_state = Mock()
    n._has_pending_skill_goal = lambda: False
    n._cli_observe = Mock()
    n._cli_push = Mock()
    n.get_logger = lambda: Mock()
    n._demo_call = Mock()
    n._execute_plan = Mock()
    n._active_task_run_id = None
    n._quarantine = SimpleNamespace(active=False)
    return n


def composite_goal(stage):
    request = RunComposite.Goal()
    request.scenario_id = 't08'
    request.motion_profile_id = 'demo_slow'
    request.position_tolerance_m = 0.02
    request.clearance_m = 0.05
    obj = ObjectPosition()
    obj.object_name = 'target_box_a'
    obj.position.x, obj.position.y, obj.position.z = BOX_A
    request.initial_objects = [obj]
    request.stages = [stage]
    return SimpleNamespace(request=request,
                           goal_id=SimpleNamespace(uuid=[2] * 16),
                           is_cancel_requested=False,
                           publish_feedback=Mock(), succeed=Mock(),
                           abort=Mock(), canceled=Mock())


def push_stage():
    stage = CompositeStage()
    stage.stage_id = 'shove'
    stage.object_name = 'target_box_a'
    stage.action = ACTION_PUSH
    stage.push_direction.x, stage.push_direction.y = -1.0, 0.0
    stage.push_distance_m = 0.030
    stage.contact_height_m = 0.030
    stage.overdrive_m = 0.02
    return stage


def legacy_stage():
    stage = CompositeStage()
    stage.stage_id = 'put'
    stage.object_name = 'target_box_a'
    stage.place_pose.header.frame_id = 'world'
    stage.place_pose.pose.orientation.w = 1.0
    stage.place_pose.pose.position.x = 0.12
    stage.place_pose.pose.position.y = -0.15
    stage.place_pose.pose.position.z = 0.0175
    return stage


def observe_reply(node, actual):
    def call(client, request, label, goal_handle, started, deadline):
        reply = Observe.Result()
        reply.outcome, reply.error_code = 0, 0
        reply.evidence_id = 'obs'
        reply.world_state.source = 'SIMULATION_GROUND_TRUTH'
        reply.world_state.revision = 1
        reply.world_state.carry.engaged = False
        reply.world_state.carry.object_id = ''
        obj = WorldObject()
        obj.name = 'target_box_a'
        obj.available = True
        obj.pose.position.x, obj.pose.position.y, obj.pose.position.z = actual
        reply.world_state.objects = [obj]
        return reply, None
    return call


def test_a_push_stage_is_dispatched_to_the_push_skill():
    node = server()
    actual = list(BOX_A)
    node._demo_call = Mock(side_effect=observe_reply(node, actual))
    handle = composite_goal(push_stage())

    def fake_demo_call(client, goal, label, view, started, deadline):
        if client is node._cli_push:
            actual[0] = BOX_A[0] - 0.030
            result = PushObject.Result()
            result.outcome, result.error_code = 0, 0
            result.evidence_id = 'push-1'
            result.displacement_m = 0.030
            result.direction_cos = 1.0
            result.lateral_m = 0.0
            result.delta_z_m = 0.0
            result.contact_made = True
            result.contact_lost = False
            result.carry_engaged_during = False
            return result, None
        return observe_reply(node, actual)(client, goal, label, view, started, deadline)

    node._demo_call = Mock(side_effect=fake_demo_call)
    result = node._execute_composite(handle)
    assert result.outcome == 0, result.detail
    assert result.completed_stage_ids == ['shove']
    sent = [c.args[1] for c in node._demo_call.call_args_list
            if c.args and c.args[0] is node._cli_push]
    assert len(sent) == 1 and isinstance(sent[0], PushObject.Goal)
    assert sent[0].object_name == 'target_box_a'
    assert sent[0].distance_m == 0.030
    assert sent[0].contact_height_m == 0.030
    # NaN on the wire means "use the server parameter" and must be forwarded as
    # NaN, not silently rewritten to 0.0 (which is the table plane).
    assert sent[0].overdrive_m == 0.02


def test_a_push_goal_never_carries_a_place_pose():
    """A push stage has no destination. If the mapping invented one, a plan
    could place and push at once."""
    node = server()
    actual = list(BOX_A)
    handle = composite_goal(push_stage())
    seen = {}

    def fake(client, goal, label, view, started, deadline):
        if client is node._cli_push:
            seen['goal'] = goal
            actual[0] = BOX_A[0] - 0.030
            result = PushObject.Result()
            result.outcome, result.error_code = 0, 0
            result.displacement_m, result.direction_cos = 0.030, 1.0
            result.lateral_m, result.delta_z_m = 0.0, 0.0
            result.contact_made = True
            return result, None
        return observe_reply(node, actual)(client, goal, label, view, started, deadline)

    node._demo_call = Mock(side_effect=fake)
    node._execute_composite(handle)
    assert isinstance(seen['goal'], PushObject.Goal)
    assert not hasattr(seen['goal'], 'place_pose')


def test_a_legacy_stage_still_reaches_the_pick_place_path():
    """Backward compatibility at the dispatch boundary, not just in the plan."""
    node = server()
    actual = list(BOX_A)

    def native(view, single, admission_held, component):
        actual[:] = [0.12, -0.15, 0.0175]
        result = RunPickPlace.Result()
        result.object_at_place = True
        result.final_position_error_m = 0.001
        component.update(
            run_id='native-one', episode_path='test-native.json',
            final_state=dict(goal_uuid=bytes(view.goal_id.uuid).hex(),
                             outcome='0', error_code=0, object_at_place=True,
                             final_position_error_m=0.001))
        view.succeed()
        return result

    node._demo_call = Mock(side_effect=observe_reply(node, actual))
    node._execute_plan = Mock(side_effect=native)
    handle = composite_goal(legacy_stage())
    result = node._execute_composite(handle)
    assert result.outcome == 0, result.detail
    assert result.completed_stage_ids == ['put']
    # The push client was never touched.
    assert not any(c.args and c.args[0] is node._cli_push
                   for c in node._demo_call.call_args_list)
    assert node._execute_plan.called


def test_a_push_stage_that_moved_nothing_fails_the_chain():
    node = server()
    actual = list(BOX_A)

    def fake(client, goal, label, view, started, deadline):
        if client is node._cli_push:
            result = PushObject.Result()
            result.outcome, result.error_code = 27, 27     # CONTACT_NOT_MADE
            result.displacement_m = 0.0
            result.direction_cos = float('nan')
            result.lateral_m, result.delta_z_m = 0.0, 0.0
            result.contact_made = False
            return result, None
        return observe_reply(node, actual)(client, goal, label, view, started, deadline)

    node._demo_call = Mock(side_effect=fake)
    handle = composite_goal(push_stage())
    result = node._execute_composite(handle)
    assert result.outcome == 1
    assert result.error_code == 62          # component failed
    assert result.completed_stage_ids == []
