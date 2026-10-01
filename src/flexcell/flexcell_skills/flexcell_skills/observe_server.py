#!/usr/bin/env python3
"""FlexCell Observe skill server v2 (Week-1.5; snapshot schema v2 since issue #3).

Canonical WorldState snapshot with STRUCTURED fields (schema v2):
  robot   : joint names/positions + end-effector pose
  objects : ground-truth poses + availability
  carry   : what the carry BACKEND believes (never physical evidence)
  zones   : semantic demo zones, occupancy derived from ground truth
  source  : always SIMULATION_GROUND_TRUTH in this stage

Bumps the canonical world revision whenever a tracked object moves past an
epsilon. Deterministic; no LLM anywhere.
"""

import time
import copy

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.duration import Duration
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy
from rclpy.time import Time

from geometry_msgs.msg import Point, Pose
from sensor_msgs.msg import JointState
from std_msgs.msg import Header
from tf2_ros import Buffer, TransformListener

from flexcell_interfaces.action import Observe
from flexcell_interfaces.srv import QueryCarry
from flexcell_interfaces.msg import (
    CarryState, RobotStateSummary, TaskContext, WorldObject, WorldState, ZoneState)

from flexcell_skills.common import (
    JsonlLog, crash_detail, dist3, new_evidence, pose_msg,
    sample_gz_pose_age, wait_future)
from flexcell_skills.contracts.skill_result import derive_status

R = Observe.Result

class CarrySnapshotUnavailable(RuntimeError):
    pass


ARM_JOINTS = ['joint1', 'joint2', 'joint3', 'joint4']


class ObserveServer(Node):

    def __init__(self):
        super().__init__('observe_server')

        self.declare_parameter('tracked_objects', ['target_box_a', 'target_box_b'])
        self.declare_parameter('move_epsilon_m', 0.002)
        self.declare_parameter('base_frame', 'world')
        self.declare_parameter('end_effector_link', 'end_effector_link')
        self.declare_parameter('joint_states_topic', '/joint_states')
        self.declare_parameter('world_state_topic', '/flexcell/world_state')
        self.declare_parameter('carry_state_topic', '/flexcell/carry_state')
        self.declare_parameter('carry_query_service', '/flexcell/carry_snapshot')
        self.declare_parameter('zones', ['zone_1', 'zone_2'])
        self.declare_parameter('source', 'SIMULATION_GROUND_TRUTH')
        self.declare_parameter('log_dir', '~/.ros/flexcell')
        self.declare_parameter('log_file', 'observe.jsonl')

        gp = self.get_parameter
        self._tracked = list(gp('tracked_objects').value)
        self._eps = float(gp('move_epsilon_m').value)
        self._base = gp('base_frame').value
        self._ee = gp('end_effector_link').value
        self._source = gp('source').value
        self._log = JsonlLog(self, gp('log_dir').value, gp('log_file').value)

        # per-object sizes and per-zone specs (lists of lists are not ROS params)
        self._sizes = {}
        for name in self._tracked:
            key = 'object_%s_size' % name
            self.declare_parameter(key, [0.035, 0.035, 0.035])
            self._sizes[name] = list(gp(key).value)
        self._zones = []
        for zid in list(gp('zones').value):
            self.declare_parameter('zone_%s_x' % zid, 0.0)
            self.declare_parameter('zone_%s_y' % zid, 0.0)
            self.declare_parameter('zone_%s_z' % zid, 0.0175)
            self.declare_parameter('zone_%s_radius' % zid, 0.06)
            self._zones.append({
                'id': zid,
                'x': float(gp('zone_%s_x' % zid).value),
                'y': float(gp('zone_%s_y' % zid).value),
                'z': float(gp('zone_%s_z' % zid).value),
                'radius': float(gp('zone_%s_radius' % zid).value),
            })

        # ---------------- state ----------------
        self._revision = 0
        self._last = {}          # name -> position[3]
        self._js = None
        self._carry = None       # last latched CarryState from the backend
        self._seq = 0

        self._cbg = ReentrantCallbackGroup()
        self._carry_query = self.create_client(
            QueryCarry, gp('carry_query_service').value, callback_group=self._cbg)
        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self, spin_thread=False)
        self.create_subscription(
            JointState, gp('joint_states_topic').value, self._on_js, 50,
            callback_group=self._cbg)

        qos = QoSProfile(depth=1)
        qos.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL
        qos.reliability = QoSReliabilityPolicy.RELIABLE
        self.create_subscription(
            CarryState, gp('carry_state_topic').value, self._on_carry, qos,
            callback_group=self._cbg)

        self._pub = self.create_publisher(
            WorldState, gp('world_state_topic').value, 1)

        self._server = ActionServer(
            self, Observe, 'observe',
            execute_callback=self._execute,
            goal_callback=lambda req: GoalResponse.ACCEPT,
            cancel_callback=lambda gh: CancelResponse.ACCEPT,
            callback_group=self._cbg)

        self.get_logger().info(
            'Observe server v2 up | tracked=%s zones=%s eps=%.4fm source=%s'
            % (self._tracked, [z['id'] for z in self._zones], self._eps, self._source))

    def _on_js(self, msg):
        self._js = msg

    def _on_carry(self, msg):
        self._carry = copy.deepcopy(msg)
        self._carry_rx_mono = time.monotonic()

    def _current_carry(self):
        if not self._carry_query.wait_for_service(timeout_sec=2.0):
            raise CarrySnapshotUnavailable('carry snapshot service unavailable')
        for _ in range(2):
            before = time.monotonic_ns()
            future = self._carry_query.call_async(QueryCarry.Request())
            if wait_future(future, 2.0) == 'done':
                result = future.result()
                if not result.success:
                    raise CarrySnapshotUnavailable(result.detail)
                state = copy.deepcopy(result.state)
                self._log.write({'event': 'carry_snapshot', 'request_mono_ns': before,
                                 'reply_mono_ns': time.monotonic_ns(),
                                 'revision': result.revision, 'session': result.session,
                                 'engaged': state.engaged, 'object_id': state.object_id,
                                 'cached_engaged': self._carry.engaged if self._carry else None,
                                 'cached_object': self._carry.object_id if self._carry else None})
                return state
            self._carry_query.remove_pending_request(future)
        raise CarrySnapshotUnavailable('carry snapshot response timed out')

    # ------------------------------------------------------------ snapshot
    def _snapshot(self):
        notes = []
        objects = []
        moved_any = False
        for name in self._tracked:
            sampled, age_s, err = sample_gz_pose_age(name)
            wo = WorldObject()
            wo.name = name
            wo.klass = 'box'
            wo.size = self._sizes[name]
            if sampled is None:
                wo.available = False
                wo.pose = Pose()
                wo.pose.orientation.w = 1.0
                objects.append(wo)
                notes.append('%s: unavailable (%s)' % (name, err))
                continue
            position, quat = sampled
            last = self._last.get(name)
            if last is None or dist3(position, last) > self._eps:
                self._revision += 1
                if last is not None:
                    moved_any = True
            self._last[name] = position
            wo.available = True
            wo.pose = pose_msg(position, quat)
            wo.pose_age_s = age_s
            objects.append(wo)

        # robot summary
        robot = RobotStateSummary()
        robot.ee_frame = self._ee
        robot.ee_pose = Pose()
        robot.ee_pose.orientation.w = 1.0
        if self._js is not None:
            idx = {n: i for i, n in enumerate(self._js.name)}
            names, positions = [], []
            for j in ARM_JOINTS:
                if j in idx:
                    names.append(j)
                    positions.append(float(self._js.position[idx[j]]))
            robot.joint_names = names
            robot.positions = positions
            for n in self._js.name:                  # v2: gripper aperture (first gripper* joint)
                if 'gripper' in n:
                    robot.gripper_joint_name = n
                    robot.gripper_position = float(self._js.position[idx[n]])
                    robot.has_gripper_state = True
                    break
        try:
            tr = self._tf_buffer.lookup_transform(
                self._base, self._ee, Time(), Duration(seconds=1.0))
            t = tr.transform.translation
            robot.ee_pose = pose_msg([t.x, t.y, t.z],
                                     [tr.transform.rotation.x, tr.transform.rotation.y,
                                      tr.transform.rotation.z, tr.transform.rotation.w])
        except Exception as exc:  # noqa: BLE001
            notes.append('ee: lookup failed (%s)' % exc)

        # A transition-only topic can remain cached indefinitely. Query the
        # backend for this snapshot; missing confirmation is an observation error.
        carry = self._current_carry()
        if carry.engaged:
            notes.append('carry: confirmed backend engaged on %s' % carry.object_id)

        # zones: occupancy derived from ground truth (never faked)
        zones = []
        for z in self._zones:
            zs = ZoneState()
            zs.id = z['id']
            c = Point()
            c.x, c.y, c.z = z['x'], z['y'], z['z']
            zs.center = c
            zs.radius = z['radius']
            occupant = ''
            for wo in objects:
                if not wo.available:
                    continue
                d = dist3([wo.pose.position.x, wo.pose.position.y, wo.pose.position.z],
                          [z['x'], z['y'], z['z']])
                if d <= z['radius']:
                    occupant = wo.name
                    break
            if not occupant:
                zs.occupancy = ZoneState.OCCUPANCY_FREE
            else:
                zs.occupancy = ZoneState.OCCUPANCY_OCCUPIED
            zs.occupied_by = occupant
            zones.append(zs)

        if moved_any:
            notes.append('revision bumped: tracked object moved past %.3fm' % self._eps)

        ws = WorldState()
        ws.header = Header()
        ws.header.stamp = self.get_clock().now().to_msg()
        ws.header.frame_id = self._base
        ws.revision = self._revision
        ws.source = self._source
        ws.schema_version = '2.0'
        ws.robot = robot
        ws.objects = objects
        ws.carry = carry
        ws.zones = zones
        ws.task = TaskContext()   # executor-owned at decide() time (ADR-002); default here
        ws.notes = notes
        return ws

    def _execute(self, goal_handle):
        t_start = time.monotonic()
        self._seq += 1
        rid, evidence = new_evidence('', self._seq)
        res = R()
        rec = {'request_id': rid, 'evidence_id': evidence}

        def finish(outcome, error, detail, world_state=None):
            # single finalization point (SkillResult v2: status derives here)
            res.outcome = outcome
            res.status = derive_status('OBSERVE', outcome)
            res.error_code = error
            res.detail = detail
            res.evidence_id = evidence
            if world_state is not None:
                res.world_state = world_state
            rec.update(outcome=str(outcome), error_code=int(error),
                       status=int(res.status), detail=detail,
                       elapsed_ms=int((time.monotonic() - t_start) * 1000))
            self._log.write(rec)
            if outcome == R.OUTCOME_SUCCEEDED:
                goal_handle.succeed()
            elif outcome == R.OUTCOME_CANCELED:
                goal_handle.canceled()
            else:
                goal_handle.abort()
            return res

        try:
            if goal_handle.is_cancel_requested:
                return finish(R.OUTCOME_CANCELED, R.ERR_CANCELED,
                              'canceled before snapshot')
            ws = self._snapshot()
            rec.update(
                revision=self._revision,
                available=[o.name for o in ws.objects if o.available],
                carry_engaged=ws.carry.engaged,
                zones={z.id: int(z.occupancy) for z in ws.zones},
            )
            self._pub.publish(ws)
            return finish(R.OUTCOME_SUCCEEDED, R.ERR_NONE,
                          '; '.join(ws.notes), world_state=ws)
        except CarrySnapshotUnavailable as exc:
            return finish(R.OUTCOME_FAILED, R.ERR_WORLD_STATE_UNAVAILABLE, str(exc))
        except Exception as exc:  # crash guard (issue #20): a raising execute
            # callback must become a typed FAILURE - rclpy's fallback default
            # Result has outcome=0, which reads as OUTCOME_SUCCEEDED
            return finish(R.OUTCOME_FAILED, R.ERR_INTERNAL, crash_detail(exc))


def main(args=None):
    rclpy.init(args=args)
    node = ObserveServer()
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
