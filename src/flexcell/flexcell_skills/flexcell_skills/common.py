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
import threading
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


# ---------------------------------------------------------------- gz ground truth
# One persistent Pose_V subscriber feeds every sample request. The gz CLI
# (`gz model -p`) races its own discovery handshake on every invocation and
# silently returns empty output under session churn (measured 2026-09-26).
# The gz-transport SUBSCRIPTION handshake is also one-shot and can fail at
# process startup (measured: observe's stream flowed while pick's never
# connected), so the listener self-heals: no data in 6s -> rebuild the node;
# stream stale >10s (e.g. world restart) -> reconnect.
_GZ_STREAM = {
    'lock': threading.Lock(),
    'poses': {},          # name -> (position[3], quat[4], last_seen_monotonic)
    'last_rx': 0.0,
    'thread': None,
    'world': None,
    'last_start': 0.0,    # restart backoff bookkeeping (thread-death self-heal)
}


def _gz_stream_loop(world):
    import gz.transport13 as gz_transport
    # importing the nested-class modules registers them in protobuf BEFORE any
    # callback deserializes a Pose_V - without this the callback thread dies
    # with "No message class registered for 'gz.msgs.Pose'" (and can segfault)
    from gz.msgs10 import pose_v_pb2, pose_pb2, header_pb2  # noqa: F401
    while True:
        node = gz_transport.Node()
        got_first = threading.Event()

        def cb(msg):
            now = time.monotonic()
            with _GZ_STREAM['lock']:
                for ent in msg.pose:
                    _GZ_STREAM['poses'][ent.name] = (
                        [ent.position.x, ent.position.y, ent.position.z],
                        [ent.orientation.x, ent.orientation.y,
                         ent.orientation.z, ent.orientation.w],
                        now)
                _GZ_STREAM['last_rx'] = now
            got_first.set()

        node.subscribe(type(pose_v_pb2.Pose_V()),
                       '/world/%s/dynamic_pose/info' % world, cb)
        got_first.wait(6.0)
        while True:
            time.sleep(1.0)
            with _GZ_STREAM['lock']:
                stale = time.monotonic() - _GZ_STREAM['last_rx'] > 10.0
            if stale:
                break   # rebuild the subscription with a fresh node


def _ensure_gz_pose_stream(world='empty'):
    with _GZ_STREAM['lock']:
        t = _GZ_STREAM['thread']
        if t is not None and t.is_alive() and _GZ_STREAM['world'] == world:
            return
        now = time.monotonic()
        if (t is not None and not t.is_alive()
                and now - _GZ_STREAM['last_start'] < 1.0):
            return   # died moments ago; avoid restart churn
        # self-heal (audit P2): a dead stream thread used to stay dead forever
        # - the process silently lost its ground-truth source while
        # _GZ_STREAM['thread'] still looked occupied
        _GZ_STREAM['last_start'] = now
        t = threading.Thread(target=_gz_stream_loop, args=(world,), daemon=True)
        _GZ_STREAM['thread'] = t
        _GZ_STREAM['world'] = world
        t.start()
    deadline = time.monotonic() + 4.0
    while time.monotonic() < deadline:
        with _GZ_STREAM['lock']:
            if _GZ_STREAM['last_rx'] > 0:
                return
        time.sleep(0.1)


def sample_gz_pose(model_name, timeout_s=6.0, world='empty', max_age_s=1.0):
    """Ground-truth model pose from the live gz Pose_V stream.

    Returns ((position[3], quat[4]), None) or (None, error). The error
    distinguishes 'pose stream is not flowing' (global observation failure,
    recoverable) from 'not seen in pose stream' (object-specific, e.g. the
    object was removed from the world).
    """
    _ensure_gz_pose_stream(world)
    deadline = time.monotonic() + timeout_s
    while True:
        with _GZ_STREAM['lock']:
            entry = _GZ_STREAM['poses'].get(model_name)
        if entry is not None and time.monotonic() - entry[2] <= max_age_s:
            return (entry[0], entry[1]), None
        if time.monotonic() >= deadline:
            with _GZ_STREAM['lock']:
                flowing = time.monotonic() - _GZ_STREAM['last_rx'] <= 3.0
            if not flowing:
                return None, ('pose stream is not flowing (no fresh entity '
                              'updates; gz transport may be wedged)')
            return None, ('model %r not seen in pose stream within %.1fs'
                          % (model_name, timeout_s))
        time.sleep(0.05)


def sample_gz_pose_age(model_name, timeout_s=6.0, world='empty', max_age_s=1.0):
    """Same contract as sample_gz_pose, additionally returning sample freshness.

    Returns ((position[3], quat[4]), age_s, None) or (None, -1.0, error).
    age_s = seconds since the pose stream last saw this entity (>= 0); it is
    the honest freshness signal behind WorldState v2 `pose_age_s`. The existing
    sample_gz_pose signature is untouched - verify_server and observe_server
    keep their current behavior.
    """
    _ensure_gz_pose_stream(world)
    deadline = time.monotonic() + timeout_s
    while True:
        with _GZ_STREAM['lock']:
            entry = _GZ_STREAM['poses'].get(model_name)
        if entry is not None and time.monotonic() - entry[2] <= max_age_s:
            return (entry[0], entry[1]), max(0.0, time.monotonic() - entry[2]), None
        if time.monotonic() >= deadline:
            with _GZ_STREAM['lock']:
                flowing = time.monotonic() - _GZ_STREAM['last_rx'] <= 3.0
            if not flowing:
                return None, -1.0, ('pose stream is not flowing (no fresh entity '
                                    'updates; gz transport may be wedged)')
            return None, -1.0, ('model %r not seen in pose stream within %.1fs'
                                % (model_name, timeout_s))
        time.sleep(0.05)


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


def crash_detail(exc):
    """One-line crash report for the execute-callback crash guard (issue #20).

    rclpy's fallback for a raising execute callback is a default Result whose
    outcome=0 reads as SUCCEEDED/VERIFIED - the Week-1 PLACE ghost success.
    Skill servers convert unhandled exceptions into typed ERR_INTERNAL
    failures carrying this detail instead.
    """
    import traceback
    tail = ' | '.join(
        line.strip() for line in traceback.format_exc().strip().splitlines()[-3:])
    return 'unhandled exception: %s: %s (%s)' % (type(exc).__name__, exc, tail)


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


def interruptible_sleep(seconds, cancel_check=None, step=0.05):
    """Sleep in small steps; return True as soon as cancel_check() fires.

    Skill servers use this instead of time.sleep() so a cancel landing during
    a settle/engage pause is noticed within ~step seconds instead of after
    the full sleep (audit P0-3).
    """
    end = time.monotonic() + seconds
    while True:
        if cancel_check is not None and cancel_check():
            return True
        remaining = end - time.monotonic()
        if remaining <= 0.0:
            return cancel_check is not None and cancel_check()
        time.sleep(min(step, remaining))


class MoveToPoseClient:
    """Blocking helper around the Day-2 MoveToPose action."""

    def __init__(self, node, action):
        self._cli = ActionClient(node, MoveToPose, action,
                                 callback_group=ReentrantCallbackGroup())

    def wait_ready(self, timeout_s=10.0):
        return self._cli.wait_for_server(timeout_sec=timeout_s)

    def call(self, position, profile='demo_slow', deadline_ms=30000,
             timeout_s=60.0, frame='world', request_id='', cancel_check=None):
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
            if cancel_check is not None and cancel_check():
                # caller cancel: forward it so the arm actually stops
                # (preempt + stop confirmation), then surface the server's
                # CANCELED result (audit P0-3 - the motion used to run to
                # completion and the caller still got SUCCEEDED)
                gh.cancel_goal_async()
                t_c = time.monotonic()
                while not rf.done() and time.monotonic() - t_c < 15.0:
                    time.sleep(0.05)
                if not rf.done():
                    return None, 'move_to_pose canceled: stop confirmation timeout'
                return rf.result().result, None
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
