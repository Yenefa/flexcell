#!/usr/bin/env python3
"""FlexCell deterministic pick-and-place task FSM (Week 1).

Strict sequential FSM over the four skills:

    OBSERVE -> PICK -> PLACE -> VERIFY

No LLM, no Jev, no planning policy - exactly the deterministic baseline the
upstream roadmap requires before any Task Policy work. One task at a time
(single-arm mutual exclusion). Cancellation is honoured between states; a
canceled mid-task leaves the robot in the state the skills left it in and
reports honestly.
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

from flexcell_skills.common import JsonlLog, new_evidence

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

        # ---------------- Week-1.5 demo FSM ----------------
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
            'Task FSM v2 up | demo: %s->zone_1, %s->zone_2 | recovery budget=%d'
            % (self._obj_a, self._obj_b, self._budget))

    def _publish_task_state(self, state):
        self._state_pub.publish(StringMsg(data=state))

        self.get_logger().info('Task FSM server up | OBSERVE->PICK->PLACE->VERIFY')

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

        finally:
            self._busy = False

    # =================================================================
    # Week-1.5 deterministic demo:
    #   OBSERVE -> PICK A -> PLACE A -> VERIFY A
    #   -> OBSERVE -> PICK B -> PLACE B -> VERIFY B
    # Bounded recovery: recoverable failures get REOBSERVE + one retry
    # (budget=1); non-recoverable failures abort with a typed error. Every
    # step lands in the per-run demo evidence JSONL.
    # =================================================================

    # PickObject error codes that a REOBSERVE+RETRY may plausibly fix
    RECOVERABLE_PICK = frozenset({22, 23, 30})  # WORLD_STATE_UNAVAIL/GRASP_FAILED/MOTION_FAILED

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
            plan = [('A', self._obj_a, 'zone_1', self._zones['zone_1']),
                    ('B', self._obj_b, 'zone_2', self._zones['zone_2'])]
            for tag, obj, zone_id, zone in plan:
                # ---------- OBSERVE ----------
                og = Observe.Goal()
                og.refresh = True
                r, err = self._demo_call(self._cli_observe, og, 'OBSERVE_%s' % tag,
                                         goal_handle, t0, 30.0)
                steps.append({'state': 'OBSERVE_%s' % tag, 'skill': 'observe',
                              'ok': err is None and r is not None and
                              int(r.outcome) == Observe.Result.OUTCOME_SUCCEEDED,
                              'error': err or '', 'attempt': 1})
                if err or int(r.outcome) != Observe.Result.OUTCOME_SUCCEEDED:
                    return finish(RunDemo.Result.OUTCOME_FAILED,
                                  RunDemo.Result.ERR_SKILL_FAILED,
                                  'OBSERVE_%s failed: %s' % (tag, err or r.detail))

                # ---------- PICK with bounded recovery ----------
                attempt = 1
                while True:
                    pg = PickObject.Goal()
                    pg.object_name = obj
                    pg.motion_profile_id = 'demo_slow'
                    label = 'PICK_%s(attempt=%d)' % (tag, attempt)
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
                    if pick_ok:
                        trace.append('%s:OK' % label)
                        break
                    trace.append('%s:FAIL:%s' % (label, ename))
                    recoverable = (err is None and code in self.RECOVERABLE_PICK)
                    if not recoverable or attempt > self._budget:
                        ecode = (RunDemo.Result.ERR_RECOVERY_EXHAUSTED
                                 if recoverable and attempt > self._budget
                                 else RunDemo.Result.ERR_SKILL_FAILED)
                        return finish(RunDemo.Result.OUTCOME_FAILED, ecode,
                                      '%s failed (%s): %s'
                                      % (label, ename, err or r.detail))
                    trace.append('RECOVERY:REOBSERVE+RETRY(after %s)' % label)
                    og = Observe.Goal()
                    og.refresh = True
                    ro, oerr = self._demo_call(self._cli_observe, og,
                                               'REOBSERVE_%s' % tag,
                                               goal_handle, t0, 30.0)
                    steps.append({'state': 'REOBSERVE_%s' % tag, 'skill': 'observe',
                                  'ok': oerr is None, 'error': oerr or '',
                                  'attempt': attempt})
                    if oerr or int(ro.outcome) != Observe.Result.OUTCOME_SUCCEEDED:
                        return finish(RunDemo.Result.OUTCOME_FAILED,
                                      RunDemo.Result.ERR_SKILL_FAILED,
                                      'REOBSERVE_%s failed: %s' % (tag, oerr or ro.detail))
                    attempt += 1

                # ---------- PLACE (carried box: no auto-retry, typed abort) ----------
                zone_pose = PoseStamped()
                zone_pose.header.frame_id = 'world'
                zone_pose.pose.position.x = zone[0]
                zone_pose.pose.position.y = zone[1]
                zone_pose.pose.position.z = zone[2]
                zone_pose.pose.orientation.w = 1.0
                pg = PlaceObject.Goal()
                pg.object_name = obj
                pg.place_pose = zone_pose
                pg.motion_profile_id = 'demo_slow'
                r, err = self._demo_call(self._cli_place, pg, 'PLACE_%s' % tag,
                                         goal_handle, t0, 90.0)
                place_ok = (err is None and r is not None and
                            int(r.outcome) == PlaceObject.Result.OUTCOME_SUCCEEDED)
                steps.append({'state': 'PLACE_%s' % tag, 'skill': 'place',
                              'ok': place_ok,
                              'error': err or (r.detail if r else ''),
                              'evidence_id': getattr(r, 'evidence_id', '') if r else ''})
                trace.append('PLACE_%s:%s' % (tag, 'OK' if place_ok else 'FAIL'))
                if not place_ok:
                    return finish(RunDemo.Result.OUTCOME_FAILED,
                                  RunDemo.Result.ERR_SKILL_FAILED,
                                  'PLACE_%s failed: %s'
                                  % (tag, err or (r.detail if r else '')))

                # ---------- VERIFY with one bounded reobserve+reverify ----------
                vattempt = 1
                while True:
                    vg = VerifyObject.Goal()
                    vg.object_name = obj
                    vg.expected_pose = zone_pose.pose
                    vg.position_tolerance_m = self._demo_tol
                    label = 'VERIFY_%s(attempt=%d)' % (tag, vattempt)
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
                        break
                    if vattempt > self._budget:
                        return finish(RunDemo.Result.OUTCOME_FAILED,
                                      RunDemo.Result.ERR_RECOVERY_EXHAUSTED,
                                      'VERIFY_%s still mismatched after budget: %s'
                                      % (tag, err or r.detail))
                    trace.append('RECOVERY:REOBSERVE+REVERIFY(after %s)' % label)
                    og = Observe.Goal()
                    og.refresh = True
                    self._demo_call(self._cli_observe, og, 'REOBSERVE_%s' % tag,
                                    goal_handle, t0, 30.0)
                    vattempt += 1

            return finish(RunDemo.Result.OUTCOME_SUCCEEDED, RunDemo.Result.ERR_NONE,
                          'demo done: A->zone_1 (%.4fm), B->zone_2 (%.4fm)'
                          % (res.zone_a_error_m, res.zone_b_error_m))

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
