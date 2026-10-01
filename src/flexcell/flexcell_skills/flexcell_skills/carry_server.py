#!/usr/bin/env python3
"""Simulation-only magnetic carry with an explicit physics backend.

Declared simulation-only backend: pins the carried object to the gripper by
re-issuing the gz set_pose service at a fixed period, at the gripper-to-object
offset frozen at engage time. The default 'teleport' preserves the v2 baseline.
'velocity_servo' uses a world plugin to constrain pose and velocity each step
under a bounded session lease. Release must confirm removal of constraints.

v2 changes:
- engage command is a JSON std_msgs/String (object id + offset + frame), so the
  backend is object-agnostic;
- publishes a LATCHED /flexcell/carry_state (CarryState msg) whenever state
  changes, so pick / place / reset can READ what the backend believes instead
  of guessing. CarryState is backend state, never physical evidence.
"""

import json
import math
import threading
import time
import uuid

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.duration import Duration
from rclpy.time import Time
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy

from geometry_msgs.msg import Vector3
from std_msgs.msg import Empty as EmptyMsg
from std_msgs.msg import String as StringMsg
from std_srvs.srv import Trigger
from tf2_ros import Buffer, TransformListener

from flexcell_interfaces.msg import CarryState
from flexcell_interfaces.srv import EngageCarry

from flexcell_skills.common import JsonlLog


class CarryServer(Node):

    def __init__(self):
        super().__init__('carry_server')

        self.declare_parameter('world', 'empty')
        self.declare_parameter('carry_period_s', 0.1)
        self.declare_parameter('carry_backend', 'teleport')
        self.declare_parameter('base_frame', 'world')
        self.declare_parameter('end_effector_link', 'end_effector_link')
        self.declare_parameter('start_topic', '/flexcell/carry_start')
        self.declare_parameter('stop_topic', '/flexcell/carry_stop')
        self.declare_parameter('state_topic', '/flexcell/carry_state')
        self.declare_parameter('release_service', '/flexcell/carry_release')
        self.declare_parameter('engage_service', '/flexcell/carry_engage')
        self.declare_parameter('log_dir', '~/.ros/flexcell')
        self.declare_parameter('log_file', 'carry.jsonl')

        gp = self.get_parameter
        self._world = gp('world').value
        self._period = float(gp('carry_period_s').value)
        self._backend = gp('carry_backend').value
        if self._backend not in ('teleport', 'velocity_servo'):
            raise ValueError('unknown carry backend')
        self._base = gp('base_frame').value
        self._ee_link = gp('end_effector_link').value
        self._log = JsonlLog(self, gp('log_dir').value, gp('log_file').value)

        import gz.transport13 as gz_transport
        from gz.msgs10 import boolean_pb2, pose_pb2, stringmsg_pb2
        self._gz_node = gz_transport.Node()
        self._Pose = pose_pb2.Pose
        self._Boolean = boolean_pb2.Boolean
        self._String = stringmsg_pb2.StringMsg
        self._service = '/world/%s/set_pose' % self._world
        self._guard = '/world/%s/flexcell/carry/' % self._world
        if self._backend == 'velocity_servo': self._service = self._guard + 'pin'

        self._object_id = ''
        self._offset = None
        self._stop_evt = threading.Event()
        self._thread = None
        self._session = ''
        self._retired_sessions = set()

        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self, spin_thread=False)

        # latched state topic: last value always available to late joiners
        qos = QoSProfile(depth=1)
        qos.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL
        qos.reliability = QoSReliabilityPolicy.RELIABLE
        self._state_pub = self.create_publisher(CarryState, gp('state_topic').value, qos)

        self.create_subscription(
            StringMsg, gp('start_topic').value, self._on_start, 10)
        self.create_subscription(
            EmptyMsg, gp('stop_topic').value, self._on_stop, 10)
        self.create_service(Trigger, gp('release_service').value, self._on_release)
        self.create_service(EngageCarry, gp('engage_service').value, self._on_engage)
        self.create_timer(0.2, self._check_worker)

        self._publish_state()
        self.get_logger().info(
            'Carry servo up | backend=%s service=%s period=%.2fs state=%s'
            % (self._backend, self._service, self._period, gp('state_topic').value))

    # ------------------------------------------------------------ state topic
    def _publish_state(self):
        msg = CarryState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self._base
        msg.engaged = self._offset is not None
        msg.object_id = self._object_id if msg.engaged else ''
        msg.reference_frame = self._base
        if self._offset is not None:
            msg.offset = [float(v) for v in self._offset]
        else:
            msg.offset = [0.0, 0.0, 0.0]
        self._state_pub.publish(msg)

    # ------------------------------------------------------------ commands
    def _on_start(self, msg):
        try:
            cmd = json.loads(msg.data)
            object_id = str(cmd['object'])
            offset = [float(cmd['offset'][0]), float(cmd['offset'][1]),
                      float(cmd['offset'][2])]
            if not object_id or not all(math.isfinite(v) for v in offset):
                raise ValueError('object and finite offset required')
        except (ValueError, KeyError, TypeError) as exc:
            self.get_logger().error('bad carry_start payload %r: %s' % (msg.data, exc))
            return
        self._engage(object_id, offset, uuid.uuid4().hex)

    def _on_engage(self, request, response):
        token = request.request_id
        offset = list(request.offset)
        valid = (len(token) == 32 and all(c in '0123456789abcdef' for c in token)
                 and request.object_id and request.reference_frame == self._base
                 and all(math.isfinite(v) for v in offset))
        response.session = token
        if not valid:
            response.success = False
            response.message = 'invalid carry identity, frame or offset'
            return response
        if token in self._retired_sessions:
            response.success = False
            response.message = 'carry session is retired'
            return response
        # Service callbacks share the default mutually exclusive callback group.
        # A repeated request cannot restart a session while its reply is lost.
        if self._session == token:
            response.success = (self._object_id == request.object_id
                                and self._offset == offset
                                and self._thread is not None and self._thread.is_alive())
        else:
            response.success = self._engage(request.object_id, offset, token)
        response.message = ('carry engaged and physics acknowledged' if response.success
                            else 'carry engage was not confirmed')
        return response

    def _engage(self, object_id, offset, session):
        if not self._on_stop(None):
            self.get_logger().error('cannot replace an unconfirmed carry session')
            return False
        if self._backend == 'velocity_servo':
            ee = self._ee()
            if ee is None or not self._guard_request('engage', self._pose(object_id, offset, ee, session)):
                # An ambiguous engage timeout must be followed by force release.
                self._guard_release('')
                self._retired_sessions.add(session)
                self.get_logger().error('velocity-servo engage was not confirmed')
                self._log.write({'event': 'engage_failed', 'object': object_id,
                                 'backend': self._backend, 'session': session})
                return False
        # state copies ride with the thread (audit P2): a replaced thread must
        # never pin the NEW object with a stale loop reading shared attrs
        stop_evt = threading.Event()
        self._object_id = object_id
        self._offset = offset
        self._stop_evt = stop_evt
        self._session = session
        self._thread = threading.Thread(target=self._loop,
                                        args=(object_id, offset, stop_evt, session),
                                        daemon=True)
        self._thread.start()
        self.get_logger().info(
            'carry ENGAGED object=%s offset=[%.3f %.3f %.3f]'
            % (object_id, offset[0], offset[1], offset[2]))
        self._log.write({'event': 'start', 'object': object_id, 'offset': offset,
                         'backend': self._backend, 'session': session})
        self._publish_state()
        return True

    def _on_stop(self, _msg):
        self._stop_evt.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        stopped = self._thread is None or not self._thread.is_alive()
        if not stopped:
            return False
        if getattr(self, '_backend', 'teleport') == 'velocity_servo':
            if not self._guard_release(''):
                self._log.write({'event': 'release_unconfirmed', 'backend': self._backend})
                return False
        if getattr(self, '_session', ''):
            self._retired_sessions.add(self._session)
        self._object_id = ''
        self._offset = None
        self._session = ''
        self.get_logger().info('carry RELEASED')
        self._log.write({'event': 'stop', 'backend': getattr(self, '_backend', 'teleport')})
        self._publish_state()
        return stopped

    def _on_release(self, _request, response):
        # Idempotent acknowledgement: no release success while a pin request
        # can still be in flight. The legacy stop topic remains for reset.
        response.success = self._on_stop(None)
        response.message = ('servo stopped and backend release confirmed' if response.success else
                            'servo thread or physics release was not confirmed')
        return response

    def _check_worker(self):
        if self._offset is not None and self._thread is not None and not self._thread.is_alive():
            self._log.write({'event': 'worker_ended', 'object': self._object_id})
            self._on_stop(None)

    def _guard_request(self, operation, request):
        try:
            return self._request_ok(self._gz_node.request(
                self._guard + operation, request, self._Pose, self._Boolean, 1000))
        except Exception as exc:
            self.get_logger().error('carry %s failed: %s' % (operation, type(exc).__name__))
            return False

    def _guard_release(self, session):
        request = self._String()
        request.data = session
        try:
            return self._request_ok(self._gz_node.request(
                self._guard + 'release', request, self._String, self._Boolean, 1000))
        except Exception as exc:
            self.get_logger().error('carry physics release failed: %s' % type(exc).__name__)
            return False

    def _pose(self, object_id, offset, ee, session):
        request = self._Pose()
        request.name = object_id
        request.position.x, request.position.y, request.position.z = [ee[i] + offset[i] for i in range(3)]
        request.orientation.w = 1.0
        if self._backend == 'velocity_servo':
            item = request.header.data.add()
            item.key = 'carry_session'
            item.value.append(session)
        return request

    # ------------------------------------------------------------ servo loop
    def _ee(self):
        try:
            tr = self._tf_buffer.lookup_transform(
                self._base, self._ee_link, Time(), Duration(seconds=0.5))
            t = tr.transform.translation
            return [t.x, t.y, t.z]
        except Exception:  # noqa: BLE001 - keep the last pinned pose on TF gaps
            return None

    @staticmethod
    def _request_ok(rep):
        """Interpret a gz set_pose request reply (audit P2: the return value
        used to be discarded - an engage whose every request failed looked
        identical to one pinning at 10Hz)."""
        if rep is None:
            return False
        if isinstance(rep, tuple):
            if len(rep) != 2 or not rep[0]:
                return False
            rep = rep[-1]
        return bool(getattr(rep, 'data', rep))

    def _loop(self, object_id, offset, stop_evt, session):
        consecutive_fail = 0
        while not stop_evt.is_set():
            ee = self._ee()
            if ee is not None and offset is not None:
                req = self._pose(object_id, offset, ee, session)
                before = time.monotonic_ns()
                try:
                    # short timeout: a blocking 300ms wait on a failing
                    # service silently stretched the servo from 10Hz to ~2Hz
                    # and the box crept to its pinned pose over seconds
                    rep = self._gz_node.request(self._service, req, self._Pose,
                                                self._Boolean, 1000 if self._backend == 'velocity_servo' else 100)
                except Exception as exc:  # noqa: BLE001 - servo must not die
                    consecutive_fail += 1
                    if consecutive_fail <= 3 or consecutive_fail % 20 == 0:
                        self.get_logger().warn(
                            'set_pose failed (%d consecutive): %s'
                            % (consecutive_fail, exc))
                else:
                    if self._request_ok(rep):
                        consecutive_fail = 0
                    else:
                        consecutive_fail += 1
                        if consecutive_fail <= 3 or consecutive_fail % 20 == 0:
                            self.get_logger().warn(
                                'set_pose rejected (%d consecutive)' % consecutive_fail)
                if self._backend == 'velocity_servo':
                    self._log.write({'event': 'pin', 'object': object_id, 'session': session,
                                     'target': [req.position.x, req.position.y, req.position.z],
                                     'request_mono_ns': before, 'reply_mono_ns': time.monotonic_ns(),
                                     'confirmed': consecutive_fail == 0})
                    if consecutive_fail >= 3: stop_evt.set()
                if consecutive_fail > 0 and (consecutive_fail <= 3
                                             or consecutive_fail % 20 == 0):
                    self._log.write({'event': 'set_pose_fail',
                                     'object': object_id,
                                     'consecutive': consecutive_fail})
            stop_evt.wait(self._period)


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
        node._on_stop(None)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
