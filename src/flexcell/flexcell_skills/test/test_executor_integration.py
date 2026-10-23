#!/usr/bin/env python3
"""Executor integration tests (audit P1-4 sub-item, issue #8 scope note).

The offline suites cover the pure contracts; THIS suite drives the REAL
executor code paths with duck-typed ROS plumbing (no rclpy spin, no
simulator): the demo loop with the live FSMPolicy + safety gate + episode
recorder, the RunPickPlace skill-call helper, and pick_server's grasp path.

Covers the three paths the M2.3 audit named:
  1. _execute_demo abort path  -> typed ERR_RECOVERY_EXHAUSTED, never the
     catch-all 'policy state error'
  2. _call_skill timeout       -> (None, '<STATE> result timeout (cancel sent)')
  3. carry/planning-scene engage failure on PICK -> typed ERR_GRASP_FAILED,
     carry_stop published (safety release attempted)
plus the atomic admission lock (second concurrent task -> RESOURCE_BUSY).
"""

import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from geometry_msgs.msg import Point, Pose
from moveit_msgs.msg import CollisionObject
from std_msgs.msg import Header as StdHeader

from flexcell_interfaces.action import PickObject, RunDemo, RunPickPlace
from flexcell_interfaces.msg import (
    CarryState, RobotStateSummary, WorldObject, WorldState, ZoneState)

from flexcell_skills.contracts.episode import EpisodeStore, replay_episode
from flexcell_skills.contracts.injection import InjectionLifecycle
from flexcell_skills.common import JsonlLog, PlanningSceneOps
from flexcell_skills.decision_policy import FSMPolicy
from flexcell_skills.jev_policy import JevBackend, JevPolicy, JevResponse
from flexcell_skills.task_fsm_server import TaskFsmServer
from flexcell_skills import pick_server as pick_server_module
from flexcell_skills.pick_server import PickServer


class _Logger:
    def info(self, *a, **k):
        pass

    warn = info
    error = info
    fatal = info


class _ScriptedJevBackend(JevBackend):
    """Synthetic model choices; exercise the real JevPolicy and executor."""
    name = 'scripted-test'

    def __init__(self, choices):
        self._choices = iter(choices)

    def health(self):
        return True, 'synthetic backend'

    def classify(self, state, question):
        return JevResponse(next(self._choices), 0.9, {'tokens': 7})


class _StubNode:
    def get_logger(self):
        return _Logger()


def _pose(x=0.0, y=0.0, z=0.0175):
    p = Pose()
    p.position.x, p.position.y, p.position.z = x, y, z
    p.orientation.w = 1.0
    return p


def _world_state():
    """A fully-populated v2 WorldState msg (passes serialize_envelope)."""
    ws = WorldState()
    ws.header = StdHeader()
    ws.header.frame_id = 'world'
    ws.revision = 7
    ws.source = 'SIMULATION_GROUND_TRUTH'
    ws.schema_version = '2.0'
    ws.robot = RobotStateSummary()
    ws.robot.ee_frame = 'end_effector_link'
    ws.robot.joint_names = ['joint1']
    ws.robot.positions = [0.0]
    ws.robot.ee_pose = _pose(0.22, 0.0, 0.177)
    ws.robot.has_gripper_state = False
    a = WorldObject()
    a.name, a.klass, a.available = 'target_box_a', 'box', True
    a.pose, a.size = _pose(0.22, 0.0), [0.035, 0.035, 0.035]
    a.pose_age_s = 0.04
    ws.objects.append(a)
    b = WorldObject()
    b.name, b.klass, b.available = 'target_box_b', 'box', True
    b.pose, b.size = _pose(0.20, -0.18), [0.035, 0.035, 0.035]
    b.pose_age_s = 0.04
    ws.objects.append(b)
    ws.carry = CarryState()
    ws.carry.engaged = False
    z = ZoneState()
    z.id, z.occupancy = 'zone_1', 0
    c = Point()
    c.x, c.y, c.z = 0.12, -0.15, 0.0175
    z.center = c
    ws.zones.append(z)
    return ws


class _GoalHandle:
    def __init__(self, request):
        self.request = request
        self.terminal = None
        self.cancel_requested = False

    @property
    def is_cancel_requested(self):
        return self.cancel_requested

    def publish_feedback(self, _fb):
        pass

    def succeed(self):
        self.terminal = 'succeed'

    def abort(self):
        self.terminal = 'abort'

    def canceled(self):
        self.terminal = 'canceled'


def _skill_result(outcome=0, error_code=0, detail='ok', evidence_id='ev',
                  world_state=None):
    return SimpleNamespace(
        outcome=outcome, error_code=error_code, detail=detail,
        evidence_id=evidence_id, world_state=world_state,
        grasp_attached=True if outcome == 0 else False)


def _make_demo_call(script, calls):
    """Instance-attribute stub for _demo_call: canned results by action
    prefix (labels look like OBSERVE_A / PICK_A(attempt=1) / REOBSERVE_A);
    a single-entry script repeats that result forever."""

    def _demo_call(cli, goal, label, goal_handle, t0, deadline_s):
        calls.append(label)
        base = label.split('(')[0]
        # label grammar: ACTION_TAG / REOBSERVE_TAG / ACTION_TAG(attempt=n)
        key = 'OBSERVE' if base.startswith('REOBSERVE') else base.split('_')[0]
        seq = script[key]
        seen = sum(1 for c in calls
                   if ('OBSERVE' if c.split('(')[0].startswith('REOBSERVE')
                       else c.split('(')[0].split('_')[0]) == key)
        return seq[min(len(seq) - 1, seen - 1)]

    return _demo_call


def _make_fsm(tmpdir, demo_call):
    node = TaskFsmServer.__new__(TaskFsmServer)
    node._policy = FSMPolicy()
    node._obj_a = 'target_box_a'
    node._obj_b = 'target_box_b'
    node._zones = {'zone_1': (0.12, -0.15, 0.0175),
                   'zone_2': (0.25, 0.05, 0.0175)}
    node._budget = 1
    node._demo_tol = 0.06
    node._tol = 0.06
    node._seq = 0
    node._admission = threading.Lock()
    node.get_logger = lambda: _Logger()
    node.get_parameter = lambda name: SimpleNamespace(value='')
    node._publish_task_state = lambda state: None
    node._demo_log = JsonlLog(_StubNode(), tmpdir, 'demo_runs_it.jsonl')
    node._log = JsonlLog(_StubNode(), tmpdir, 'task_runs_it.jsonl')
    node._decision_log = JsonlLog(_StubNode(), tmpdir, 'decisions_it.jsonl')
    node._episodes = EpisodeStore(tmpdir, _Logger())
    node._cli_observe = node._cli_pick = None
    node._cli_place = node._cli_verify = None
    node._demo_call = demo_call
    return node


class TestDemoAbortPath(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='fx_it_')
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_pick_budget_exhaustion_is_typed(self):
        """Audit acceptance: the exhaust scenario must finish with the typed
        ERR_RECOVERY_EXHAUSTED - never the 'policy state error' catch-all."""
        calls = []
        script = {
            'OBSERVE': [(_skill_result(world_state=_world_state()), None)],
            'PICK': [(_skill_result(outcome=1, error_code=23,
                                    detail='injected grasp failure'), None)],
            'PLACE': [], 'VERIFY': [],
        }
        node = _make_fsm(self.tmp, _make_demo_call(script, calls))
        gh = _GoalHandle(RunDemo.Goal())
        gh.request.scenario_id = 'it_abort'
        res = node._execute_demo(gh)

        self.assertEqual(res.outcome, RunDemo.Result.OUTCOME_FAILED)
        self.assertEqual(res.error_code, RunDemo.Result.ERR_RECOVERY_EXHAUSTED)
        self.assertIn('policy abort (BUDGET_EXHAUSTED)', res.detail)
        self.assertNotIn('policy state error', res.detail)
        self.assertEqual(gh.terminal, 'abort')
        # the trace shows the full recovery shape before the abort
        self.assertIn('RECOVERY:REOBSERVE+RETRY', ','.join(res.fsm_trace))
        # episode record: typed final state + safety accounting
        import glob
        episodes = sorted(glob.glob(self.tmp + '/it_abort_*.json'))
        self.assertEqual(len(episodes), 1)
        with open(episodes[0]) as fh:
            episode = json.load(fh)
        self.assertEqual(episode['final_state']['error_code'],
                         RunDemo.Result.ERR_RECOVERY_EXHAUSTED)
        self.assertGreaterEqual(
            episode['final_state']['safety']['evaluated'], 4)

    def test_second_concurrent_task_gets_resource_busy(self):
        node = _make_fsm(self.tmp, _make_demo_call(
            {'OBSERVE': [], 'PICK': [], 'PLACE': [], 'VERIFY': []}, []))
        node._admission.acquire()   # another task holds the arm
        gh = _GoalHandle(RunDemo.Goal())
        gh.request.scenario_id = 'it_busy'
        res = node._execute_demo(gh)
        self.assertEqual(res.outcome, RunDemo.Result.OUTCOME_FAILED)
        self.assertEqual(res.error_code, RunDemo.Result.ERR_RESOURCE_BUSY)
        node._admission.release()

    def test_jev_budget_abort_retains_51_and_last_skill_cause(self):
        calls = []
        script = {
            'OBSERVE': [(_skill_result(world_state=_world_state()), None)],
            'PICK': [(_skill_result(outcome=1, error_code=23), None)],
            'PLACE': [], 'VERIFY': [],
        }
        node = _make_fsm(self.tmp, _make_demo_call(script, calls))
        node._policy = JevPolicy(_ScriptedJevBackend(
            ['PICK', 'OBSERVE', 'PICK', 'ABORT']))
        gh = _GoalHandle(RunDemo.Goal())
        gh.request.scenario_id = 'it_jev_exhaust'
        result = node._execute_demo(gh)
        self.assertEqual(result.error_code, RunDemo.Result.ERR_RECOVERY_EXHAUSTED)
        self.assertIn('previous_skill=PICK cause=ERR_GRASP_FAILED', result.detail)
        self.assertEqual(gh.terminal, 'abort')
        self.assertEqual(sum(c.startswith('PICK') for c in calls), 2)

    def test_observe_abort_uses_real_reply_without_changing_policy_history(self):
        for code, name in [(2, 'ERR_INTERNAL'), (3, 'ERR_WORLD_STATE_UNAVAILABLE')]:
            with self.subTest(code=code):
                script = {
                    'OBSERVE': [(_skill_result(outcome=1, error_code=code,
                                              detail='real observe failure'), None)],
                    'PICK': [], 'PLACE': [], 'VERIFY': [],
                }
                node = _make_fsm(self.tmp, _make_demo_call(script, []))
                node._policy = JevPolicy(_ScriptedJevBackend([]))
                gh = _GoalHandle(RunDemo.Goal())
                gh.request.scenario_id = 'it_observe_%d' % code
                result = node._execute_demo(gh)
                self.assertEqual(result.error_code, 50)
                self.assertIn('previous_skill=OBSERVE cause=%s legacy_error_code=%d'
                              % (name, code), result.detail)
                path = next(Path(self.tmp).glob(
                    'it_observe_%d_*.json' % code))
                episode = json.loads(path.read_text())
                self.assertEqual(episode['steps'][0]['executor_result']['error_code'], code)
                history = episode['steps'][1]['policy_input']['history'][-1]
                self.assertEqual((history['outcome'], history['error_code']), (255, -1))
                self.assertEqual(episode['final_state']['detail'], result.detail)

    def test_observe_transport_timeout_remains_a_timeout(self):
        script = {'OBSERVE': [(None, 'observe result timeout')],
                  'PICK': [], 'PLACE': [], 'VERIFY': []}
        node = _make_fsm(self.tmp, _make_demo_call(script, []))
        result = node._execute_demo(_GoalHandle(RunDemo.Goal()))
        self.assertEqual(result.error_code, 50)
        self.assertIn('previous_skill=OBSERVE cause=ERR_TIMEOUT legacy_error_code=-1',
                      result.detail)

    def test_successful_reobserve_does_not_reuse_old_pick_failure(self):
        script = {'OBSERVE': [(_skill_result(world_state=_world_state()), None)],
                  'PICK': [(_skill_result(outcome=1, error_code=23), None)],
                  'PLACE': [], 'VERIFY': []}
        node = _make_fsm(self.tmp, _make_demo_call(script, []))
        node._policy = JevPolicy(_ScriptedJevBackend(['PICK', 'OBSERVE', 'ABORT']))
        result = node._execute_demo(_GoalHandle(RunDemo.Goal()))
        self.assertEqual(result.error_code, 50)
        self.assertNotIn('previous_skill=', result.detail)


class TestSingleTaskPolicySeam(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='fx_single_it_')
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def drive(self, place_fails=False, skip_verify=False, recover_pick=False,
              policy=None):
        calls = []
        pick = [(_skill_result(), None)]
        if recover_pick:
            pick.insert(0, (_skill_result(outcome=1, error_code=23), None))
        script = {
            'OBSERVE': [(_skill_result(world_state=_world_state()), None)],
            'PICK': pick,
            'PLACE': [(SimpleNamespace(outcome=1 if place_fails else 0,
                                       error_code=10 if place_fails else 0,
                                       detail='place', evidence_id='place',
                                       released=not place_fails,
                                       object_pose_after=_pose(0.12, -0.15)), None)],
            'VERIFY': [(SimpleNamespace(outcome=0, error_code=0, detail='verified',
                                        evidence_id='verify', has_measured_pose=True,
                                        position_error_m=0.002), None)],
        }
        node = _make_fsm(self.tmp, _make_demo_call(script, calls))
        if policy is not None:
            node._policy = policy
        goal = RunPickPlace.Goal()
        goal.object_name = 'target_box_a'
        goal.place_pose.pose = _pose(0.12, -0.15)
        goal.motion_profile_id = 'demo_slow'
        goal.skip_verify = skip_verify
        gh = _GoalHandle(goal)
        result = node._execute(gh)
        import glob
        with open(glob.glob(self.tmp + '/pick_place_v1_*.json')[0]) as fh:
            episode = json.load(fh)
        return result, episode, calls

    def test_task_success_records_real_verifier_result_and_replays(self):
        result, episode, _ = self.drive()
        self.assertEqual(result.outcome, 0)
        self.assertTrue(result.object_at_place)
        self.assertEqual(episode['final_state']['final_position_error_m'], 0.002)
        self.assertEqual(len(episode['steps']), 4)
        self.assertTrue(all(r['ok'] for r in replay_episode(episode, FSMPolicy())))
        for step in episode['steps']:
            self.assertEqual(step['decide_latency_clock'], 'perf_counter_ns')
            self.assertGreater(step['decide_latency_ms'], 0)

    def test_s4_place_failure_is_a_policy_abort_with_replay(self):
        result, episode, calls = self.drive(place_fails=True)
        self.assertEqual(result.outcome, 1)
        self.assertEqual(episode['steps'][-1]['policy_output']['action'], 'ABORT')
        self.assertFalse(any(c.startswith('VERIFY') for c in calls))
        self.assertTrue(all(r['ok'] for r in replay_episode(episode, FSMPolicy())))

    def test_jev_s4_preserves_typed_skill_cause_in_result_and_episode(self):
        result, episode, calls = self.drive(
            place_fails=True,
            policy=JevPolicy(_ScriptedJevBackend(['PICK', 'PLACE', 'ABORT'])))
        self.assertEqual(result.error_code, RunPickPlace.Result.ERR_SKILL_FAILED)
        self.assertIn('previous_skill=PLACE cause=ERR_IK_UNREACHABLE', result.detail)
        self.assertEqual(episode['final_state']['detail'], result.detail)
        output = episode['steps'][-1]['policy_output']
        self.assertEqual(output['policy_trace']['source'], 'jev')
        self.assertFalse(output['policy_trace']['fallback'])
        self.assertFalse(any(c.startswith('VERIFY') for c in calls))

    def test_pick_recovery_uses_policy_and_counts_attempt_two(self):
        result, episode, calls = self.drive(recover_pick=True)
        self.assertEqual(result.outcome, 0)
        self.assertIn('PICK_A(attempt=2)', calls)
        self.assertEqual(len(episode['steps']), 6)
        self.assertTrue(all(r['ok'] for r in replay_episode(episode, FSMPolicy())))

    def test_skip_verify_does_not_invent_a_measurement(self):
        result, episode, calls = self.drive(skip_verify=True)
        self.assertEqual(result.outcome, 0)
        self.assertTrue(result.object_at_place)
        self.assertIsNone(episode['final_state']['final_position_error_m'])
        self.assertEqual(len(episode['steps']), 3)
        self.assertFalse(any(c.startswith('VERIFY') for c in calls))


class TestCallSkillTimeout(unittest.TestCase):

    def test_result_timeout_cancels_and_reports(self):
        node = TaskFsmServer.__new__(TaskFsmServer)

        class _NeverDone:
            def done(self):
                return False

            def result(self):  # pragma: no cover - must not be reached
                raise AssertionError('result() on a never-done future')

        class _GoalStub:
            def __init__(self):
                self.accepted = True
                self.cancelled = False

            def cancel_goal_async(self):
                self.cancelled = True

            def get_result_async(self):
                return _NeverDone()

        gh_stub = _GoalStub()

        class _Cli:
            def wait_for_server(self, timeout_sec=None):
                return True

            def send_goal_async(self, goal):
                f = SimpleNamespace(done=lambda: True,
                                    result=lambda: gh_stub)
                return f

        rec = {}
        result, err = node._call_skill(_Cli(), RunDemo.Goal(), 'VERIFY',
                                       [], rec, 0.15)
        self.assertIsNone(result)
        self.assertEqual(err, 'VERIFY result timeout (cancel sent)')


class TestPickEngageFailure(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='fx_pick_it_')
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_planning_scene_attach_failure_is_typed_and_releases(self):
        node = PickServer.__new__(PickServer)
        node._seq = 0
        node._admission = threading.Lock()
        node.get_logger = lambda: _Logger()
        node._log = JsonlLog(_StubNode(), self.tmp, 'pick_it.jsonl')
        node._profiles = ['demo_slow']
        node._default_profile = 'demo_slow'
        node._deadline = 30000
        # T6: the injection is a four-state lifecycle object now, not three
        # loose attributes (a bare fixture without it made _injection_check
        # raise and the typed GRASP_FAILED degrade to ERR_INTERNAL).
        node._inject = InjectionLifecycle()
        node._publish_inject_status = lambda: None
        node._base = 'world'
        node._ee = 'end_effector_link'
        node._size = [0.035, 0.035, 0.035]
        node._hover = 0.22
        node._grasp_dz = 0.16
        node._raise = 0.10
        node._attach_radius = 0.20
        node._follow_min = 0.03
        node._gripper_open = 0.02
        node._gripper_close = -0.011
        node._m2p = SimpleNamespace(call=lambda *a, **k: (
            SimpleNamespace(outcome=0, error_code=0, detail='ok'), None))
        node._gripper = SimpleNamespace(command=lambda *a, **k: (
            SimpleNamespace(stalled=False), None))
        node._carry_backend = 'teleport'
        node._carry_start = SimpleNamespace(publish=lambda m: None)
        stopped = []
        node._carry_stop = SimpleNamespace(publish=lambda m: stopped.append(m))
        node._scene = SimpleNamespace(
            add_box=lambda *a, **k: (True, ''),
            attach=lambda *a, **k: (False, 'boom'),
            remove=lambda *a, **k: (True, ''))
        tf = SimpleNamespace(transform=SimpleNamespace(
            translation=SimpleNamespace(x=0.22, y=0.0, z=0.1775),
            rotation=SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0)))
        node._tf_buffer = SimpleNamespace(
            lookup_transform=lambda *a, **k: tf)

        sample = lambda name, **k: (((0.22, 0.0, 0.0175),
                                     (0.0, 0.0, 0.0, 1.0)), None)
        patched = getattr(pick_server_module, 'sample_gz_pose')
        pick_server_module.sample_gz_pose = sample
        try:
            gh = _GoalHandle(PickObject.Goal())
            gh.request.object_name = 'target_box_a'
            gh.request.motion_profile_id = 'demo_slow'
            res = node._execute(gh)
        finally:
            pick_server_module.sample_gz_pose = patched

        self.assertEqual(res.outcome, PickObject.Result.OUTCOME_FAILED)
        self.assertEqual(res.error_code, PickObject.Result.ERR_GRASP_FAILED)
        self.assertIn('planning-scene attach failed', res.detail)
        # the safety release ran: the carry servo was told to stop
        self.assertGreaterEqual(len(stopped), 1)
        self.assertEqual(gh.terminal, 'abort')


class TestPickLiftCleanup(unittest.TestCase):
    """Drive the real lift failure branch and real planning-scene messages."""

    def drive(self, scene_ok=True, gripper_ok=True, cancel=False):
        node = PickServer.__new__(PickServer)
        values = dict(_seq=0, _admission=threading.Lock(),
                      _profiles=['demo_slow'], _default_profile='demo_slow',
                      _deadline=30000, _inject=InjectionLifecycle(), _base='world',
                      _size=[0.035] * 3, _hover=0.22, _grasp_dz=0.16, _raise=0.10,
                      _attach_radius=0.20, _follow_min=0.03,
                      _gripper_open=0.02, _gripper_close=-0.011,
                      _carry_backend='teleport')
        for key, value in values.items():
            setattr(node, key, value)
        node.get_logger = lambda: _Logger()
        node._publish_inject_status = lambda: None
        node._feedback = lambda *a: None
        node._log = SimpleNamespace(write=lambda rec: None)
        node._ee_position = lambda: ([0.22, 0.0, 0.1775], None)
        gh = _GoalHandle(PickObject.Goal())
        gh.request.object_name = 'target_box_a'
        gh.request.motion_profile_id = 'demo_slow'
        motions = []

        def motion(*args, **kwargs):
            motions.append(args)
            failed = len(motions) == 3
            if failed and cancel:
                gh.cancel_requested = True
            return SimpleNamespace(outcome=int(failed), error_code=10 if failed else 0,
                                   detail='NO_IK_SOLUTION' if failed else 'ok'), None

        node._m2p = SimpleNamespace(call=motion)
        gripper_calls = []

        def gripper(*args, **kwargs):
            gripper_calls.append(args)
            error = 'gripper unavailable' if len(gripper_calls) == 3 and not gripper_ok else None
            return SimpleNamespace(), error

        node._gripper = SimpleNamespace(command=gripper)
        stopped = []
        node._carry_start = SimpleNamespace(publish=lambda msg: None)
        node._carry_stop = SimpleNamespace(publish=lambda msg: stopped.append(msg))
        scenes = []
        node._scene = PlanningSceneOps.__new__(PlanningSceneOps)

        def apply(scene):
            scenes.append(scene)
            cleanup = bool(scene.robot_state.attached_collision_objects and
                           scene.world.collision_objects)
            return (False, 'apply rejected') if cleanup and not scene_ok else (True, '')

        node._scene._apply_scene = apply
        with patch.object(pick_server_module, 'sample_gz_pose', return_value=(
                ((0.22, 0.0, 0.0175), (0.0, 0.0, 0.0, 1.0)), None)), \
                patch.object(pick_server_module, 'interruptible_sleep', return_value=False):
            result = node._execute(gh)
        return result, scenes, stopped

    def test_lift_failure_clears_attachment_and_world_in_one_diff(self):
        result, scenes, stopped = self.drive()
        self.assertEqual(result.error_code, 30)
        self.assertEqual(len(stopped), 1)
        cleanup = scenes[-1]
        self.assertTrue(cleanup.robot_state.is_diff)
        attached = cleanup.robot_state.attached_collision_objects[0]
        world = cleanup.world.collision_objects[0]
        self.assertEqual(attached.object.id, 'target_box_a')
        self.assertEqual(world.id, attached.object.id)
        self.assertEqual(attached.object.operation, CollisionObject.REMOVE)
        self.assertEqual(world.operation, CollisionObject.REMOVE)

    def test_scene_cleanup_failure_is_not_a_recoverable_motion_failure(self):
        result, _, _ = self.drive(scene_ok=False)
        self.assertEqual(result.error_code, PickObject.Result.ERR_INTERNAL)
        self.assertIn('NO_IK_SOLUTION', result.detail)
        self.assertIn('planning-scene cleanup: apply rejected', result.detail)

    def test_gripper_cleanup_failure_is_not_a_recoverable_motion_failure(self):
        result, _, _ = self.drive(gripper_ok=False)
        self.assertEqual(result.error_code, PickObject.Result.ERR_INTERNAL)
        self.assertIn('gripper unavailable', result.detail)

    def test_cancel_during_lift_keeps_carry_and_attachment(self):
        result, scenes, stopped = self.drive(cancel=True)
        self.assertEqual(result.error_code, PickObject.Result.ERR_CANCELED)
        self.assertEqual(stopped, [])
        self.assertEqual(len(scenes), 2)  # world ADD, attachment ADD; no cleanup


if __name__ == '__main__':
    unittest.main()
