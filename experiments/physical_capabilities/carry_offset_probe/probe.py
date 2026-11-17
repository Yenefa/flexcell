#!/usr/bin/env python3
"""Read-only carry-offset probe for issue #261.

`observe_server` publishes WorldState inside the `observe` action, not on a timer,
so a plain subscriber sees snapshots only at task decision points. The probe
therefore sends one `observe` goal at a time (mode `action`, the default) and
consumes the returned WorldState. Mode `topic` still subscribes for setups that
publish periodically.

It creates no publisher and no control service client: the probe only asks for
observations. If it dies, the task is unaffected.

Run:
    python3 probe.py --out /artifacts/carry-offset --object target_box_a
"""
import argparse
import json
import pathlib

from recorder import CarryOffsetRecorder

try:  # keep the module importable for offline tests
    import rclpy
    from rclpy.action import ActionClient
    from rclpy.executors import ExternalShutdownException
    from rclpy.node import Node
    from flexcell_interfaces.action import Observe
    from flexcell_interfaces.msg import CarryState, WorldState
except ImportError:  # pragma: no cover - exercised only without a ROS install
    rclpy = None
    ActionClient = None
    ExternalShutdownException = RuntimeError
    Node = object
    Observe = None
    CarryState = WorldState = None


def _pose(msg):
    return ((msg.position.x, msg.position.y, msg.position.z),
            (msg.orientation.x, msg.orientation.y,
             msg.orientation.z, msg.orientation.w))


def snapshot_from(msg):
    """WorldState -> the plain dict the recorder consumes."""
    objects = {}
    for obj in msg.objects:
        objects[obj.name] = dict(pose=_pose(obj.pose),
                                 available=obj.available,
                                 pose_age_s=obj.pose_age_s)
    return dict(revision=msg.revision,
                source=msg.source,
                objects=objects,
                robot=dict(ee_frame=msg.robot.ee_frame,
                           ee_pose=_pose(msg.robot.ee_pose)))


class CarryOffsetProbe(Node):
    """Read-only adapter: observations in, newline-delimited samples out."""

    def __init__(self, out, object_name, rate_hz, max_age_s, settle_s=1.0,
                 mode='action'):
        super().__init__('carry_offset_probe')
        out = pathlib.Path(out)
        out.mkdir(parents=True, exist_ok=True)
        self.recorder = CarryOffsetRecorder(object_name, rate_hz, max_age_s, settle_s)
        self.stream = (out / 'carry_offset.jsonl').open('a')
        self.skip_stream = (out / 'carry_offset_skips.jsonl').open('a')
        self._pending = False

        self.create_subscription(CarryState, '/flexcell/carry_state',
                                 self._on_carry, 10)
        if mode == 'action' and Observe is not None:
            self._client = ActionClient(self, Observe, 'observe')
            self.create_timer(1.0 / rate_hz, self._request)
        else:
            self._client = None
            self.create_subscription(WorldState, '/flexcell/world_state',
                                     self._on_world, 10)
            self.create_timer(1.0 / rate_hz, self._tick)

    def _request(self):
        """One observe goal in flight; the result carries a fresh WorldState."""
        if self._pending or not self._client.server_is_ready():
            return
        goal = Observe.Goal()
        goal.refresh = True
        goal.max_age_s = float(self.recorder.max_age_s)
        self._pending = True
        self._client.send_goal_async(goal).add_done_callback(self._on_goal)

    def _on_goal(self, future):
        handle = future.result()
        if handle is None or not handle.accepted:
            self._pending = False
            return
        handle.get_result_async().add_done_callback(self._on_result)

    def _on_result(self, future):
        self._pending = False
        result = future.result()
        world = getattr(getattr(result, 'result', None), 'world_state', None)
        if world is not None:
            self.recorder.on_world(snapshot_from(world))
        self.recorder.tick(self.get_clock().now().nanoseconds)
        self._flush()

    def _on_world(self, msg):
        self.recorder.on_world(snapshot_from(msg))

    def _on_carry(self, msg):
        self.recorder.on_carry(msg.engaged, msg.object_id,
                               self.get_clock().now().nanoseconds)
        self._flush()

    def _tick(self):
        self.recorder.tick(self.get_clock().now().nanoseconds)
        self._flush()

    def _flush(self):
        while self.recorder.rows:
            self.stream.write(json.dumps(self.recorder.rows.pop(0)) + '\n')
        while self.recorder.skips:
            self.skip_stream.write(
                json.dumps(self.recorder.skips.pop(0)) + '\n')
        self.stream.flush()
        self.skip_stream.flush()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=pathlib.Path, required=True)
    parser.add_argument('--object', default='target_box_a')
    parser.add_argument('--rate-hz', type=float, default=20.0)
    parser.add_argument('--max-age-s', type=float, default=0.5)
    parser.add_argument('--settle-s', type=float, default=1.0)
    parser.add_argument('--mode', choices=('action', 'topic'), default='action')
    args = parser.parse_args(argv)

    if rclpy is None:
        raise SystemExit('rclpy is not available; this node needs a ROS install')

    rclpy.init()
    node = CarryOffsetProbe(args.out, args.object, args.rate_hz, args.max_age_s,
                            args.settle_s, args.mode)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:  # context already shut down by a signal handler
            pass


if __name__ == '__main__':
    main()
