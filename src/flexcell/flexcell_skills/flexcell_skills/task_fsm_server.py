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

No LLM, no Jev - FSMPolicy is the deterministic baseline the upstream roadmap
requires. One task at a time (single-arm mutual exclusion). Cancellation is
honoured between states; a canceled mid-task leaves the robot in the state the
skills left it in and reports honestly.
"""

import json
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

from flexcell_interfaces.action import (
    Observe, PickObject, PlaceObject, RunDemo, RunPickPlace, VerifyObject)

from flexcell_skills.common import JsonlLog, crash_detail, new_evidence
from flexcell_skills.decision_policy import (
    ACTION_ABORT, ACTION_OBSERVE, ACTION_PICK, ACTION_PLACE, ACTION_VERIFY,
    Constraints, FSMPolicy, HistoryRecord, PolicyStateError, TaskGoal,
    RC_BUDGET_EXHAUSTED, RC_OBSERVE_FAILED, RC_RECOVERABLE_RETRY,
    RC_VERIFY_BUDGET_EXHAUSTED, RC_VERIFY_MISMATCH_RETRY)

R = RunPickPlace.Result


def err_name(cls, prefix, value):
    for k, v in vars(cls).items():
        if k.startswith(prefix) and isinstance(v, int) and v == value:
            return k
    return str(value)


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

        self._busy = False
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
        self.declare_parameter('task_state_topic', '/flexcell/task_state')
        self.declare_parameter('decision_policy', 'fsm')
        self.declare_parameter('decision_log_file', 'decisions.jsonl')

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
        self._demo_busy = False

        policy_name = gp2('decision_policy').value
        if policy_name != 'fsm':
            raise ValueError(
                'unknown decision_policy %r (only "fsm" is implemented; '
                'jev/llm/hybrid follow the ratified order)' % policy_name)
        self._policy = FSMPolicy()
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

        self.get_logger().info(
            'Task FSM v3 up | demo: %s->zone_1, %s->zone_2 | recovery budget=%d | '
            'policy=%s v%s' % (self._obj_a, self._obj_b, self._budget,
                               self._policy.name, self._policy.version))

    def _publish_task_state(self, state):
        self._state_pub.publish(StringMsg(data=state))

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
        send = cli.send_goal_async(goal)
        t0 = time.monotonic()
        while not send.done():
            if time.monotonic() - t0 > 15.0:
                return None, '%s goal send timeout' % state
            time.sleep(0.02)
        gh = send.result()
        if gh is None or not gh.accepted:
            return None, '%s goal rejected' % state
        rf = gh.get_result_async()
        while not rf.done():
            if time.monotonic() - t0 > deadline_s:
                gh.cancel_goal_async()
                return None, '%s result timeout (cancel sent)' % state
            time.sleep(0.05)
        result = rf.result().result
        rec['%s_result' % state.lower()] = {
            'outcome': int(result.outcome),
            'error_code': int(getattr(result, 'error_code', 0)),
            'detail': getattr(result, 'detail', ''),
        }
        return result, None

    def _execute(self, goal_handle):
        t0 = time.monotonic()
        goal = goal_handle.request
        self._seq += 1
        rid, evidence = new_evidence(goal.object_name, self._seq)
        res = R()
        trace = []
        rec = {
            'request_id': rid, 'evidence_id': evidence,
            'object_name': goal.object_name,
            'place': [goal.place_pose.pose.position.x,
                      goal.place_pose.pose.position.y,
                      goal.place_pose.pose.position.z],
        }

        def finish(outcome, error, detail):
            res.outcome = outcome
            res.error_code = error
            res.detail = detail
            res.fsm_trace = trace
            res.evidence_id = evidence
            rec.update(outcome=str(outcome), error_code=int(error), detail=detail,
                       trace=list(trace),
                       elapsed_ms=int((time.monotonic() - t0) * 1000))
            self._log.write(rec)
            if outcome == R.OUTCOME_SUCCEEDED:
                goal_handle.succeed()
            elif outcome == R.OUTCOME_CANCELED:
                goal_handle.canceled()
            else:
                goal_handle.abort()
            return res

        # ---------- admission ----------
        if self._busy:
            return finish(R.OUTCOME_FAILED, R.ERR_RESOURCE_BUSY,
                          'another task is active')
        self._busy = True
        try:
            if not goal.object_name:
                return finish(R.OUTCOME_FAILED, R.ERR_OBJECT_UNKNOWN,
                              'object_name is empty')
            pp = goal.place_pose.pose.position
            deadline_s = self._skill_wait

            # ---------- OBSERVE ----------
            if goal_handle.is_cancel_requested:
                return finish(R.OUTCOME_CANCELED, R.ERR_CANCELED,
                              'canceled before OBSERVE')
            g = Observe.Goal()
            g.refresh = True
            result, err = self._call_skill(self._cli_observe, g, 'OBSERVE', trace, rec, 30.0, goal_handle=goal_handle, t0=t0)
            if err:
                return finish(R.OUTCOME_FAILED, R.ERR_SKILL_FAILED,
                              'OBSERVE failed: %s' % err)
            if int(result.outcome) != Observe.Result.OUTCOME_SUCCEEDED:
                return finish(R.OUTCOME_FAILED, R.ERR_SKILL_FAILED,
                              'OBSERVE failed: %s' % result.detail)
            res.detail = result.detail

            # ---------- PICK ----------
            if goal_handle.is_cancel_requested:
                return finish(R.OUTCOME_CANCELED, R.ERR_CANCELED,
                              'canceled before PICK (trace=%s)' % ','.join(trace))
            g = PickObject.Goal()
            g.object_name = goal.object_name
            g.motion_profile_id = goal.motion_profile_id
            result, err = self._call_skill(self._cli_pick, g, 'PICK', trace, rec, deadline_s, goal_handle=goal_handle, t0=t0)
            if err:
                return finish(R.OUTCOME_FAILED, R.ERR_SKILL_FAILED,
                              'PICK failed: %s' % err)
            if int(result.outcome) != PickObject.Result.OUTCOME_SUCCEEDED:
                return finish(R.OUTCOME_FAILED, R.ERR_SKILL_FAILED,
                              'PICK failed: %s (%s)' % (err_name(
                                  PickObject.Result, 'ERR_', int(result.error_code)),
                                  result.detail))

            # ---------- PLACE ----------
            if goal_handle.is_cancel_requested:
                return finish(R.OUTCOME_CANCELED, R.ERR_CANCELED,
                              'canceled before PLACE (box is attached; robot left '
                              'holding the object - trace=%s)' % ','.join(trace))
            g = PlaceObject.Goal()
            g.object_name = goal.object_name
            g.place_pose = PoseStamped()
            g.place_pose.header.frame_id = 'world'
            g.place_pose.pose.position = pp
            g.place_pose.pose.orientation.w = 1.0
            g.motion_profile_id = goal.motion_profile_id
            result, err = self._call_skill(self._cli_place, g, 'PLACE', trace, rec, deadline_s, goal_handle=goal_handle, t0=t0)
            if err:
                return finish(R.OUTCOME_FAILED, R.ERR_SKILL_FAILED,
                              'PLACE failed: %s' % err)
            if int(result.outcome) != PlaceObject.Result.OUTCOME_SUCCEEDED:
                return finish(R.OUTCOME_FAILED, R.ERR_SKILL_FAILED,
                              'PLACE failed: %s (%s)' % (err_name(
                                  PlaceObject.Result, 'ERR_', int(result.error_code)),
                                  result.detail))

            # ---------- VERIFY ----------
            res.object_at_place = False
            if goal.skip_verify:
                trace.append('VERIFY(skipped)')
                res.object_at_place = True   # PLACE already verified internally
                return finish(R.OUTCOME_SUCCEEDED, R.ERR_NONE,
                              'task done (VERIFY skipped; PLACE drop check passed)')

            if goal_handle.is_cancel_requested:
                return finish(R.OUTCOME_CANCELED, R.ERR_CANCELED,
                              'canceled before VERIFY (trace=%s)' % ','.join(trace))
            g = VerifyObject.Goal()
            g.object_name = goal.object_name
            g.expected_pose = goal.place_pose.pose
            g.position_tolerance_m = self._tol
            result, err = self._call_skill(self._cli_verify, g, 'VERIFY', trace, rec, 30.0, goal_handle=goal_handle, t0=t0)
            if err:
                return finish(R.OUTCOME_FAILED, R.ERR_SKILL_FAILED,
                              'VERIFY failed: %s' % err)
            if int(result.outcome) == VerifyObject.Result.OUTCOME_VERIFIED:
                res.object_at_place = True
                res.final_position_error_m = result.position_error_m
                return finish(R.OUTCOME_SUCCEEDED, R.ERR_NONE,
                              'task done: object verified at place (err=%.4f)'
                              % result.position_error_m)
            res.final_position_error_m = result.position_error_m
            return finish(R.OUTCOME_FAILED, R.ERR_SKILL_FAILED,
                          'VERIFY mismatch: %s' % result.detail)

        except Exception as exc:  # crash guard (issue #20): rclpy's
            # fallback for a raising execute callback is a default Result
            # with outcome=0 = OUTCOME_SUCCEEDED - never let that happen
            return finish(R.OUTCOME_FAILED, R.ERR_SKILL_FAILED,
                          crash_detail(exc))
        finally:
            self._busy = False

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
            fb = RunDemo.Feedback()
            fb.state = label
            fb.elapsed_ms = int((time.monotonic() - t0) * 1000)
            goal_handle.publish_feedback(fb)
        if not cli.wait_for_server(timeout_sec=10.0):
            return None, '%s skill server unavailable' % label
        send = cli.send_goal_async(goal)
        t_send = time.monotonic()
        while not send.done():
            if time.monotonic() - t_send > 15.0:
                return None, '%s goal send timeout' % label
            time.sleep(0.02)
        gh = send.result()
        if gh is None or not gh.accepted:
            return None, '%s goal rejected' % label
        rf = gh.get_result_async()
        t_r = time.monotonic()
        while not rf.done():
            if time.monotonic() - t_r > deadline_s:
                gh.cancel_goal_async()
                return None, '%s result timeout (cancel sent)' % label
            time.sleep(0.05)
        return rf.result().result, None

    def _execute_demo(self, goal_handle):
        t0 = time.monotonic()
        goal = goal_handle.request
        self._seq += 1
        scenario = goal.scenario_id or 'week1_demo_v1'
        run_id = '%s-%s' % (scenario, uuid.uuid4().hex[:8])
        _, evidence = new_evidence(scenario, self._seq)
        trace = []
        steps = []
        res = RunDemo.Result()
        verify_results = {}

        def finish(outcome, error, detail):
            res.outcome = outcome
            res.error_code = error
            res.scenario_id = scenario
            res.run_id = run_id
            res.detail = detail
            res.fsm_trace = trace
            res.duration_s = time.monotonic() - t0
            res.evidence_id = evidence
            for tag in ('a', 'b'):
                vr = verify_results.get(tag)
                v_ok = vr is not None and int(vr.outcome) == VerifyObject.Result.OUTCOME_VERIFIED
                setattr(res, 'object_%s_at_zone' % tag, bool(v_ok))
                setattr(res, 'zone_%s_error_m' % tag,
                        float(vr.position_error_m) if vr is not None and vr.has_measured_pose
                        else float('nan'))
            self._demo_log.write({
                'scenario_id': scenario, 'run_id': run_id,
                'evidence_id': evidence,
                'outcome': str(outcome), 'error_code': int(error),
                'detail': detail, 'duration_s': res.duration_s,
                'steps': steps, 'fsm_trace': list(trace),
                'object_a_at_zone': res.object_a_at_zone,
                'object_b_at_zone': res.object_b_at_zone,
                'zone_a_error_m': res.zone_a_error_m,
                'zone_b_error_m': res.zone_b_error_m,
            })
            self._publish_task_state('IDLE')
            if outcome == RunDemo.Result.OUTCOME_SUCCEEDED:
                goal_handle.succeed()
            elif outcome == RunDemo.Result.OUTCOME_CANCELED:
                goal_handle.canceled()
            else:
                goal_handle.abort()
            return res

        if self._demo_busy:
            return finish(RunDemo.Result.OUTCOME_FAILED,
                          RunDemo.Result.ERR_RESOURCE_BUSY,
                          'another demo task is active')
        self._demo_busy = True
        self._publish_task_state('BUSY')
        try:
            # ---- decision inputs (ADR-002: executor assembles, policy decides) ----
            goal_obj = TaskGoal(
                goal_id=run_id,
                scenario_id=scenario,
                assignments=((self._obj_a, 'zone_1'), (self._obj_b, 'zone_2')),
            )
            constraints = Constraints(
                allowed_actions=frozenset((
                    ACTION_OBSERVE, ACTION_PICK, ACTION_PLACE, ACTION_VERIFY,
                    'WAIT', ACTION_ABORT)),
                recovery_budget=self._budget,
                verify_tolerance_m=self._demo_tol,
                motion_profile_id='demo_slow',
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
            abort_error = RunDemo.Result.ERR_SKILL_FAILED
            abort_detail = ''

            def tag_of(object_id):
                return 'A' if object_id == self._obj_a else 'B'

            while True:
                # cancellation is honoured at decision boundaries (the original
                # demo loop never checked it - safety delta, documented in #4)
                if goal_handle.is_cancel_requested:
                    return finish(RunDemo.Result.OUTCOME_CANCELED,
                                  RunDemo.Result.ERR_CANCELED,
                                  'canceled (trace=%s)' % ','.join(trace))
                # completion is structural (all assignments verified), not a decision
                verified_legs = sum(
                    1 for d in history
                    if d.action == ACTION_VERIFY and d.outcome == 0)
                if verified_legs >= len(goal_obj.assignments):
                    return finish(RunDemo.Result.OUTCOME_SUCCEEDED,
                                  RunDemo.Result.ERR_NONE,
                                  'demo done: A->zone_1 (%.4fm), B->zone_2 (%.4fm)'
                                  % (res.zone_a_error_m, res.zone_b_error_m))

                # ---- ask the policy WHAT next ----
                t_dec = time.monotonic()
                decision = self._policy.decide(world, goal_obj, constraints,
                                               tuple(history))
                d_ms = int((time.monotonic() - t_dec) * 1000)
                decision_seq += 1
                self._decision_log.write({
                    'run_id': run_id, 'scenario_id': scenario,
                    'seq': decision_seq,
                    'action': decision.action, 'target': decision.target,
                    'confidence': decision.confidence,
                    'reason_code': decision.reason_code,
                    'explanation': decision.explanation,
                    'policy': self._policy.name,
                    'policy_version': self._policy.version,
                    'world_revision': last_world_revision,
                    'observe_evidence_id': last_observe_evidence,
                    'decide_latency_ms': d_ms,
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
                    r, err = self._demo_call(self._cli_observe, og, label,
                                             goal_handle, t0, 30.0)
                    o_outcome = int(r.outcome) if r is not None else 255
                    o_evidence = getattr(r, 'evidence_id', '') if r else ''
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
                        abort_error = RunDemo.Result.ERR_SKILL_FAILED
                        abort_detail = '%s failed: %s' % (label, err or r.detail)
                        history.append(HistoryRecord(
                            action=ACTION_OBSERVE, target=decision.target,
                            outcome=255, error_code=-1, attempt=attempt,
                            world_revision=last_world_revision, evidence_id=''))
                        continue
                    world = r.world_state
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
                    label = 'PICK_%s(attempt=%d)' % (tag, attempt)
                    pg = PickObject.Goal()
                    pg.object_name = decision.target
                    pg.motion_profile_id = constraints.motion_profile_id
                    r, err = self._demo_call(self._cli_pick, pg, label,
                                             goal_handle, t0, 90.0)
                    pick_ok = (err is None and r is not None and
                               int(r.outcome) == PickObject.Result.OUTCOME_SUCCEEDED)
                    code = int(r.error_code) if (err is None and r is not None) else -1
                    ename = err or err_name(PickObject.Result, 'ERR_', code)
                    steps.append({'state': label, 'skill': 'pick', 'ok': pick_ok,
                                  'error': err or (r.detail if r else ''),
                                  'error_code': code, 'attempt': attempt,
                                  'evidence_id': getattr(r, 'evidence_id', '') if r else ''})
                    trace.append('%s:%s' % (label, 'OK' if pick_ok else 'FAIL:%s' % ename))
                    if pick_ok:
                        history.append(HistoryRecord(
                            action=ACTION_PICK, target=decision.target,
                            outcome=0, error_code=0, attempt=attempt,
                            world_revision=last_world_revision,
                            evidence_id=r.evidence_id))
                    else:
                        last_fail_label = label
                        abort_error = RunDemo.Result.ERR_SKILL_FAILED
                        abort_detail = '%s failed (%s): %s' % (label, ename, err or r.detail)
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
                    zx, zy, zz = self._zones[zone_of[decision.target]]
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
                    r, err = self._demo_call(self._cli_place, pg, label,
                                             goal_handle, t0, 90.0)
                    place_ok = (err is None and r is not None and
                                int(r.outcome) == PlaceObject.Result.OUTCOME_SUCCEEDED)
                    steps.append({'state': label, 'skill': 'place', 'ok': place_ok,
                                  'error': err or (r.detail if r else ''),
                                  'evidence_id': getattr(r, 'evidence_id', '') if r else ''})
                    trace.append('%s:%s' % (label, 'OK' if place_ok else 'FAIL'))
                    if place_ok:
                        history.append(HistoryRecord(
                            action=ACTION_PLACE, target=decision.target,
                            outcome=0, error_code=0, attempt=attempt,
                            world_revision=last_world_revision,
                            evidence_id=getattr(r, 'evidence_id', '') if r else ''))
                    else:
                        abort_error = RunDemo.Result.ERR_SKILL_FAILED
                        abort_detail = 'PLACE_%s failed: %s' % (tag, err or (r.detail if r else ''))
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
                    label = 'VERIFY_%s(attempt=%d)' % (tag, vattempt)
                    zx, zy, zz = self._zones[zone_of[decision.target]]
                    zone_pose = PoseStamped()
                    zone_pose.header.frame_id = 'world'
                    zone_pose.pose.position.x = zx
                    zone_pose.pose.position.y = zy
                    zone_pose.pose.position.z = zz
                    zone_pose.pose.orientation.w = 1.0
                    vg = VerifyObject.Goal()
                    vg.object_name = decision.target
                    vg.expected_pose = zone_pose.pose
                    vg.position_tolerance_m = self._demo_tol
                    r, err = self._demo_call(self._cli_verify, vg, label,
                                             goal_handle, t0, 30.0)
                    verify_results[tag.lower()] = r
                    v_ok = (err is None and r is not None and
                            int(r.outcome) == VerifyObject.Result.OUTCOME_VERIFIED)
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
                        abort_error = RunDemo.Result.ERR_RECOVERY_EXHAUSTED
                        abort_detail = 'VERIFY_%s still mismatched after budget: %s' % (
                            tag, err or r.detail)
                        history.append(HistoryRecord(
                            action=ACTION_VERIFY, target=decision.target,
                            outcome=(int(r.outcome) if r is not None else 255),
                            error_code=(int(r.error_code) if r is not None else -1),
                            attempt=vattempt,
                            world_revision=last_world_revision,
                            evidence_id=getattr(r, 'evidence_id', '') if r else ''))
                    continue

                # ---------------- WAIT / unknown ----------------
                if decision.action == 'WAIT':
                    continue
                raise PolicyStateError(
                    'policy returned unsupported action %r' % decision.action)

        except PolicyStateError as exc:
            self.get_logger().error('policy state error: %s' % exc)
            return finish(RunDemo.Result.OUTCOME_FAILED,
                          RunDemo.Result.ERR_SKILL_FAILED,
                          'policy state error: %s' % exc)
        except Exception as exc:  # crash guard (issue #20): rclpy's fallback
            # for a raising execute callback is a default Result with
            # outcome=0 = OUTCOME_SUCCEEDED - never let that happen
            return finish(RunDemo.Result.OUTCOME_FAILED,
                          RunDemo.Result.ERR_SKILL_FAILED, crash_detail(exc))
        finally:
            self._demo_busy = False
            self._publish_task_state('IDLE')


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
