#!/usr/bin/env python3
"""FlexCell deterministic pick-and-place task FSM (Week 1; policy seam since #4).

Strict sequential task over the four skills:

    OBSERVE -> PICK -> PLACE -> VERIFY

The task decisions (sequencing, recoverability, retry budgeting) are ROUTED
through the DecisionPolicy interface (issue #4, ADR-002): the executor asks
`FSMPolicy.decide()` at every decision point and consumes the returned
`Decision` objects. With the default `decision_policy=fsm` the policy encodes
exactly the frozen Week-1.5 semantics, so behavior is trace-equivalent (B5).
Every decision is logged to `decisions.jsonl` with evidence references
(world revision + observe evidence id + decide latency).

FSMPolicy remains the default reference arm. Jev, LLM and Hybrid policies
use the same executor for both task actions. One task at a time (single-arm
mutual exclusion). Cancellation is
honoured between states; a canceled mid-task leaves the robot in the state the
skills left it in and reports honestly.
"""

import json
import os
import threading
import time
import uuid

import rclpy
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy

from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String as StringMsg
from unique_identifier_msgs.msg import UUID

from flexcell_interfaces.action import (
    Observe, PickObject, PlaceObject, RunComposite, RunDemo, RunPickPlace, VerifyObject)
from flexcell_interfaces.msg import ZoneState

from flexcell_skills.common import JsonlLog, crash_detail, new_evidence
from flexcell_skills.skill_contract import (
    check_pick, check_place, check_verify)
from flexcell_skills.canonical_state import serialize_envelope
from flexcell_skills.contracts.error_codes import task_abort_error_code
from flexcell_skills.contracts.action_result import AcceptedGoalResult
from flexcell_skills.contracts.goal_response import LateGoalCleanup
from flexcell_skills.contracts.backend_health import startup_health
from flexcell_skills.contracts.composite import CompositeError, Journal, prepare_plan, execute as execute_composite
from flexcell_skills.contracts.composite_checkpoint import load_checkpoint, claim_checkpoint

from flexcell_skills.contracts.episode import EpisodeRecorder, EpisodeStore
from flexcell_skills.contracts.benchmark_protocol import load_protocol
from flexcell_skills.contracts.safety_gate import (
    metrics as safety_metrics, sanitize as sanitize_decision, validate)
from flexcell_skills.contracts.recovery import (
    RECIPE_PICK, RECIPE_VERIFY, recovery_eligible)
from flexcell_skills.contracts.skill_result import previous_skill_result
from flexcell_skills.decision_policy import (
    ACTION_ABORT, ACTION_OBSERVE, ACTION_PICK, ACTION_PLACE, ACTION_VERIFY,
    Constraints, Decision, FSMPolicy, HistoryRecord, PolicyStateError,
    TaskGoal, RC_BUDGET_EXHAUSTED, RC_OBSERVE_FAILED, RC_RECOVERABLE_RETRY,
    RC_VERIFY_BUDGET_EXHAUSTED, RC_VERIFY_MISMATCH_RETRY)

R = RunPickPlace.Result


class SkillTransportError(RuntimeError):
    """An unknown skill result must not become another policy dispatch."""


class ComponentGoal:
    """Internal native goal sharing the parent's cancellation and arm lease."""
    def __init__(self, parent, request, goal_uuid, stage_id, started, completed=0):
        self.parent, self.request = parent, request
        self.goal_id = UUID(uuid=list(bytes.fromhex(goal_uuid)))
        self.stage_id, self.started, self.completed = stage_id, started, completed
        self.terminal_status = None

    @property
    def is_cancel_requested(self):
        return self.parent.is_cancel_requested

    def publish_feedback(self, feedback):
        fb = RunComposite.Feedback()
        fb.stage_id, fb.state = self.stage_id, feedback.state
        fb.completed_stages = self.completed
        fb.elapsed_ms = int((time.monotonic() - self.started) * 1000)
        self.parent.publish_feedback(fb)

    def succeed(self):
        self.terminal_status = 'SUCCEEDED'

    def canceled(self):
        self.terminal_status = 'CANCELED'

    def abort(self):
        self.terminal_status = 'FAILED'


def err_name(cls, prefix, value):
    for k, v in vars(cls).items():
        if k.startswith(prefix) and isinstance(v, int) and v == value:
            return k
    return str(value)


def _parse_planted(spec):
    """Test-hook parser (issue #6 AC): "ACTION[:target]" -> planted Decision.

    Read PER RUN from the plant_out_of_contract parameter, so a runtime
    `ros2 param set` arms the deterministic out-of-contract proposal for the
    next demo.  Empty/None -> no planting.
    """
    spec = str(spec or '').strip()
    if not spec:
        return None
    action, _, target = spec.partition(':')
    return Decision(action.strip(), target.strip() or '',
                    explanation='planted out-of-contract proposal (issue #6 AC)')


class TaskFsmServer(Node):

    def __init__(self):
        super().__init__('task_fsm_server')

        self.declare_parameter('observe_action', '/observe')
        self.declare_parameter('pick_action', '/pick_object')
        self.declare_parameter('place_action', '/place_object')
        self.declare_parameter('verify_action', '/verify_object')
        self.declare_parameter('default_place_tolerance_m', 0.05)
        self.declare_parameter('skill_wait_s', 90.0)
        self.declare_parameter('log_dir', '~/.ros/flexcell')
        self.declare_parameter('log_file', 'task_fsm.jsonl')

        gp = self.get_parameter
        self._cli_observe = ActionClient(self, Observe, gp('observe_action').value,
                                         callback_group=ReentrantCallbackGroup())
        self._cli_pick = ActionClient(self, PickObject, gp('pick_action').value,
                                      callback_group=ReentrantCallbackGroup())
        self._cli_place = ActionClient(self, PlaceObject, gp('place_action').value,
                                       callback_group=ReentrantCallbackGroup())
        self._cli_verify = ActionClient(self, VerifyObject, gp('verify_action').value,
                                        callback_group=ReentrantCallbackGroup())
        self._tol = float(gp('default_place_tolerance_m').value)
        self._skill_wait = float(gp('skill_wait_s').value)
        self._log = JsonlLog(self, gp('log_dir').value, gp('log_file').value)
        self._skill_transport_log = JsonlLog(self, gp('log_dir').value,
                                             'skill_transport.jsonl')
        self._pending_skill_sends = {}
        self._send_guard_lock = threading.Lock()
        self.create_timer(.1, self._poll_late_skill_goals,
                          callback_group=ReentrantCallbackGroup())

        # one atomic admission gate for BOTH task actions - they drive the
        # same arm (audit P1-3: the old per-action check-then-set flags were
        # racy and mutually blind; RunDemo and RunPickPlace could run
        # concurrently on one robot)
        self._admission = threading.Lock()
        self._seq = 0

        self._server = ActionServer(
            self, RunPickPlace, 'run_pick_place',
            execute_callback=self._execute,
            goal_callback=lambda req: GoalResponse.ACCEPT,
            cancel_callback=lambda gh: CancelResponse.ACCEPT,
            callback_group=ReentrantCallbackGroup())

        # ---------------- Week-1.5 demo task (policy seam since #4) ----------------
        self.declare_parameter('object_a', 'target_box_a')
        self.declare_parameter('object_b', 'target_box_b')
        self.declare_parameter('zone_1_x', 0.12)
        self.declare_parameter('zone_1_y', -0.15)
        self.declare_parameter('zone_1_z', 0.0175)
        self.declare_parameter('zone_2_x', 0.25)
        self.declare_parameter('zone_2_y', 0.05)
        self.declare_parameter('zone_2_z', 0.0175)
        self.declare_parameter('recovery_budget', 1)
        self.declare_parameter('demo_verify_tolerance_m', 0.06)
        self.declare_parameter('demo_log_file', 'demo_runs.jsonl')
        self.declare_parameter('episode_dir', '~/.ros/flexcell/episodes')
        self.declare_parameter('task_state_topic', '/flexcell/task_state')
        self.declare_parameter('decision_policy', 'fsm')
        self.declare_parameter('jev_backend', 'local')
        self.declare_parameter('hybrid_threshold', 0.7)
        self.declare_parameter('decision_log_file', 'decisions.jsonl')
        # test hook (issue #6 AC): "ACTION[:target]" - the FIRST decision the
        # executor receives is replaced by this planted out-of-contract
        # proposal, so the safety gate's rejection is demonstrable end-to-end
        self.declare_parameter('plant_out_of_contract', '')

        gp2 = self.get_parameter
        self._obj_a = gp2('object_a').value
        self._obj_b = gp2('object_b').value
        self._zones = {
            'zone_1': (float(gp2('zone_1_x').value), float(gp2('zone_1_y').value),
                       float(gp2('zone_1_z').value)),
            'zone_2': (float(gp2('zone_2_x').value), float(gp2('zone_2_y').value),
                       float(gp2('zone_2_z').value)),
        }
        self._budget = int(gp2('recovery_budget').value)
        self._demo_tol = float(gp2('demo_verify_tolerance_m').value)
        self._demo_log = JsonlLog(self, gp2('log_dir').value,
                                  gp2('demo_log_file').value)
        self._episodes = EpisodeStore(gp2('episode_dir').value,
                                      self.get_logger())
        protocol, digest = load_protocol()
        self._benchmark_protocol = {'id': protocol['protocol_id'],
                                    'version': protocol['protocol_version'],
                                    'sha256': digest}

        policy_name = gp2('decision_policy').value
        if policy_name == 'fsm':
            self._policy = FSMPolicy()
        elif policy_name in ('jev', 'llm', 'hybrid'):
            # issue #10 (ratified ④): backend-agnostic fast policy with typed
            # policy_failure -> FSM fallback (degradation, not deadlock)
            from flexcell_skills.jev_backends import make_backend
            from flexcell_skills.jev_policy import JevPolicy
            from flexcell_skills.hybrid_policy import HybridRouter, LLMPolicy
            backend = make_backend(str(gp2('jev_backend').value))
            ok, detail = startup_health(backend, str(gp2('jev_backend').value))
            if not ok:
                self.get_logger().warn(
                    'jev backend %r unavailable (%s) - fast path will '
                    'fall back or escalate according to the selected policy' % (
                        gp2('jev_backend').value, detail))
            else:
                self.get_logger().info('jev backend %r startup: %s' % (
                    gp2('jev_backend').value, detail))
            fast = JevPolicy(backend, fallback=FSMPolicy())
            slow = LLMPolicy(fallback=FSMPolicy())
            self._policy = (fast if policy_name == 'jev' else
                            slow if policy_name == 'llm' else
                            HybridRouter(fast, slow,
                                         threshold=gp2('hybrid_threshold').value))
        else:
            raise ValueError(
                'unknown decision_policy %r (fsm|jev|llm|hybrid)' % policy_name)
        self._decision_log = JsonlLog(self, gp2('log_dir').value,
                                      gp2('decision_log_file').value)

        # latched task state so lifecycle reset / diagnostics can read it
        qos = QoSProfile(depth=1)
        qos.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL
        qos.reliability = QoSReliabilityPolicy.RELIABLE
        self._state_pub = self.create_publisher(
            StringMsg, gp2('task_state_topic').value, qos)
        self._publish_task_state('IDLE')

        self._demo_server = ActionServer(
            self, RunDemo, 'run_demo',
            execute_callback=self._execute_demo,
            goal_callback=lambda req: GoalResponse.ACCEPT,
            cancel_callback=lambda gh: CancelResponse.ACCEPT,
            callback_group=ReentrantCallbackGroup())

        self._composite_dir = os.path.join(os.path.expanduser(gp('log_dir').value), 'composites')
        self._composite_server = ActionServer(
            self, RunComposite, 'run_composite',
            execute_callback=self._execute_composite,
            goal_callback=lambda req: GoalResponse.ACCEPT,
            cancel_callback=lambda gh: CancelResponse.ACCEPT,
            callback_group=ReentrantCallbackGroup())

        self.get_logger().info(
            'Task FSM v3 up | demo: %s->zone_1, %s->zone_2 | recovery budget=%d | '
            'policy=%s v%s' % (self._obj_a, self._obj_b, self._budget,
                               self._policy.name, self._policy.version))

    def _publish_task_state(self, state):
        self._state_pub.publish(StringMsg(data=state))

    def _has_pending_skill_goal(self):
        return bool(getattr(self, '_pending_skill_sends', {}))

    def _poll_late_skill_goals(self):
        with self._send_guard_lock:
            for goal_id, cleanup in list(self._pending_skill_sends.items()):
                if cleanup.poll():
                    del self._pending_skill_sends[goal_id]
            if (not self._pending_skill_sends and getattr(self, '_late_goal_blocked', False)
                    and self._admission.acquire(blocking=False)):
                try:
                    self._late_goal_blocked = False
                    self._publish_task_state('IDLE')
                finally:
                    self._admission.release()

    def _send_skill_goal(self, cli, goal, label, timeout_s=15.0):
        goal_id = uuid.uuid4()
        message_id = UUID(uuid=list(goal_id.bytes))
        run_id = getattr(self, '_active_task_run_id', None)
        started = time.monotonic_ns()

        def emit(**fields):
            log = getattr(self, '_skill_transport_log', None)
            if log is not None:
                log.write(dict(task_run_id=run_id, goal_uuid=goal_id.hex,
                               label=label, mono_ns=time.monotonic_ns(),
                               elapsed_ms=(time.monotonic_ns()-started)/1e6,
                               **fields))

        def quarantine(future, detail, event):
            emit(event=event, acceptance='UNKNOWN')
            cleanup = LateGoalCleanup(future, emit)
            with self._send_guard_lock:
                self._pending_skill_sends[goal_id.hex] = cleanup
                self._late_goal_blocked = True
            return None, detail

        emit(event='goal_send_requested')
        try:
            send = cli.send_goal_async(goal, goal_uuid=message_id)
        except Exception as exc:
            return quarantine(None, '%s goal send error: %s' % (label, type(exc).__name__),
                              'goal_send_error')
        deadline = time.monotonic() + timeout_s
        while not send.done():
            if time.monotonic() >= deadline:
                return quarantine(send, '%s goal send timeout' % label, 'goal_send_timeout')
            time.sleep(.02)
        try:
            handle = send.result()
        except Exception as exc:
            return quarantine(send, '%s goal response error: %s' % (label, type(exc).__name__),
                              'goal_response_error')
        if handle is None:
            return quarantine(send, '%s goal response unknown' % label, 'goal_response_unknown')
        emit(event='goal_response', accepted=bool(handle and handle.accepted))
        if handle is None or not handle.accepted:
            return None, '%s goal rejected' % label
        return handle, None

    def _guard_canceled_skill(self, handle, result_read, label):
        goal_id = getattr(handle, 'goal_id', None)
        goal_uuid = bytes(goal_id.uuid).hex() if goal_id is not None else None
        run_id = getattr(self, '_active_task_run_id', None)

        def emit(**fields):
            log = getattr(self, '_skill_transport_log', None)
            if log is not None:
                log.write(dict(task_run_id=run_id, goal_uuid=goal_uuid, label=label,
                               mono_ns=time.monotonic_ns(), **fields))

        emit(event='cancel_stop_unconfirmed')
        with self._send_guard_lock:
            cleanup = (LateGoalCleanup.after_cancel(result_read, emit)
                       if result_read is not None else LateGoalCleanup.for_accepted(handle, emit))
            self._pending_skill_sends[goal_uuid or id(handle)] = cleanup
            self._late_goal_blocked = True

    def _wait_skill_result(self, handle, label, deadline_s, goal_handle=None):
        reader = None
        cancel_attempted = False
        started = time.monotonic()
        try:
            reader = AcceptedGoalResult(handle)
            while not reader.done():
                if goal_handle is not None and goal_handle.is_cancel_requested:
                    cancel_attempted = True
                    handle.cancel_goal_async()
                    cancel_started = time.monotonic()
                    while not reader.done() and time.monotonic() - cancel_started < 15.0:
                        time.sleep(.05)
                    if not reader.done():
                        self._guard_canceled_skill(handle, reader, label)
                        return None, '%s canceled: stop confirmation timeout' % label
                    break
                if time.monotonic() - started > deadline_s:
                    cancel_attempted = True
                    handle.cancel_goal_async()
                    self._guard_canceled_skill(handle, reader, label)
                    return None, '%s result timeout (cancel sent)' % label
                time.sleep(.05)
            response = reader.result()
            if response.status not in (4, 5, 6):
                raise RuntimeError('skill result is not terminal')
            return response.result, None
        except Exception as exc:
            self._guard_canceled_skill(handle, reader, label)
            if reader is not None and not cancel_attempted:
                try:
                    handle.cancel_goal_async()
                except Exception:
                    pass  # Quarantine remains until a terminal result is known.
            return None, '%s result/stop unconfirmed: %s' % (label, type(exc).__name__)

    def _call_skill(self, cli, goal, state, trace, rec, deadline_s, goal_handle=None, t0=None):
        """Call one skill; returns (result, None) or (None, detail)."""
        trace.append(state)
        if goal_handle is not None:
            fb = RunPickPlace.Feedback()
            fb.state = state
            fb.elapsed_ms = int((time.monotonic() - t0) * 1000) if t0 else 0
            goal_handle.publish_feedback(fb)
        if not cli.wait_for_server(timeout_sec=10.0):
            return None, '%s skill server unavailable' % state
        gh, error = self._send_skill_goal(cli, goal, state)
        if error:
            return None, error
        result, error = self._wait_skill_result(gh, state, deadline_s, goal_handle)
        if error:
            return None, error
        rec['%s_result' % state.lower()] = {
            'outcome': int(result.outcome),
            'error_code': int(getattr(result, 'error_code', 0)),
            'detail': getattr(result, 'detail', ''),
        }
        return result, None

    def _execute(self, goal_handle):
        """Single-object tasks use the same policy/skill seam as RunDemo."""
        return self._execute_plan(goal_handle, single=True)

    # =================================================================
    # Week-1.5 demo task, policy-driven (issue #4 / ADR-002):
    #   decisions come from FSMPolicy (frozen Week-1.5 semantics) at every
    #   decision point; the executor gates, dispatches, records. Bounded
    #   recovery: recoverable pick failures get REOBSERVE + one retry
    #   (budget=1); place failures abort; verify mismatches get one
    #   re-verification. Every decision lands in decisions.jsonl with
    #   evidence references; every step lands in the demo evidence JSONL.
    # =================================================================

    def _demo_call(self, cli, goal, label, goal_handle, t0, deadline_s):
        """Run one skill for the demo; returns (result, None) or (None, err_detail)."""
        if goal_handle is not None:
            fb_type = (RunPickPlace.Feedback if isinstance(
                goal_handle.request, RunPickPlace.Goal) else RunDemo.Feedback)
            fb = fb_type()
            fb.state = label
            fb.elapsed_ms = int((time.monotonic() - t0) * 1000)
            goal_handle.publish_feedback(fb)
        if not cli.wait_for_server(timeout_sec=10.0):
            return None, '%s skill server unavailable' % label
        gh, error = self._send_skill_goal(cli, goal, label)
        if error:
            return None, error
        return self._wait_skill_result(gh, label, deadline_s, goal_handle)

    def _execute_demo(self, goal_handle):
        return self._execute_plan(goal_handle, single=False)

    def _execute_composite(self, goal_handle):
        """Hold the common arm admission gate across the entire outer chain."""
        started = time.monotonic()
        res = RunComposite.Result()
        res.outcome, res.error_code = res.OUTCOME_FAILED, res.ERR_INTERNAL
        res.run_id = 'composite-' + uuid.uuid4().hex[:16]
        journal, owns_arm = None, False
        progress = []
        try:
            journal = Journal(self._composite_dir, res.run_id, dict(
                goal_uuid=bytes(goal_handle.goal_id.uuid).hex(),
                runtime_fingerprint=os.environ.get('FLEXCELL_RUNTIME_FINGERPRINT'),
                policy=self._policy.name, policy_version=self._policy.version, contract_version=2))
            res.evidence_id = str(journal.path)
            if not self._admission.acquire(blocking=False):
                res.error_code, res.detail = res.ERR_RESOURCE_BUSY, 'another task owns the arm'
                journal.emit('TERMINAL', outcome=1, error_code=res.error_code, detail=res.detail)
            else:
                owns_arm = True
                self._active_task_run_id = res.run_id
                self._publish_task_state('BUSY')
                if self._has_pending_skill_goal():
                    res.error_code, res.detail = res.ERR_RESOURCE_BUSY, 'skill acceptance or stop confirmation is unknown'
                    journal.emit('TERMINAL', outcome=1, error_code=res.error_code, detail=res.detail)
                else:
                    goal = goal_handle.request
                    def xyz(p):
                        return [p.x, p.y, p.z]
                    names = [p.object_name for p in goal.initial_objects]
                    if len(names) != len(set(names)):
                        raise ValueError('duplicate initial objects')
                    stages = []
                    for stage in goal.stages:
                        pose = stage.place_pose
                        q = pose.pose.orientation
                        if pose.header.frame_id != 'world' or [q.x, q.y, q.z, q.w] != [0., 0., 0., 1.]:
                            raise ValueError('stages require world frame and identity orientation')
                        stages.append(dict(stage_id=stage.stage_id, object_name=stage.object_name,
                                           destination=xyz(pose.pose.position)))
                    plan = dict(scenario_id=goal.scenario_id, initial_objects={p.object_name:xyz(p.position) for p in goal.initial_objects},
                                stages=stages, final_empty_positions=[xyz(p) for p in goal.final_empty_positions],
                                position_tolerance_m=goal.position_tolerance_m, clearance_m=goal.clearance_m,
                                motion_profile_id=goal.motion_profile_id)
                    plan = prepare_plan(plan)
                    checkpoint = None
                    if goal.resume_run_id or goal.resume_receipt_sha256:
                        if goal.pause_after_stages:
                            raise CompositeError(65, 'resume must finish the remaining chain')
                        try:
                            checkpoint = load_checkpoint(self._composite_dir, goal.resume_run_id, goal.resume_receipt_sha256,
                                                         plan, os.environ.get('FLEXCELL_RUNTIME_FINGERPRINT'), self._episodes._dir)
                        except (ValueError, KeyError, TypeError, OSError) as exc:
                            raise CompositeError(65, 'checkpoint rejected: ' + str(exc))
                        if checkpoint['policy'] != self._policy.name or checkpoint['policy_version'] != self._policy.version:
                            raise CompositeError(65, 'checkpoint policy identity mismatch')
                        checkpoint['claim'] = claim_checkpoint(self._composite_dir, checkpoint, res.run_id)
                        res.resumed_from_run_id = checkpoint['source_run_id']
                        res.inherited_stages = len(checkpoint['completed_stage_ids'])
                        progress.extend(checkpoint['completed_stage_ids'])
                    def emit(event, **data):
                        journal.emit(event, **data)
                        if event == 'COMMITTED':
                            progress.append(data['stage_id'])
                    def observe(stage_id, boundary):
                        view = ComponentGoal(goal_handle, RunPickPlace.Goal(), uuid.uuid4().hex, stage_id, started, len(progress))
                        request = Observe.Goal(); request.refresh = True
                        reply, error = self._demo_call(self._cli_observe, request, 'OBSERVE_' + boundary.upper(), view, started, self._skill_wait)
                        if reply is None:
                            raise SkillTransportError(error)
                        ws = reply.world_state
                        return dict(outcome=int(reply.outcome), error_code=int(reply.error_code), evidence_id=reply.evidence_id,
                                    source=ws.source, revision=int(ws.revision),
                                    carry=dict(engaged=bool(ws.carry.engaged), object_id=ws.carry.object_id),
                                    objects=[dict(name=o.name, available=bool(o.available), position=xyz(o.pose.position)) for o in ws.objects])
                    def native(stage, goal_uuid):
                        request = RunPickPlace.Goal()
                        request.object_name, request.motion_profile_id = stage['object_name'], plan['motion_profile_id']
                        request.place_pose.header.frame_id = 'world'
                        request.place_pose.pose.orientation.w = 1.
                        p = request.place_pose.pose.position
                        p.x, p.y, p.z = map(float, stage['destination'])
                        request.skip_verify = False
                        context = dict(parent_run_id=res.run_id, stage_id=stage['stage_id'])
                        view = ComponentGoal(goal_handle, request, goal_uuid, stage['stage_id'], started, len(progress))
                        result = self._execute_plan(view, single=True, admission_held=True, component=context)
                        self._active_task_run_id = res.run_id
                        return dict(context, goal_uuid=goal_uuid, terminal_status=view.terminal_status,
                                    outcome=int(result.outcome), error_code=int(result.error_code), detail=result.detail,
                                    object_at_place=bool(result.object_at_place), final_position_error_m=result.final_position_error_m)
                    result = execute_composite(plan, observe, native, emit, lambda: goal_handle.is_cancel_requested,
                                               pause_after_stages=int(goal.pause_after_stages), checkpoint=checkpoint)
                    for field in ('outcome', 'error_code', 'detail', 'completed_stage_ids', 'component_run_ids', 'component_goal_uuids'):
                        setattr(res, field, result[field])
        except Exception as exc:
            res.outcome = res.OUTCOME_FAILED
            res.error_code = exc.code if isinstance(exc, CompositeError) else res.ERR_INVALID_PLAN if isinstance(exc, ValueError) else res.ERR_INTERNAL
            res.detail = crash_detail(exc)
            if journal is not None:
                try:
                    journal.emit('TERMINAL', outcome=int(res.outcome), error_code=int(res.error_code), detail=res.detail)
                except Exception as log_exc:
                    self.get_logger().error('composite receipt failed: %s' % log_exc)
        finally:
            if owns_arm:
                self._publish_task_state('BUSY' if self._has_pending_skill_goal() else 'IDLE')
                self._admission.release()
            if journal is not None:
                try:
                    journal.close()
                except Exception as exc:
                    res.outcome, res.error_code, res.detail = res.OUTCOME_FAILED, res.ERR_INTERNAL, crash_detail(exc)
        if res.outcome in (res.OUTCOME_SUCCEEDED, res.OUTCOME_PAUSED):
            goal_handle.succeed()
        elif res.outcome == res.OUTCOME_CANCELED:
            goal_handle.canceled()
        else:
            goal_handle.abort()
        return res

    def _execute_plan(self, goal_handle, single=False, admission_held=False, component=None):
        t0 = time.monotonic()
        goal = goal_handle.request
        self._seq += 1
        scenario = ('pick_place_v1' if single else
                    goal.scenario_id or 'week1_demo_v1')
        result_type = RunPickPlace.Result if single else RunDemo.Result
        owns_arm = False
        zones = dict(self._zones)
        if single:
            pp = goal.place_pose.pose.position
            zones['task_place'] = (pp.x, pp.y, pp.z)
        run_id = '%s-%s' % (scenario, uuid.uuid4().hex[:8])
        _, evidence = new_evidence(scenario, self._seq)
        trace = []
        steps = []
        res = result_type()
        verify_results = {}
        # episode recorder (issue #7 / §4.4): the exact policy input at every
        # decide() call, persisted for offline policy-input replay
        episode = EpisodeRecorder(scenario, run_id, self._policy.name,
                                  self._policy.version)
        # safety-gate accounting (issue #6): per-run, executor-owned counters
        safety_evaluated = 0
        safety_rejected = 0
        planted = _parse_planted(
            self.get_parameter('plant_out_of_contract').value)
        if planted is not None:
            self.get_logger().warn(
                'SAFETY TEST HOOK armed: first decision will be planted '
                '(%r -> %r)' % (planted.action, planted.target))
        planted_used = False

        def finish(outcome, error, detail):
            res.outcome, res.error_code = outcome, error
            res.detail, res.fsm_trace, res.evidence_id = detail, trace, evidence
            duration_s = time.monotonic() - t0
            final = {
                'outcome': str(outcome), 'error_code': int(error),
                'detail': detail, 'fsm_trace': list(trace),
                'duration_s': duration_s, 'evidence_id': evidence,
                'safety': safety_metrics(safety_evaluated, safety_rejected),
            }
            ros_goal = getattr(goal_handle, 'goal_id', None)
            if ros_goal is not None:
                final['goal_uuid'] = bytes(ros_goal.uuid).hex()
            if component is not None:
                final.update(parent_run_id=component['parent_run_id'], stage_id=component['stage_id'],
                             execution_kind='IN_PROCESS_COMPONENT', component_execution_id=final.get('goal_uuid'))
            if single:
                vr = verify_results.get('a')
                res.object_at_place = bool(
                    (vr is not None and int(vr.outcome) == 0) or
                    (goal.skip_verify and outcome == result_type.OUTCOME_SUCCEEDED))
                res.final_position_error_m = (
                    float(vr.position_error_m)
                    if vr is not None and vr.has_measured_pose else float('nan'))
                final.update(object_at_place=res.object_at_place,
                             final_position_error_m=res.final_position_error_m)
            else:
                res.scenario_id, res.run_id = scenario, run_id
                res.duration_s = duration_s
                for tag in ('a', 'b'):
                    vr = verify_results.get(tag)
                    v_ok = vr is not None and int(vr.outcome) == 0
                    setattr(res, 'object_%s_at_zone' % tag, bool(v_ok))
                    setattr(res, 'zone_%s_error_m' % tag,
                            float(vr.position_error_m)
                            if vr is not None and vr.has_measured_pose
                            else float('nan'))
                    final['object_%s_at_zone' % tag] = bool(v_ok)
                    final['zone_%s_error_m' % tag] = getattr(
                        res, 'zone_%s_error_m' % tag)
            episode.drop_pending()
            episode_path = self._episodes.write(episode.to_dict(
                final_state=final, protocol=getattr(self, '_benchmark_protocol', None)))
            if component is not None:
                component.update(run_id=run_id, final_state=final, episode_path=episode_path)
            log_record = dict(final, scenario_id=scenario, run_id=run_id,
                              steps=steps)
            if single:
                log_record.update(object_name=goal.object_name,
                                  place=list(zones['task_place']))
                self._log.write(log_record)
            else:
                self._demo_log.write(log_record)
            if owns_arm:
                self._publish_task_state('BUSY' if self._has_pending_skill_goal() else 'IDLE')
            if outcome == result_type.OUTCOME_SUCCEEDED:
                goal_handle.succeed()
            elif outcome == result_type.OUTCOME_CANCELED:
                goal_handle.canceled()
            else:
                goal_handle.abort()
            return res

        if not admission_held and not self._admission.acquire(blocking=False):
            return finish(result_type.OUTCOME_FAILED,
                          result_type.ERR_RESOURCE_BUSY,
                          'another demo task is active')
        owns_arm = not admission_held
        self._active_task_run_id = run_id
        self._publish_task_state('BUSY')
        try:
            if self._has_pending_skill_goal():
                return finish(result_type.OUTCOME_FAILED,
                              result_type.ERR_RESOURCE_BUSY,
                              'skill goal acceptance or stop confirmation is unknown')
            if single and not goal.object_name:
                return finish(result_type.OUTCOME_FAILED, result_type.ERR_OBJECT_UNKNOWN,
                              'object_name is empty')
            # ---- decision inputs (ADR-002: executor assembles, policy decides) ----
            goal_obj = TaskGoal(
                goal_id=run_id,
                scenario_id=scenario,
                assignments=(((goal.object_name, 'task_place'),) if single else
                             ((self._obj_a, 'zone_1'), (self._obj_b, 'zone_2'))),
            )
            constraints = Constraints(
                allowed_actions=frozenset((
                    ACTION_OBSERVE, ACTION_PICK, ACTION_PLACE, ACTION_VERIFY,
                    'WAIT', ACTION_ABORT)),
                recovery_budget=self._budget,
                verify_tolerance_m=(self._tol if single else self._demo_tol),
                motion_profile_id=(goal.motion_profile_id or 'demo_slow'
                                   if single else 'demo_slow'),
                max_world_age_s=0.0,
            )
            zone_of = dict(goal_obj.assignments)
            world = None
            history = []
            decision_seq = 0
            tag = 'A'
            attempt = 1
            vattempt = 1
            last_world_revision = 0
            last_observe_evidence = ''
            last_fail_label = ''

            def call_skill(cli, request, label, deadline):
                result, error = self._demo_call(cli, request, label, goal_handle, t0, deadline)
                if error:
                    episode.record_executor_result(detail=error)
                    steps.append(dict(state=label, ok=False, error=error,
                                      transport_failure=True))
                    raise SkillTransportError(error)
                return result, error

            def tag_of(object_id):
                return 'A' if single or object_id == self._obj_a else 'B'

            while True:
                # cancellation is honoured at decision boundaries (the original
                # demo loop never checked it - safety delta, documented in #4)
                if goal_handle.is_cancel_requested:
                    return finish(result_type.OUTCOME_CANCELED,
                                  result_type.ERR_CANCELED,
                                  'canceled (trace=%s)' % ','.join(trace))
                # completion is structural (all assignments verified), not a decision
                verified_targets = {d.target for d in history
                                    if d.action == ACTION_VERIFY and d.outcome == 0}
                if single and goal.skip_verify:
                    verified_targets = {d.target for d in history
                                        if d.action == ACTION_PLACE and d.outcome == 0}
                if {obj for obj, _ in goal_obj.assignments} <= verified_targets:
                    if single and goal.skip_verify:
                        trace.append('VERIFY(skipped)')
                    return finish(result_type.OUTCOME_SUCCEEDED,
                                  result_type.ERR_NONE,
                                  'task done: all assignments verified')

                if decision_seq >= 64:
                    return finish(result_type.OUTCOME_FAILED, result_type.ERR_SKILL_FAILED,
                                  'executor decision limit reached (64)')
                # ---- ask the policy WHAT next ----
                # issue #7: persist the EXACT policy input before decide()
                world_canonical = (serialize_envelope(world)
                                   if world is not None else None)
                episode.begin_step(world_canonical, goal_obj, constraints,
                                   history)
                t_dec = time.perf_counter_ns()
                decision = self._policy.decide(world, goal_obj, constraints,
                                               tuple(history))
                d_ms = (time.perf_counter_ns() - t_dec) / 1_000_000.0
                if planted is not None and not planted_used:
                    # issue #6 AC test hook: the executor receives the planted
                    # out-of-contract proposal instead of the policy's output
                    decision = planted
                    planted_used = True
                episode.record_decision(decision, d_ms, clock='perf_counter_ns')

                # ---- safety gate (issue #6): deterministic, BEFORE dispatch.
                # Consumes the policy-facing view (canonical envelope), never
                # the planning-scene belief; free text cannot pass (sanitize
                # is what the dispatcher would see).
                safety_evaluated += 1
                decision_seq += 1
                # prev / recovery_audit (the policy-facing view of the last
                # skill result and the recovery context) are needed by BOTH
                # the gate's rejection record and the regular decision log -
                # compute them before the gate
                prev = (previous_skill_result(history[-1].action,
                                              history[-1].outcome,
                                              history[-1].error_code)
                        if history else None)
                recovery_audit = None
                world_dict = (json.loads(world_canonical)
                              if world_canonical is not None else None)
                gate_ok, gate_reason = validate(decision, goal_obj, world_dict,
                                                constraints)
                if not gate_ok:
                    safety_rejected += 1
                    self._decision_log.write({
                        'run_id': run_id, 'scenario_id': scenario,
                        'seq': decision_seq,
                        'previous_skill_result': prev,
                        'recovery': recovery_audit,
                        'action': decision.action, 'target': decision.target,
                        'confidence': decision.confidence,
                        'reason_code': decision.reason_code,
                        'explanation': decision.explanation,
                        'policy': self._policy.name,
                        'policy_version': self._policy.version,
                        'world_revision': last_world_revision,
                        'observe_evidence_id': last_observe_evidence,
                        'decide_latency_ms': d_ms,
                        'policy_trace': decision.policy_trace,
                        'dispatched': False,
                        'safety_rejection': gate_reason,
                    })
                    episode.record_executor_result(
                        detail='safety rejection: %s' % gate_reason,
                        post_condition='SAFETY_REJECTED')
                    return finish(result_type.OUTCOME_FAILED,
                                  result_type.ERR_SAFETY_REJECTED,
                                  'safety gate rejected %s on %r: %s'
                                  % (decision.action, decision.target,
                                     gate_reason))
                dispatch_view = sanitize_decision(decision)
                # the dispatch sites read ONLY action/target - the sanitized
                # assert proves free text (explanation) can never reach a
                # skill goal (issue #6 §2.6)
                assert dispatch_view == {'action': decision.action,
                                         'target': decision.target}
                recovery_audit = None
                if (history and decision.reason_code in (
                        RC_RECOVERABLE_RETRY, RC_VERIFY_MISMATCH_RETRY,
                        RC_BUDGET_EXHAUSTED)):
                    last_rec = history[-1]
                    recovery_audit = {
                        'recipe': (RECIPE_PICK
                                   if decision.reason_code == RC_RECOVERABLE_RETRY
                                   else (RECIPE_VERIFY
                                         if decision.reason_code == RC_VERIFY_MISMATCH_RETRY
                                         else 'BUDGET_EXHAUSTED')),
                        'eligible': recovery_eligible(
                            last_rec.action, last_rec.error_code,
                            last_rec.outcome),
                        'error_code': int(last_rec.error_code),
                        'canonical_error_code': (
                            prev['canonical_error_code'] if prev else None),
                        'attempt': (vattempt
                                    if decision.reason_code == RC_VERIFY_MISMATCH_RETRY
                                    else attempt),
                        'budget_cap': constraints.recovery_budget,
                    }
                self._decision_log.write({
                    'run_id': run_id, 'scenario_id': scenario,
                    'seq': decision_seq,
                    'previous_skill_result': prev,
                    'recovery': recovery_audit,
                    'action': decision.action, 'target': decision.target,
                    'confidence': decision.confidence,
                    'reason_code': decision.reason_code,
                    'explanation': decision.explanation,
                    'policy': self._policy.name,
                    'policy_version': self._policy.version,
                    'world_revision': last_world_revision,
                    'observe_evidence_id': last_observe_evidence,
                    'decide_latency_ms': d_ms,
                    'policy_trace': decision.policy_trace,
                    'dispatched': True,
                    'safety_rejection': None,
                })

                if decision.target and tag_of(decision.target) != tag:
                    tag = tag_of(decision.target)   # leg transition
                    attempt = 1
                    vattempt = 1

                # ---------------- OBSERVE (leg start / recovery) ----------------
                if decision.action == ACTION_OBSERVE:
                    if decision.reason_code == RC_RECOVERABLE_RETRY:
                        trace.append('RECOVERY:REOBSERVE+RETRY(after %s)' % last_fail_label)
                        label = 'REOBSERVE_%s' % tag
                    elif decision.reason_code == RC_VERIFY_MISMATCH_RETRY:
                        trace.append('RECOVERY:REOBSERVE+REVERIFY(after %s)' % last_fail_label)
                        label = 'REOBSERVE_%s' % tag
                    else:
                        label = 'OBSERVE_%s' % tag
                    og = Observe.Goal()
                    og.refresh = True
                    r, err = call_skill(self._cli_observe, og, label, 30.0)
                    o_outcome = int(r.outcome) if r is not None else 255
                    o_evidence = getattr(r, 'evidence_id', '') if r else ''
                    episode.record_executor_result(
                        outcome=(int(r.outcome) if r is not None else None),
                        error_code=(int(getattr(r, 'error_code', 0))
                                    if r is not None else None),
                        detail=(err or getattr(r, 'detail', '')),
                        evidence_id=o_evidence)
                    if decision.reason_code == RC_VERIFY_MISMATCH_RETRY:
                        # frozen behavior: the verify-path reobserve result is
                        # ignored - the re-verify decides
                        history.append(HistoryRecord(
                            action=ACTION_OBSERVE, target=decision.target,
                            outcome=o_outcome, error_code=0, attempt=vattempt,
                            world_revision=last_world_revision,
                            evidence_id=o_evidence))
                        continue
                    o_ok = (err is None and r is not None and
                            o_outcome == Observe.Result.OUTCOME_SUCCEEDED)
                    steps.append({'state': label, 'skill': 'observe',
                                  'ok': o_ok, 'error': err or '', 'attempt': attempt})
                    if err or o_outcome != Observe.Result.OUTCOME_SUCCEEDED:
                        if goal_handle.is_cancel_requested:
                            return finish(result_type.OUTCOME_CANCELED,
                                          result_type.ERR_CANCELED,
                                          'canceled during %s (trace=%s)'
                                          % (label, ','.join(trace)))
                        history.append(HistoryRecord(
                            action=ACTION_OBSERVE, target=decision.target,
                            outcome=255, error_code=-1, attempt=attempt,
                            world_revision=last_world_revision, evidence_id=''))
                        continue
                    world = r.world_state
                    if single:
                        zone = ZoneState()
                        zone.id = 'task_place'
                        zone.center.x, zone.center.y, zone.center.z = zones['task_place']
                        world.zones = [z for z in world.zones if z.id != 'task_place'] + [zone]
                    last_world_revision = int(r.world_state.revision)
                    # Observe.action carries no evidence_id field - defensive
                    # getattr keeps the decision log honest if it is added later
                    last_observe_evidence = getattr(r, 'evidence_id', '')
                    history.append(HistoryRecord(
                        action=ACTION_OBSERVE, target=decision.target,
                        outcome=0, error_code=0, attempt=attempt,
                        world_revision=last_world_revision,
                        evidence_id=getattr(r, 'evidence_id', '')))
                    continue

                # ---------------- PICK (bounded recovery via policy) ----------------
                if decision.action == ACTION_PICK:
                    attempt = 1 + sum(h.action == ACTION_PICK and
                                      h.target == decision.target for h in history)
                    if attempt > 1 + constraints.recovery_budget:
                        episode.record_executor_result(detail='executor pick budget exhausted')
                        return finish(result_type.OUTCOME_FAILED,
                                      result_type.ERR_RECOVERY_EXHAUSTED,
                                      'executor pick budget exhausted')
                    label = 'PICK_%s(attempt=%d)' % (tag, attempt)
                    pg = PickObject.Goal()
                    pg.object_name = decision.target
                    pg.motion_profile_id = constraints.motion_profile_id
                    r, err = call_skill(self._cli_pick, pg, label, 90.0)
                    pick_ok = (err is None and r is not None and
                               int(r.outcome) == PickObject.Result.OUTCOME_SUCCEEDED)
                    code = int(r.error_code) if (err is None and r is not None) else -1
                    episode.record_executor_result(
                        outcome=(int(r.outcome) if r is not None else None),
                        error_code=(code if r is not None else None),
                        detail=(err or (r.detail if r else '')),
                        evidence_id=getattr(r, 'evidence_id', '') if r else '')
                    ename = err or err_name(PickObject.Result, 'ERR_', code)
                    steps.append({'state': label, 'skill': 'pick', 'ok': pick_ok,
                                  'error': err or (r.detail if r else ''),
                                  'error_code': code, 'attempt': attempt,
                                  'evidence_id': getattr(r, 'evidence_id', '') if r else ''})
                    trace.append('%s:%s' % (label, 'OK' if pick_ok else 'FAIL:%s' % ename))
                    if pick_ok:
                        violation = check_pick(r)
                        if violation is not None:
                            steps.append({'state': label, 'skill': 'pick',
                                          'ok': False, 'error': violation,
                                          'error_code': result_type.ERR_SKILL_CONTRACT_VIOLATION,
                                          'attempt': attempt,
                                          'evidence_id': getattr(r, 'evidence_id', '')})
                            trace.append('%s:FAIL:ERR_SKILL_CONTRACT_VIOLATION' % label)
                            return finish(result_type.OUTCOME_FAILED,
                                          result_type.ERR_SKILL_CONTRACT_VIOLATION,
                                          'post-condition violation on %s: %s'
                                          % (label, violation))
                        history.append(HistoryRecord(
                            action=ACTION_PICK, target=decision.target,
                            outcome=0, error_code=0, attempt=attempt,
                            world_revision=last_world_revision,
                            evidence_id=r.evidence_id))
                        # executor-owned world update (issue #6): the pick
                        # attached the object, but the canonical world dates
                        # from the last observe - the gate's PLACE carried
                        # check needs the carry state the executor knows
                        if world is not None:
                            world.carry.engaged = True
                            world.carry.object_id = decision.target
                    else:
                        last_fail_label = label
                        if goal_handle.is_cancel_requested:
                            return finish(result_type.OUTCOME_CANCELED,
                                          result_type.ERR_CANCELED,
                                          'canceled during %s (trace=%s)'
                                          % (label, ','.join(trace)))
                        history.append(HistoryRecord(
                            action=ACTION_PICK, target=decision.target,
                            outcome=(int(r.outcome) if r is not None else 255),
                            error_code=code, attempt=attempt,
                            world_revision=last_world_revision,
                            evidence_id=getattr(r, 'evidence_id', '') if r else ''))
                    continue

                # ---------------- PLACE (failure aborts: carried box) ----------------
                if decision.action == ACTION_PLACE:
                    label = 'PLACE_%s' % tag
                    zx, zy, zz = zones[zone_of[decision.target]]
                    zone_pose = PoseStamped()
                    zone_pose.header.frame_id = 'world'
                    zone_pose.pose.position.x = zx
                    zone_pose.pose.position.y = zy
                    zone_pose.pose.position.z = zz
                    zone_pose.pose.orientation.w = 1.0
                    pg = PlaceObject.Goal()
                    pg.object_name = decision.target
                    pg.place_pose = zone_pose
                    pg.motion_profile_id = constraints.motion_profile_id
                    r, err = call_skill(self._cli_place, pg, label, 90.0)
                    place_ok = (err is None and r is not None and
                                int(r.outcome) == PlaceObject.Result.OUTCOME_SUCCEEDED)
                    episode.record_executor_result(
                        outcome=(int(r.outcome) if r is not None else None),
                        error_code=(int(r.error_code) if r is not None else None),
                        detail=(err or (r.detail if r else '')),
                        evidence_id=getattr(r, 'evidence_id', '') if r else '')
                    steps.append({'state': label, 'skill': 'place', 'ok': place_ok,
                                  'error': err or (r.detail if r else ''),
                                  'evidence_id': getattr(r, 'evidence_id', '') if r else ''})
                    trace.append('%s:%s' % (label, 'OK' if place_ok else 'FAIL'))
                    if place_ok:
                        violation = check_place(
                            r, place_position=[zx, zy, zz],
                            tolerance_m=constraints.verify_tolerance_m)
                        if violation is not None:
                            steps.append({'state': label, 'skill': 'place',
                                          'ok': False, 'error': violation,
                                          'error_code': result_type.ERR_SKILL_CONTRACT_VIOLATION,
                                          'evidence_id': getattr(r, 'evidence_id', '') if r else ''})
                            trace.append('%s:FAIL:ERR_SKILL_CONTRACT_VIOLATION' % label)
                            return finish(result_type.OUTCOME_FAILED,
                                          result_type.ERR_SKILL_CONTRACT_VIOLATION,
                                          'post-condition violation on %s: %s'
                                          % (label, violation))
                        history.append(HistoryRecord(
                            action=ACTION_PLACE, target=decision.target,
                            outcome=0, error_code=0, attempt=attempt,
                            world_revision=last_world_revision,
                            evidence_id=getattr(r, 'evidence_id', '') if r else ''))
                        # executor-owned world update (issue #6): the object
                        # was released into the zone
                        if world is not None:
                            world.carry.engaged = False
                            world.carry.object_id = ''
                            for obj in world.objects:
                                if obj.name == decision.target:
                                    obj.pose = r.object_pose_after
                                    obj.pose_age_s = 0.0
                    else:
                        if goal_handle.is_cancel_requested:
                            return finish(result_type.OUTCOME_CANCELED,
                                          result_type.ERR_CANCELED,
                                          'canceled during PLACE_%s (box state '
                                          'unchanged by the failed place; '
                                          'trace=%s)' % (tag, ','.join(trace)))
                        history.append(HistoryRecord(
                            action=ACTION_PLACE, target=decision.target,
                            outcome=(int(r.outcome) if r is not None else 255),
                            error_code=(int(r.error_code) if r is not None else -1),
                            attempt=attempt,
                            world_revision=last_world_revision,
                            evidence_id=getattr(r, 'evidence_id', '') if r else ''))
                    continue

                # ---------------- VERIFY (bounded re-verification via policy) ----------------
                if decision.action == ACTION_VERIFY:
                    vattempt = 1 + sum(h.action == ACTION_VERIFY and
                                       h.target == decision.target for h in history)
                    if vattempt > 1 + constraints.recovery_budget:
                        episode.record_executor_result(detail='executor verify budget exhausted')
                        return finish(result_type.OUTCOME_FAILED,
                                      result_type.ERR_RECOVERY_EXHAUSTED,
                                      'executor verify budget exhausted')
                    label = 'VERIFY_%s(attempt=%d)' % (tag, vattempt)
                    zx, zy, zz = zones[zone_of[decision.target]]
                    zone_pose = PoseStamped()
                    zone_pose.header.frame_id = 'world'
                    zone_pose.pose.position.x = zx
                    zone_pose.pose.position.y = zy
                    zone_pose.pose.position.z = zz
                    zone_pose.pose.orientation.w = 1.0
                    vg = VerifyObject.Goal()
                    vg.object_name = decision.target
                    vg.expected_pose = zone_pose.pose
                    vg.position_tolerance_m = constraints.verify_tolerance_m
                    r, err = call_skill(self._cli_verify, vg, label, 30.0)
                    v_ok = (err is None and r is not None and
                            int(r.outcome) == VerifyObject.Result.OUTCOME_VERIFIED)
                    episode.record_executor_result(
                        outcome=(int(r.outcome) if r is not None else None),
                        error_code=(int(getattr(r, 'error_code', 0))
                                    if r is not None else None),
                        detail=(err or getattr(r, 'detail', '')),
                        evidence_id=getattr(r, 'evidence_id', '') if r else '')
                    if v_ok:
                        violation = check_verify(r)
                        if violation is not None:
                            steps.append({'state': label, 'skill': 'verify',
                                          'ok': False, 'error': violation,
                                          'attempt': vattempt,
                                          'evidence_id': getattr(r, 'evidence_id', '')})
                            trace.append('%s:FAIL:ERR_SKILL_CONTRACT_VIOLATION' % label)
                            return finish(result_type.OUTCOME_FAILED,
                                          result_type.ERR_SKILL_CONTRACT_VIOLATION,
                                          'post-condition violation on %s: %s'
                                          % (label, violation))
                    verify_results[tag.lower()] = r
                    steps.append({'state': label, 'skill': 'verify', 'ok': v_ok,
                                  'error': err or (r.detail if r else ''),
                                  'attempt': vattempt,
                                  'position_error_m':
                                      float(r.position_error_m)
                                      if r is not None and r.has_measured_pose else None,
                                  'evidence_id': getattr(r, 'evidence_id', '') if r else ''})
                    trace.append('%s:%s' % (label, 'OK' if v_ok else 'FAIL'))
                    if v_ok:
                        history.append(HistoryRecord(
                            action=ACTION_VERIFY, target=decision.target,
                            outcome=0, error_code=0, attempt=vattempt,
                            world_revision=last_world_revision,
                            evidence_id=getattr(r, 'evidence_id', '') if r else ''))
                    else:
                        last_fail_label = label
                        if goal_handle.is_cancel_requested:
                            return finish(result_type.OUTCOME_CANCELED,
                                          result_type.ERR_CANCELED,
                                          'canceled during %s (trace=%s)'
                                          % (label, ','.join(trace)))
                        history.append(HistoryRecord(
                            action=ACTION_VERIFY, target=decision.target,
                            outcome=(int(r.outcome) if r is not None else 255),
                            error_code=(int(r.error_code) if r is not None else -1),
                            attempt=vattempt,
                            world_revision=last_world_revision,
                            evidence_id=getattr(r, 'evidence_id', '') if r else ''))
                    continue

                # ---------------- ABORT (typed policy abort) ----------------
                # The policy owns the abort verdict; the executor owns the
                # typed task code (audit P1-2: BUDGET_EXHAUSTED-class aborts
                # used to degenerate into ERR_SKILL_FAILED + "policy state
                # error" via the PolicyStateError path - the dead abort_error
                # assignments this branch replaces were its residue).
                if decision.action == ACTION_ABORT:
                    episode.record_executor_result()
                    return finish(result_type.OUTCOME_FAILED,
                                  task_abort_error_code(decision.reason_code),
                                  'policy abort (%s): %s (trace=%s)'
                                  % (decision.reason_code, decision.explanation,
                                     ','.join(trace)))

                # ---------------- WAIT / unknown ----------------
                if decision.action == 'WAIT':
                    episode.record_executor_result()
                    continue
                raise PolicyStateError(
                    'policy returned unsupported action %r' % decision.action)

        except SkillTransportError as exc:
            canceled = goal_handle.is_cancel_requested
            return finish(result_type.OUTCOME_CANCELED if canceled else result_type.OUTCOME_FAILED,
                          result_type.ERR_CANCELED if canceled else result_type.ERR_SKILL_FAILED,
                          'skill transport failure: %s' % exc)
        except PolicyStateError as exc:
            self.get_logger().error('policy state error: %s' % exc)
            return finish(result_type.OUTCOME_FAILED,
                          result_type.ERR_SKILL_FAILED,
                          'policy state error: %s' % exc)
        except Exception as exc:  # crash guard (issue #20): rclpy's fallback
            # for a raising execute callback is a default Result with
            # outcome=0 = OUTCOME_SUCCEEDED - never let that happen
            return finish(result_type.OUTCOME_FAILED,
                          result_type.ERR_SKILL_FAILED, crash_detail(exc))
        finally:
            if owns_arm:
                self._publish_task_state('BUSY' if self._has_pending_skill_goal() else 'IDLE')
                self._admission.release()


def main(args=None):
    rclpy.init(args=args)
    node = TaskFsmServer()
    ex = MultiThreadedExecutor(num_threads=6)
    ex.add_node(node)
    try:
        ex.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
