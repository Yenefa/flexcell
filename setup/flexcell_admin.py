#!/usr/bin/env python3
"""FlexCell admin helpers: graph health checks + deterministic reset.

Called by the `flexcell` bash CLI (ROS env already sourced). Read-only health,
plus a bounded reset routine that restores the canonical demo state without
restarting the ROS graph.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy
from rclpy.time import Time

from geometry_msgs.msg import PoseStamped
from moveit_msgs.msg import AttachedCollisionObject, CollisionObject, PlanningScene
from moveit_msgs.srv import ApplyPlanningScene, GetPlanningScene
from std_msgs.msg import Empty as EmptyMsg
from std_msgs.msg import String as StringMsg

from flexcell_interfaces.action import Observe
from flexcell_interfaces.msg import CarryState

from flexcell_skills.common import sample_gz_pose, stop_gz_pose_stream

ACTIONS = {
    '/move_to_pose': None,          # type-agnostic presence check below
    '/observe': None,
    '/pick_object': None,
    '/place_object': None,
    '/verify_object': None,
    '/run_demo': None,
    '/run_pick_place': None,
}
CONTROLLERS = ['arm_controller', 'gripper_controller', 'joint_state_broadcaster']
REQUIRED_MODELS = ['ground_plane', 'open_manipulator_x', 'target_box_a',
                   'target_box_b', 'zone_1', 'zone_2']
CANONICAL = {
    'target_box_a': (0.22, 0.0, 0.0175),
    'target_box_b': (0.20, -0.18, 0.0175),
}
WORKSPACE = os.environ.get('FLEXCELL_WS', '/home/ros/agentic_workcell_ws')


def gz_models():
    out = subprocess.run(['gz', 'model', '--list'], capture_output=True,
                         text=True, timeout=15).stdout
    return set(re.findall(r'-\s+(\S+)', out))


def gz_pose(name):
    """Ground-truth pose via the persistent python Pose_V stream (no CLI)."""
    got, _err = sample_gz_pose(name, timeout_s=6.0)
    return got[0] if got else None


def gz_pose_cli(name):
    """CLI fallback parser (gz model -p text format)."""
    out = subprocess.run(['gz', 'model', '-m', name, '-p'], capture_output=True,
                         text=True, timeout=15).stdout
    m = re.search(r'XYZ[^\n]*\n\s*\[([^\]]+)\]', out)
    if not m:
        return None
    return [float(v) for v in m.group(1).split()]


def gz_set_pose(name, xyz):
    # NodeShared is a process singleton. A stalled cold RPC stayed stalled even
    # with a new Node and a 15s wait; a fresh process succeeded in 0.20s. Retry
    # only this idempotent pose command on a clean native transport instance.
    attempts = []
    for attempt in range(1, 4):
        detail = dict(attempt=attempt)
        attempts.append(detail)
        try:
            proc = subprocess.run(
                [sys.executable, '-m', 'flexcell_skills.pose_request_worker',
                 name, *(str(value) for value in xyz)],
                capture_output=True, text=True, timeout=5,
                env=dict(os.environ, PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION='python'))
        except subprocess.TimeoutExpired:
            detail['error'] = 'pose request worker timed out'
            return False, dict(attempts=attempts)
        detail.update(worker_rc=proc.returncode, stderr=proc.stderr[-1500:])
        if proc.returncode != 0:
            detail['error'] = 'pose request worker exit rejected'
            return False, dict(attempts=attempts)
        try:
            payload = json.loads(proc.stdout)
        except ValueError:
            payload = None
        if (not isinstance(payload, dict)
                or type(payload.get('transport_ok')) is not bool
                or type(payload.get('response_data')) is not bool):
            detail['error'] = 'invalid pose request worker response'
            return False, dict(attempts=attempts)
        detail.update(payload)
        if payload['transport_ok']:
            return payload['response_data'], dict(attempts=attempts)
    return False, dict(attempts=attempts)


class Admin(Node):

    def __init__(self):
        super().__init__('flexcell_admin')
        self._cbg = ReentrantCallbackGroup()
        qos = QoSProfile(depth=1)
        qos.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL
        qos.reliability = QoSReliabilityPolicy.RELIABLE
        self._task_state = None
        self._carry_state = None
        self.create_subscription(StringMsg, '/flexcell/task_state',
                                 self._on_task, qos, callback_group=self._cbg)
        self.create_subscription(CarryState, '/flexcell/carry_state',
                                 self._on_carry, qos, callback_group=self._cbg)
        self._carry_stop = self.create_publisher(EmptyMsg,
                                                 '/flexcell/carry_stop', 10)
        self._scene_apply = self.create_client(
            ApplyPlanningScene, '/apply_planning_scene',
            callback_group=self._cbg)
        self._plan_cli = ActionClient(self, Observe, '/observe',
                                      callback_group=self._cbg)

    def _on_task(self, msg):
        self._task_state = msg.data

    def _canonical_present(self):
        """True if any CANONICAL object is still in the planning scene.

        The authoritative check for "did the scene really get cleared" - the
        ApplyPlanningScene response flag is not, because a REMOVE diff naming an
        already-absent id makes move_group answer success=false.
        """
        cli = self.create_client(GetPlanningScene, '/get_planning_scene',
                                 callback_group=self._cbg)
        if not cli.wait_for_service(timeout_sec=4.0):
            return False
        fut = cli.call_async(GetPlanningScene.Request())
        end = time.monotonic() + 10.0
        while not fut.done() and time.monotonic() < end:
            self.spin(0.1)
        if not fut.done():
            return False
        sc = fut.result().scene
        ids = {c.id for c in sc.world.collision_objects}
        ids |= {a.object.id for a in sc.robot_state.attached_collision_objects}
        return bool(ids & set(CANONICAL))

    def _on_carry(self, msg):
        self._carry_state = msg

    def spin(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rclpy.spin_once(self, timeout_sec=0.1)

    # ------------------------------------------------------------- health
    def health(self, strict=True):
        checks = {}
        # action servers present (real graph discovery from this fresh node)
        from rclpy.action import ActionClient  # noqa: F401
        from flexcell_interfaces.action import (
            MoveToPose, Observe, PickObject, PlaceObject, RunDemo, RunPickPlace,
            VerifyObject)
        typed = {'/move_to_pose': MoveToPose, '/observe': Observe,
                 '/pick_object': PickObject, '/place_object': PlaceObject,
                 '/verify_object': VerifyObject, '/run_demo': RunDemo,
                 '/run_pick_place': RunPickPlace}
        for name, cls in typed.items():
            cli = ActionClient(self, cls, name, callback_group=self._cbg)
            ok = cli.wait_for_server(timeout_sec=4.0)
            checks['action %s' % name] = 'OK' if ok else 'MISSING'
            cli.destroy()

        # Query the service directly. CLI daemon startup can hang even when
        # the manager and physical controllers are healthy.
        from controller_manager_msgs.srv import ListControllers
        manager = self.create_client(ListControllers, '/controller_manager/list_controllers',
                                     callback_group=self._cbg)
        states = {}
        try:
            available = manager.wait_for_service(timeout_sec=4.0)
            replied = False
            if available:
                future = manager.call_async(ListControllers.Request())
                end = time.monotonic() + 5.0
                while not future.done() and time.monotonic() < end:
                    self.spin(0.1)
                if future.done() and future.exception() is None:
                    states = {c.name: c.state for c in future.result().controller}
                    replied = True
            checks['service /controller_manager/list_controllers'] = (
                'OK' if replied else 'UNAVAILABLE (discovery or reply timeout)')
        finally:
            self.destroy_client(manager)
        for c in CONTROLLERS:
            checks['controller %s' % c] = ('OK' if states.get(c) == 'active' else 'NOT_ACTIVE')

        # planning service reachable
        cli = self.create_client(GetPlanningScene, '/get_planning_scene',
                                 callback_group=self._cbg)
        checks['service /get_planning_scene'] = (
            'OK' if cli.wait_for_service(timeout_sec=4.0) else 'MISSING')

        # gz world alive: objects via the python pose stream (hard check);
        # static zone markers via CLI listing (informational, CLI may wedge)
        models = gz_models()
        missing = [m for m in REQUIRED_MODELS if m not in models]
        for name in ('target_box_a', 'target_box_b'):
            if gz_pose(name) is None:
                missing.append(name + ' (pose stream)')
        checks['gz world models'] = ('OK' if not missing
                                     else 'MISSING %s' % missing)
        for name, want in CANONICAL.items():
            got = gz_pose(name)
            checks['object %s pose' % name] = (
                'OK %s' % ['%.3f' % v for v in got] if got else 'UNAVAILABLE')

        if os.environ.get('FLEXCELL_CARRY_BACKEND') == 'velocity_servo':
            from flexcell_interfaces.srv import EngageCarry
            engage = self.create_client(EngageCarry, '/flexcell/carry_engage',
                                        callback_group=self._cbg)
            try:
                checks['service /flexcell/carry_engage'] = (
                    'OK' if engage.wait_for_service(timeout_sec=4.0) else 'UNAVAILABLE')
            finally:
                self.destroy_client(engage)

        from flexcell_interfaces.srv import QueryCarry
        snapshot = self.create_client(QueryCarry, '/flexcell/carry_snapshot', callback_group=self._cbg)
        try:
            carry_response = None
            if snapshot.wait_for_service(timeout_sec=3):
                future = snapshot.call_async(QueryCarry.Request())
                deadline = time.monotonic()+3
                while not future.done() and time.monotonic() < deadline:
                    self.spin(.1)
                if future.done() and future.exception() is None:
                    carry_response = future.result()
            checks['service /flexcell/carry_snapshot'] = ('OK' if carry_response and carry_response.success
                                                        else 'UNAVAILABLE (current backend state unconfirmed)')
        finally:
            self.destroy_client(snapshot)

        # carry backend single instance (graph-level publisher count)
        n_pub = self.count_publishers('/flexcell/carry_state')
        checks['carry_state publishers'] = ('OK (1)' if n_pub == 1
                                            else 'DUPLICATE (%d)' % n_pub)

        self.spin(1.5)
        checks['task_state'] = self._task_state or 'UNAVAILABLE'
        checks['carry_engaged'] = bool(carry_response.state.engaged) if \
            carry_response and carry_response.success else None

        fail_words = ('MISSING', 'NOT_ACTIVE', 'DUPLICATE', 'UNAVAILABLE')
        hard_fail = [k for k, v in checks.items()
                     if any(w in str(v) for w in fail_words)]
        busy = checks['task_state'] not in ('IDLE', 'UNAVAILABLE')
        ok = not hard_fail and not (strict and busy)
        print(json.dumps({'ok': ok, 'checks': checks,
                          'hard_fail': hard_fail, 'busy': busy}, indent=2))
        return 0 if ok else 1

    # ------------------------------------------------------------- reset
    def wait_task_idle(self, timeout_s=15.0):
        """Wait for the latched task_state to read IDLE.

        The window was 5 s, but a fresh process needs DDS discovery before the
        TRANSIENT_LOCAL sample arrives: measured 1.54 s here, and under the
        full stack load it can exceed 5 s - which surfaced as a spurious
        "task_fsm is BUSY" on an idle workcell.  Wait longer, and let the
        caller tell "never received" from "genuinely busy".
        """
        end = time.monotonic() + timeout_s
        while time.monotonic() < end:
            self.spin(0.2)
            if self._task_state == 'IDLE':
                return True
        return self._task_state == 'IDLE'

    def reset(self):
        report = {}

        # 0) task must be idle
        report['task_idle'] = self.wait_task_idle()
        report['task_state_seen'] = self._task_state
        report['task_state_publishers'] = self.count_publishers(
            '/flexcell/task_state')
        if not report['task_idle']:
            if self._task_state is None:
                why = ('task_state never received (no latched sample from '
                       '/flexcell/task_state; discovery or publisher down) - '
                       'NOT evidence of a busy task')
            else:
                why = 'task_fsm reports state %r' % (self._task_state,)
            self._reset_payload = {'ok': False, 'report': report, 'error': why}
            return 1

        # 1) force-disengage the carry servo.
        #
        # The old code published the stop only `if engaged`, and `engaged` came
        # from the latched CarryState - a topic that goes SILENT when the state
        # never changes.  A wedged servo (logged ENGAGED, publishing nothing)
        # therefore read as "not engaged": the stop was never sent, the reset
        # reported carry_disengaged: true, and every later set_pose was
        # overwritten at 10 Hz by the still-pinning servo.  Measured
        # 2026-09-29: target_box_a stranded at EE+offset [0.2782, 0.0028,
        # 0.0222]; set_pose -> True three times, the box never moved.  Send the
        # stop unconditionally and confirm it.
        report['carry_stop_sent'] = False
        end = time.monotonic() + 5.0
        while self.count_subscribers('/flexcell/carry_stop') == 0 \
                and time.monotonic() < end:
            self.spin(0.1)
        if self.count_subscribers('/flexcell/carry_stop') > 0:
            for _ in range(3):
                self._carry_stop.publish(EmptyMsg())
                self.spin(0.2)
            report['carry_stop_sent'] = True
        end = time.monotonic() + 3.0
        while time.monotonic() < end:
            self.spin(0.2)
            if self._carry_state and not self._carry_state.engaged:
                break
        report['carry_state_known'] = self._carry_state is not None
        report['carry_engaged'] = (bool(self._carry_state.engaged)
                                   if self._carry_state else None)
        # NOTE: carry_disengaged is settled AFTER the pose verification below,
        # from behavioural proof (the boxes hold their commanded pose) instead
        # of from a topic that may never speak.

        # 2) clear the planning scene belief (detach + remove tracked objects)
        # only if something is actually there - REMOVE of a nonexistent id
        # makes move_group report failure
        get_cli = self.create_client(GetPlanningScene, '/get_planning_scene',
                                     callback_group=self._cbg)
        present = False
        if get_cli.wait_for_service(timeout_sec=4.0):
            fut = get_cli.call_async(GetPlanningScene.Request())
            end = time.monotonic() + 10.0
            while not fut.done() and time.monotonic() < end:
                rclpy.spin_once(self, timeout_sec=0.1)
            if fut.done():
                sc = fut.result().scene
                world_ids = {c.id for c in sc.world.collision_objects}
                attached_ids = {a.object.id
                                for a in sc.robot_state.attached_collision_objects}
                present = bool((world_ids | attached_ids) & set(CANONICAL))
        report['scene_had_objects'] = present
        scene_cleared = not present
        if present:
            scene = PlanningScene()
            scene.is_diff = True
            for name in CANONICAL:
                aco = AttachedCollisionObject()
                aco.object.id = name
                aco.object.operation = CollisionObject.REMOVE
                scene.robot_state.attached_collision_objects.append(aco)
                scene.robot_state.is_diff = True
                co = CollisionObject()
                co.id = name
                co.operation = CollisionObject.REMOVE
                scene.world.collision_objects.append(co)
            req = ApplyPlanningScene.Request()
            req.scene = scene
            fut = self._scene_apply.call_async(req)
            end = time.monotonic() + 10.0
            while not fut.done() and time.monotonic() < end:
                rclpy.spin_once(self, timeout_sec=0.1)
            apply_ok = bool(fut.done() and fut.result().success)
            # Trust the SCENE, not the response flag: re-query and decide on
            # absence.  A REMOVE diff naming an already-absent id makes
            # move_group answer success=false, which used to surface as
            # `scene_cleared: false` while the scene was in fact clean.
            # Measured 2026-09-29: the scene was empty on re-query right after
            # a reported scene_cleared: false.
            report['scene_apply_ok'] = apply_ok
            report['scene_cleared'] = not self._canonical_present()
        else:
            report['scene_cleared'] = not present

        # 3) arm to joint home via the Day-1 joint tool (lifecycle, not a skill)
        proc = subprocess.run(
            ['python3', WORKSPACE + '/plan_execute.py', '0.0', '0.0', '0.0', '0.0'],
            capture_output=True, text=True, timeout=90, cwd=WORKSPACE)
        out = proc.stdout
        report['arm_home'] = ('EXECUTE error_code = 1' in out and
                              'PLAN error_code = 1' in out)
        report['arm_home_detail'] = ' '.join(out.split())[:200]

        # 4) objects back to canonical spawns (ground truth, deterministic)
        for name, xyz in CANONICAL.items():
            ok, detail = gz_set_pose(name, xyz)
            report['respawn %s' % name] = bool(ok)
            report['respawn_details %s' % name] = detail
        time.sleep(1.0)

        # 5) re-observe so WorldState revision/poses reflect the reset world
        og = Observe.Goal()
        og.refresh = True
        if self._plan_cli.wait_for_server(timeout_sec=5.0):
            send = self._plan_cli.send_goal_async(og)
            end = time.monotonic() + 15.0
            while not send.done() and time.monotonic() < end:
                self.spin(0.1)
            gh = send.result() if send.done() else None
            accepted = gh is not None and gh.accepted
            report['reobserved'] = False
            if accepted:
                rf = gh.get_result_async()
                end = time.monotonic() + 15.0
                while not rf.done() and time.monotonic() < end:
                    self.spin(0.1)
                report['reobserved'] = bool(rf.done())
        else:
            report['reobserved'] = False

        # 6) verify canonical positions: re-assert via set_pose (reliable
        # service path), then sample - stream first, CLI parse as fallback.
        # If a box refuses its commanded pose, a carry servo is very likely
        # still pinning it: re-send the stop and try once more, because
        # "set_pose returned True but the box did not move" is precisely the
        # wedge the unconditional stop in step 1 removes.
        for name, want in CANONICAL.items():
            got = None
            report['canonical_rpc %s' % name] = []
            for attempt in range(2):
                pose_ok, detail = gz_set_pose(name, want)
                report['canonical_rpc %s' % name].append(dict(ok=pose_ok, **detail))
                time.sleep(0.8)
                got = gz_pose(name)
                if got is None:
                    got = gz_pose_cli(name)
                if got is not None and all(abs(g - w) < 0.005
                                           for g, w in zip(got, want)):
                    break
                if attempt == 0:
                    for _ in range(3):
                        self._carry_stop.publish(EmptyMsg())
                        self.spin(0.2)
                    time.sleep(0.4)
            ok = got is not None and all(abs(g - w) < 0.005
                                         for g, w in zip(got, want))
            report['canonical %s' % name] = ('OK %s' % ['%.4f' % v for v in got]
                                             if ok else 'DRIFT %s' % got)

        # carry_disengaged, decided on BEHAVIOUR: a servo that is still
        # pinning cannot let a box hold a commanded pose, so boxes-on-canonical
        # is the proof.  The latched CarryState is corroboration only.
        boxes_canonical = all('OK' in report['canonical %s' % n]
                              for n in CANONICAL)
        state_says_off = (self._carry_state is not None
                          and not self._carry_state.engaged)
        report['carry_disengaged'] = bool(boxes_canonical or state_says_off)

        ok = (report['task_idle'] and report['carry_disengaged']
              and report['scene_cleared'] and report['arm_home']
              and all(report['respawn %s' % n] for n in CANONICAL)
              and all('OK' in report['canonical %s' % n] for n in CANONICAL))
        self._reset_payload = {'ok': ok, 'report': report}
        return 0 if ok else 1


def _native_main():
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=['health', 'reset'])
    ap.add_argument('--no-strict', action='store_true')
    args = ap.parse_args()
    rclpy.init()
    node = Admin()
    rc = 1
    cleanup_error = None
    try:
        node.spin(1.0)
        if args.command == 'health':
            rc = node.health(strict=not args.no_strict)
        else:
            rc = node.reset()
    finally:
        try:
            stop_gz_pose_stream()
        except Exception as exc:
            cleanup_error = str(exc)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    if args.command == 'health' and cleanup_error:
        raise RuntimeError('health worker cleanup failed: ' + cleanup_error)
    if args.command == 'reset':
        payload = getattr(node, '_reset_payload', {'ok': False, 'error': 'reset incomplete'})
        if cleanup_error:
            payload.update(ok=False, cleanup_error=cleanup_error)
            rc = 1
        print(json.dumps(payload, indent=2))
    return rc


def main():
    # The parent validates the *process exit*, after native library finalizers.
    # Never forward a child's ok:true if it then dies with SIGSEGV (RC=139).
    if '--native-admin-worker' in sys.argv:
        sys.argv.remove('--native-admin-worker')
        return _native_main()
    child = subprocess.Popen([sys.executable, __file__, '--native-admin-worker',
                              *sys.argv[1:]], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
    import signal
    def terminate(signum, _frame):
        child.send_signal(signum)
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    try:
        stdout, stderr = child.communicate(timeout=300)
    except subprocess.TimeoutExpired:
        child.kill()
        stdout, stderr = child.communicate()
        print(json.dumps({'ok': False, 'error': 'admin worker timed out'}))
        return 1
    if child.returncode != 0:
        print(json.dumps({'ok': False, 'worker_rc': child.returncode,
                          'error': 'admin worker failed; success output rejected',
                          'worker_output': stdout[-4000:], 'worker_stderr': stderr[-1500:]}))
        return 1
    sys.stdout.write(stdout)
    sys.stderr.write(stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
