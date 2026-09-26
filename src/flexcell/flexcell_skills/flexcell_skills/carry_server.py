#!/usr/bin/env python3
"""FlexCell carry servo (Week 1): teleport-servo magnetic carry.

While engaged, pins the object to the gripper by re-issuing the gz set_pose
service at a fixed period, at the gripper-to-object offset frozen at engage
time. Deterministic: no gz plugins, no toggle state, no one-shot delivery
races (all three measured as failure modes with DetachableJoint on this box).

Declared grasp mode: magnetic (teleport servo). Contact-pinch grasping is
future hardening. Everything downstream still measures ground truth - if the
servo dies, the follow check and the place verification fail honestly.
"""

import threading
import time

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.duration import Duration
from rclpy.time import Time

from geometry_msgs.msg import Vector3
from std_msgs.msg import Empty as EmptyMsg
from tf2_ros import Buffer, TransformListener

from flexcell_skills.common import JsonlLog


class CarryServer(Node):

    def __init__(self):
        super().__init__('carry_server')

        self.declare_parameter('world', 'empty')
        self.declare_parameter('model', 'target_box')
        self.declare_parameter('carry_period_s', 0.1)
        self.declare_parameter('base_frame', 'world')
        self.declare_parameter('end_effector_link', 'end_effector_link')
        self.declare_parameter('start_topic', '/flexcell/carry_start')
        self.declare_parameter('stop_topic', '/flexcell/carry_stop')
        self.declare_parameter('log_dir', '~/.ros/flexcell')
        self.declare_parameter('log_file', 'carry.jsonl')

        gp = self.get_parameter
        self._world = gp('world').value
        self._model = gp('model').value
        self._period = float(gp('carry_period_s').value)
        self._base = gp('base_frame').value
        self._ee_link = gp('end_effector_link').value
        self._log = JsonlLog(self, gp('log_dir').value, gp('log_file').value)

        import gz.transport13 as gz_transport
        from gz.msgs10 import boolean_pb2, pose_pb2
        self._gz_node = gz_transport.Node()
        self._Pose = pose_pb2.Pose
        self._Boolean = boolean_pb2.Boolean
        self._service = '/world/%s/set_pose' % self._world

        self._offset = None
        self._stop_evt = threading.Event()
        self._thread = None

        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self, spin_thread=False)

        self.create_subscription(
            Vector3, gp('start_topic').value, self._on_start, 10)
        self.create_subscription(
            EmptyMsg, gp('stop_topic').value, self._on_stop, 10)

        self.get_logger().info(
            'Carry servo up | model=%s service=%s period=%.2fs'
            % (self._model, self._service, self._period))

    def _on_start(self, msg):
        offset = [float(msg.x), float(msg.y), float(msg.z)]
        self._stop_evt.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._offset = offset
        self._stop_evt = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self.get_logger().info(
            'carry ENGAGED offset=[%.3f %.3f %.3f]' % tuple(offset))
        self._log.write({'event': 'start', 'offset': offset})

    def _on_stop(self, _msg):
        self._stop_evt.set()
        self.get_logger().info('carry RELEASED')
        self._log.write({'event': 'stop'})

    def _ee(self):
        try:
            tr = self._tf_buffer.lookup_transform(
                self._base, self._ee_link, Time(), Duration(seconds=0.5))
            t = tr.transform.translation
            return [t.x, t.y, t.z]
        except Exception:  # noqa: BLE001 - keep the last pinned pose on TF gaps
            return None

    def _loop(self):
        while not self._stop_evt.is_set():
            ee = self._ee()
            if ee is not None and self._offset is not None:
                req = self._Pose()
                req.name = self._model
                req.position.x = ee[0] + self._offset[0]
                req.position.y = ee[1] + self._offset[1]
                req.position.z = ee[2] + self._offset[2]
                req.orientation.w = 1.0
                try:
                    self._gz_node.request(self._service, req, self._Pose,
                                          self._Boolean, 300)
                except Exception as exc:  # noqa: BLE001 - servo must not die
                    self.get_logger().warn('set_pose failed: %s' % exc)
            self._stop_evt.wait(self._period)


def main(args=None):
    rclpy.init(args=args)
    node = CarryServer()
    ex = MultiThreadedExecutor(num_threads=4)
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
