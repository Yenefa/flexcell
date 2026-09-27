#!/usr/bin/env python3
"""FlexCell admin helpers: graph health checks + deterministic reset.

Called by the `flexcell` bash CLI (ROS env already sourced). Read-only health,
plus a bounded reset routine that restores the canonical demo state without
restarting the ROS graph.
"""
import argparse
import json
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

from flexcell_skills.common import sample_gz_pose

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
WORKSPACE = '/home/ros/agentic_workcell_ws'


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
    from gz.msgs10 import boolean_pb2, pose_pb2
    import gz.transport13 as gz_transport
    node = gz_transport.Node()
    req = pose_pb2.Pose()
    req.name = name
    req.position.x, req.position.y, req.position.z = xyz
    req.orientation.w = 1.0
    return node.request('/world/empty/set_pose', req, pose_pb2.Pose,
                        boolean_pb2.Boolean, 1000)


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

        # controllers active (real controller_manager query)
        out = subprocess.run(['ros2', 'control', 'list_controllers'],
                             capture_output=True, text=True, timeout=20).stdout
        for c in CONTROLLERS:
            checks['controller %s' % c] = ('OK' if
                                           re.search(r'^%s\s+.*active' % c, out,
                                                     re.M) else 'NOT_ACTIVE')

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

        # carry backend single instance (graph-level publisher count)
        n_pub = self.count_publishers('/flexcell/carry_state')
        checks['carry_state publishers'] = ('OK (1)' if n_pub == 1
                                            else 'DUPLICATE (%d)' % n_pub)

        self.spin(1.5)
        checks['task_state'] = self._task_state or 'UNAVAILABLE'
        checks['carry_engaged'] = bool(self._carry_state.engaged) if \
            self._carry_state else None

        fail_words = ('MISSING', 'NOT_ACTIVE', 'DUPLICATE', 'UNAVAILABLE')
        hard_fail = [k for k, v in checks.items()
                     if any(w in str(v) for w in fail_words)]
        busy = checks['task_state'] not in ('IDLE', 'UNAVAILABLE')
        ok = not hard_fail and not (strict and busy)
        print(json.dumps({'ok': ok, 'checks': checks,
                          'hard_fail': hard_fail, 'busy': busy}, indent=2))
        return 0 if ok else 1

    # ------------------------------------------------------------- reset
    def wait_task_idle(self, timeout_s=5.0):
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
        if not report['task_idle']:
            print(json.dumps({'ok': False, 'report': report,
                              'error': 'task_fsm is BUSY - wait or stop it'}))
            return 1

        # 1) disengage carry (backend state), verify via latched CarryState
        engaged = bool(self._carry_state.engaged) if self._carry_state else False
        if engaged:
            # wait for the stop topic to have a matched subscriber before
            # publishing (short-lived process race)
            end = time.monotonic() + 5.0
            while self.count_subscribers('/flexcell/carry_stop') == 0 \
                    and time.monotonic() < end:
                time.sleep(0.1)
            self._carry_stop.publish(EmptyMsg())
            end = time.monotonic() + 3.0
            while time.monotonic() < end:
                self.spin(0.2)
                if self._carry_state and not self._carry_state.engaged:
                    break
            engaged = bool(self._carry_state.engaged) if self._carry_state else None
        report['carry_disengaged'] = engaged is False

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
            scene_cleared = bool(fut.done() and fut.result().success)
        report['scene_cleared'] = scene_cleared

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
            ok, _ = gz_set_pose(name, xyz)
            report['respawn %s' % name] = bool(ok)
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
        # service path), then sample - stream first, CLI parse as fallback
        for name, want in CANONICAL.items():
            got = None
            for _ in range(2):
                gz_set_pose(name, want)
                time.sleep(0.8)
                got = gz_pose(name)
                if got is None:
                    got = gz_pose_cli(name)
                if got is not None:
                    break
            ok = got is not None and all(abs(g - w) < 0.005
                                         for g, w in zip(got, want))
            report['canonical %s' % name] = ('OK %s' % ['%.4f' % v for v in got]
                                             if ok else 'DRIFT %s' % got)

        ok = (report['task_idle'] and report['carry_disengaged']
              and report['scene_cleared'] and report['arm_home']
              and all(report['respawn %s' % n] for n in CANONICAL)
              and all('OK' in report['canonical %s' % n] for n in CANONICAL))
        print(json.dumps({'ok': ok, 'report': report}, indent=2))
        return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=['health', 'reset'])
    ap.add_argument('--no-strict', action='store_true')
    args = ap.parse_args()
    rclpy.init()
    node = Admin()
    try:
        node.spin(1.0)
        if args.command == 'health':
            return node.health(strict=not args.no_strict)
        return node.reset()
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    sys.exit(main())
