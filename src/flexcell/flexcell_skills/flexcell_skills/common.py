"""Shared helpers for FlexCell Week-1 skill servers.

Ground-truth sampling (gz CLI), gripper / MoveToPose / planning-scene clients,
gz trigger publishing, JSONL logging. Kept deliberately dependency-light:
the gz python msgs bindings on this box cannot construct service requests,
so everything gz-side goes through the gz CLI in subprocesses.
"""

import json
import math
import os
import re
import subprocess
import time
import uuid

from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.duration import Duration
from rclpy.time import Time

from control_msgs.action import GripperCommand
from geometry_msgs.msg import Pose, PoseStamped
from moveit_msgs.msg import AttachedCollisionObject, CollisionObject, PlanningScene
from moveit_msgs.srv import ApplyPlanningScene, GetPlanningScene
from shape_msgs.msg import SolidPrimitive

from flexcell_interfaces.action import MoveToPose


def rpy_to_quat(roll, pitch, yaw):
    cr, sr = math.cos(roll / 2), math.sin(roll / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    return (
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
        cr * cp * cy + sr * sp * sy,
    )


def sample_gz_pose(model_name, timeout_s=10.0):
    """Ground-truth model pose via the gz CLI.

    Returns ((position[3], quat[4]), None) or (None, error).
    """
    try:
        proc = subprocess.run(
            ['gz', 'model', '-m', model_name, '-p'],
            capture_output=True, text=True, timeout=timeout_s)
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return None, 'gz model failed: %s' % exc
    out = proc.stdout
    if proc.returncode != 0 or 'not found' in (proc.stderr or '').lower():
        return None, 'model %r not found in gz world' % model_name
    m = re.search(r'XYZ[^\n]*\n\s*\[([^\]]+)\]\s*\n\s*\[([^\]]+)\]', out)
    if not m:
        return None, 'pose parse failed on: %r' % out[:120]
    try:
        xyz = [float(v) for v in m.group(1).split()]
        rpy = [float(v) for v in m.group(2).split()]
    except ValueError as exc:
        return None, 'pose numbers unparsable: %s' % exc
    return (xyz, list(rpy_to_quat(*rpy))), None


_ATTACH_STATE_FILE = '/tmp/flexcell_attach_state'


class AttachGate:
    """Deterministic on/off control for the DetachableJoint toggle trigger.

    The gz trigger topic toggles attach/detach on EVERY message, and one-shot
    `gz topic -p` publishes can be lost to discovery races (measured
    2026-09-26: an entire grasp chain silently no-oped that way). This gate
    keeps a persistent gz publisher alive inside the server process and tracks
    the logical state in a side file, so callers request a DESIRED state
    instead of a toggle. 50_start_detached.sh deletes the file on world
    reload because a fresh world always starts detached.
    """

    def __init__(self, topic, logger):
        import gz.transport13 as gz_transport
        from gz.msgs10 import empty_pb2
        self._empty = empty_pb2.Empty()
        self._gz_node = gz_transport.Node()
        self._pub = self._gz_node.advertise(topic, self._empty)
        self._log = logger

    def set_attach(self, want):
        state = '0'
        try:
            with open(_ATTACH_STATE_FILE) as fh:
                state = fh.read().strip() or '0'
        except OSError:
            pass
        want_s = '1' if want else '0'
        if state == want_s:
            return True, 'already %s' % want_s
        if not self._pub.publish(self._empty):
            return False, 'gz publish returned False'
        try:
            with open(_ATTACH_STATE_FILE, 'w') as fh:
                fh.write(want_s)
        except OSError as exc:
            return False, 'state file write failed: %s' % exc
        return True, 'toggled to %s' % want_s


def gz_publish(topic, msgtype='gz.msgs.Empty', payload='', timeout_s=5.0):
    """Publish one message on a gz topic via the CLI. Returns (ok, detail)."""
    try:
        proc = subprocess.run(
            ['gz', 'topic', '-t', topic, '-m', msgtype, '-p', payload],
            capture_output=True, text=True, timeout=timeout_s)
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return False, str(exc)
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or 'gz topic failed').strip()[:200]
    return True, ''


class JsonlLog:
    def __init__(self, node, log_dir, log_file):
        d = os.path.expanduser(log_dir)
        os.makedirs(d, exist_ok=True)
        self.path = os.path.join(d, log_file)
        self._node = node

    def write(self, rec):
        rec['wall_ts'] = time.time()
        try:
            with open(self.path, 'a') as fh:
                fh.write(json.dumps(rec, default=str) + '\n')
        except OSError as exc:  # never let logging kill a skill
            self._node.get_logger().error('log write failed: %s' % exc)


def new_evidence(request_id, seq):
    rid = request_id or ('auto-%d-%s' % (seq, uuid.uuid4().hex[:8]))
    return rid, '%s-%s' % (rid, uuid.uuid4().hex[:8])


def pose_msg(position, quat):
    p = Pose()
    p.position.x, p.position.y, p.position.z = position
    p.orientation.x, p.orientation.y, p.orientation.z, p.orientation.w = quat
    return p


def dist3(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def wait_future(future, timeout_s):
    t0 = time.monotonic()
    while not future.done():
        if time.monotonic() - t0 > timeout_s:
            return 'timeout'
        time.sleep(0.02)
    return 'done'


class MoveToPoseClient:
    """Blocking helper around the Day-2 MoveToPose action."""

    def __init__(self, node, action):
        self._cli = ActionClient(node, MoveToPose, action,
                                 callback_group=ReentrantCallbackGroup())

    def wait_ready(self, timeout_s=10.0):
        return self._cli.wait_for_server(timeout_sec=timeout_s)

    def call(self, position, profile='demo_slow', deadline_ms=30000,
             timeout_s=60.0, frame='world', request_id=''):
        g = MoveToPose.Goal()
        g.target = PoseStamped()
        g.target.header.frame_id = frame
        g.target.header.stamp = Time().to_msg()
        g.target.pose.position.x, g.target.pose.position.y, g.target.pose.position.z = position
        g.target.pose.orientation.w = 1.0
        g.motion_profile_id = profile
        g.deadline_ms = deadline_ms
        g.request_id = request_id
        if not self._cli.wait_for_server(timeout_sec=5.0):
            return None, 'move_to_pose action server unavailable'
        send = self._cli.send_goal_async(g)
        if wait_future(send, 10.0) != 'done':
            return None, 'move_to_pose goal send timeout'
        gh = send.result()
        if gh is None or not gh.accepted:
            return None, 'move_to_pose goal rejected'
        rf = gh.get_result_async()
        t0 = time.monotonic()
        while not rf.done():
            if time.monotonic() - t0 > timeout_s:
                gh.cancel_goal_async()
                return None, 'move_to_pose result timeout (cancel sent)'
            time.sleep(0.05)
        return rf.result().result, None


class GripperClient:
    def __init__(self, node, action):
        self._cli = ActionClient(node, GripperCommand, action,
                                 callback_group=ReentrantCallbackGroup())

    def command(self, position, max_effort=10.0, timeout_s=10.0):
        if not self._cli.wait_for_server(timeout_sec=5.0):
            return None, 'gripper action unavailable'
        g = GripperCommand.Goal()
        g.command.position = float(position)
        g.command.max_effort = float(max_effort)
        send = self._cli.send_goal_async(g)
        if wait_future(send, 5.0) != 'done':
            return None, 'gripper goal send timeout'
        gh = send.result()
        if gh is None or not gh.accepted:
            return None, 'gripper goal rejected'
        rf = gh.get_result_async()
        if wait_future(rf, timeout_s) != 'done':
            return None, 'gripper result timeout'
        return rf.result().result, None


class PlanningSceneOps:
    """Add / attach / detach-move / remove collision objects via ApplyPlanningScene."""

    def __init__(self, node, service='/apply_planning_scene',
                 get_service='/get_planning_scene'):
        self._apply = node.create_client(ApplyPlanningScene, service,
                                         callback_group=ReentrantCallbackGroup())
        self._get = node.create_client(GetPlanningScene, get_service,
                                       callback_group=ReentrantCallbackGroup())
        self._node = node

    def _apply_scene(self, scene):
        if not self._apply.wait_for_service(timeout_sec=5.0):
            return False, 'apply_planning_scene unavailable'
        scene.is_diff = True
        req = ApplyPlanningScene.Request()
        req.scene = scene
        fut = self._apply.call_async(req)
        if wait_future(fut, 10.0) != 'done':
            return False, 'apply_planning_scene timeout'
        resp = fut.result()
        return bool(resp.success), ''

    def add_box(self, name, position, size, frame='world'):
        co = CollisionObject()
        co.header.frame_id = frame
        co.id = name
        sp = SolidPrimitive()
        sp.type = SolidPrimitive.BOX
        sp.dimensions = list(size)
        co.primitives.append(sp)
        co.primitive_poses.append(pose_msg(position, (0.0, 0.0, 0.0, 1.0)))
        co.operation = CollisionObject.ADD
        scene = PlanningScene()
        scene.world.collision_objects.append(co)
        return self._apply_scene(scene)

    def attach(self, name, link='end_effector_link'):
        aco = AttachedCollisionObject()
        aco.link_name = link
        aco.object.id = name
        aco.object.operation = CollisionObject.ADD
        scene = PlanningScene()
        scene.robot_state.attached_collision_objects.append(aco)
        scene.robot_state.is_diff = True
        return self._apply_scene(scene)

    def detach_to_world(self, name, position, size, frame='world'):
        aco = AttachedCollisionObject()
        aco.object.id = name
        aco.object.operation = CollisionObject.REMOVE
        scene = PlanningScene()
        scene.robot_state.attached_collision_objects.append(aco)
        scene.robot_state.is_diff = True
        co = CollisionObject()
        co.header.frame_id = frame
        co.id = name
        sp = SolidPrimitive()
        sp.type = SolidPrimitive.BOX
        sp.dimensions = list(size)
        co.primitives.append(sp)
        co.primitive_poses.append(pose_msg(position, (0.0, 0.0, 0.0, 1.0)))
        co.operation = CollisionObject.ADD
        scene.world.collision_objects.append(co)
        return self._apply_scene(scene)

    def remove(self, name):
        co = CollisionObject()
        co.id = name
        co.operation = CollisionObject.REMOVE
        scene = PlanningScene()
        scene.world.collision_objects.append(co)
        return self._apply_scene(scene)

    def is_attached(self, name):
        if not self._get.wait_for_service(timeout_sec=5.0):
            return False, 'get_planning_scene unavailable'
        req = GetPlanningScene.Request()
        fut = self._get.call_async(req)
        if wait_future(fut, 10.0) != 'done':
            return False, 'get_planning_scene timeout'
        scene = fut.result().scene
        for aco in scene.robot_state.attached_collision_objects:
            if aco.object.id == name:
                return True, ''
        return False, ''
