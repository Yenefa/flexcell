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
import shutil
import tempfile
import threading
import unittest
from types import SimpleNamespace

from geometry_msgs.msg import Point, Pose
from std_msgs.msg import Header as StdHeader

from flexcell_interfaces.action import PickObject, RunDemo, RunPickPlace
from flexcell_interfaces.msg import (
    CarryState, RobotStateSummary, WorldObject, WorldState, ZoneState)

from flexcell_skills.contracts.episode import EpisodeStore, replay_episode
from flexcell_skills.contracts.injection import InjectionLifecycle
from flexcell_skills.common import JsonlLog
from flexcell_skills.decision_policy import Decision, FSMPolicy
from flexcell_skills.task_fsm_server import TaskFsmServer
from flexcell_skills import pick_server as pick_server_module
from flexcell_skills.pick_server import PickServer


class _Logger:
    def info(self, *a, **k):
        pass

    warn = info
    error = info
    fatal = info


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


class TestSingleTaskPolicySeam(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='fx_single_it_')
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def drive(self, place_fails=False, skip_verify=False, recover_pick=False):
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
        node._pending_skill_sends = {}
        node._send_guard_lock = threading.Lock()

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

            def send_goal_async(self, goal, goal_uuid=None):
                f = SimpleNamespace(done=lambda: True,
                                    result=lambda: gh_stub)
                return f

        rec = {}
        result, err = node._call_skill(_Cli(), RunDemo.Goal(), 'VERIFY',
                                       [], rec, 0.15)
        self.assertIsNone(result)
        self.assertEqual(err, 'VERIFY result timeout (cancel sent)')
        self.assertTrue(gh_stub.cancelled)
        self.assertTrue(node._has_pending_skill_goal())

    def test_send_timeout_never_returns_to_a_retrying_policy(self):
        with tempfile.TemporaryDirectory(prefix='fx_send_timeout_') as tmp:
            calls = []
            node = _make_fsm(tmp, _make_demo_call({
                'OBSERVE': [(None, 'OBSERVE_A goal send timeout')],
            }, calls))

            class RetryEverything:
                name, version = 'retrying-test-policy', '1'
                invocations = 0

                def decide(self, world, goal, constraints, history):
                    self.invocations += 1
                    return Decision('OBSERVE', 'target_box_a')

            node._policy = RetryEverything()
            gh = _GoalHandle(RunDemo.Goal())
            gh.request.scenario_id = 'it_send_timeout'
            result = node._execute_demo(gh)
            self.assertEqual(result.outcome, RunDemo.Result.OUTCOME_FAILED)
            self.assertEqual(result.error_code, RunDemo.Result.ERR_SKILL_FAILED)
            self.assertIn('skill transport failure', result.detail)
            self.assertEqual(node._policy.invocations, 1)
            self.assertEqual(calls, ['OBSERVE_A'])
            record = json.loads(next(__import__('pathlib').Path(tmp).glob('it_send_timeout_*.json')).read_text())
            self.assertEqual(len(record['steps']), 1)
            self.assertIsNone(record['steps'][0]['executor_result']['outcome'])
            self.assertIn('goal send timeout', record['steps'][0]['executor_result']['detail'])

    def test_unconfirmed_skill_blocks_a_following_task(self):
        with tempfile.TemporaryDirectory(prefix='fx_send_busy_') as tmp:
            calls = []
            node = _make_fsm(tmp, lambda *args: calls.append(args))
            node._pending_skill_sends = {'unknown': object()}
            states = []
            node._publish_task_state = states.append
            gh = _GoalHandle(RunDemo.Goal())
            result = node._execute_demo(gh)
            self.assertEqual(result.error_code, RunDemo.Result.ERR_RESOURCE_BUSY)
            self.assertEqual(calls, [])
            self.assertNotIn('IDLE', states)

    def test_quarantine_is_checked_after_acquiring_task_admission(self):
        with tempfile.TemporaryDirectory(prefix='fx_send_race_') as tmp:
            calls = []
            node = _make_fsm(tmp, lambda *args: calls.append(args))
            lock = threading.Lock()

            class Admission:
                def acquire(self, blocking=False):
                    # The previous owner quarantines its goal before releasing
                    # admission; checking before this acquire would miss it.
                    node._pending_skill_sends = {'late': object()}
                    return lock.acquire(blocking=blocking)

                def release(self):
                    lock.release()

            node._admission = Admission()
            result = node._execute_demo(_GoalHandle(RunDemo.Goal()))
            self.assertEqual(result.error_code, RunDemo.Result.ERR_RESOURCE_BUSY)
            self.assertEqual(calls, [])
            self.assertFalse(lock.locked())

    def test_result_read_exception_quarantines_accepted_goal(self):
        node = TaskFsmServer.__new__(TaskFsmServer)
        node._pending_skill_sends = {}
        node._send_guard_lock = threading.Lock()
        cancels = []

        def fail_read():
            raise RuntimeError('result transport failed')

        handle = SimpleNamespace(get_result_async=fail_read,
                                 cancel_goal_async=lambda: cancels.append(True), accepted=True)
        result, error = node._wait_skill_result(handle, 'PICK', 1)
        self.assertIsNone(result)
        self.assertIn('result/stop unconfirmed', error)
        self.assertTrue(node._has_pending_skill_goal())
        # Cleanup on the original handle attempts cancellation; no new goal.
        self.assertFalse(next(iter(node._pending_skill_sends.values())).poll())
        self.assertEqual(cancels, [True])

    def test_cancel_exception_keeps_blocked_until_terminal_result(self):
        node = TaskFsmServer.__new__(TaskFsmServer)
        node._pending_skill_sends = {}
        node._send_guard_lock = threading.Lock()
        reply = SimpleNamespace(ready=False, response=None)
        future = SimpleNamespace(done=lambda: reply.ready, result=lambda: reply.response)

        def fail_cancel():
            raise RuntimeError('cancel transport failed')

        handle = SimpleNamespace(get_result_async=lambda: future, cancel_goal_async=fail_cancel)
        result, error = node._wait_skill_result(handle, 'OBSERVE', -1)
        self.assertIsNone(result)
        self.assertIn('result/stop unconfirmed', error)
        cleanup = next(iter(node._pending_skill_sends.values()))
        self.assertFalse(cleanup.poll())
        reply.ready = True
        reply.response = SimpleNamespace(status=5)
        self.assertTrue(cleanup.poll())


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


if __name__ == '__main__':
    unittest.main()
