#!/usr/bin/env python3
"""FlexCell Observe skill server (Week 1).

Ground-truth world snapshot: tracked object poses (gz ground truth) +
end-effector pose (TF). Bumps the canonical world revision whenever a tracked
object moves past an epsilon. Deterministic; no LLM anywhere.
"""

import time

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.duration import Duration
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.time import Time

from geometry_msgs.msg import PoseStamped
from sensor_msgs.msg import JointState
from std_msgs.msg import Header
from tf2_ros import Buffer, TransformListener

from flexcell_interfaces.action import Observe
from flexcell_interfaces.msg import WorldObject, WorldState

from flexcell_skills.common import JsonlLog, dist3, gz_publish, new_evidence, pose_msg, sample_gz_pose

R = Observe.Result
F = Observe.Feedback


class ObserveServer(Node):

    def __init__(self):
        super().__init__('observe_server')

        self.declare_parameter('tracked_objects', ['target_box'])
        self.declare_parameter('move_epsilon_m', 0.002)
        self.declare_parameter('base_frame', 'world')
        self.declare_parameter('end_effector_link', 'end_effector_link')
        self.declare_parameter('joint_states_topic', '/joint_states')
        self.declare_parameter('world_state_topic', '/flexcell/world_state')
        self.declare_parameter('attach_topic', '/flexcell/target_box/attach')
        self.declare_parameter('log_dir', '~/.ros/flexcell')
        self.declare_parameter('log_file', 'observe.jsonl')

        gp = self.get_parameter
        self._tracked = list(gp('tracked_objects').value)
        self._eps = float(gp('move_epsilon_m').value)
        self._base = gp('base_frame').value
        self._ee = gp('end_effector_link').value
        self._log = JsonlLog(self, gp('log_dir').value, gp('log_file').value)
        attach_topic = gp('attach_topic').value

        # sizes: one param per tracked object (lists of lists are not ROS params)
        self._sizes = {}
        for name in self._tracked:
            key = 'object_%s_size' % name
            self.declare_parameter(key, [0.035, 0.035, 0.035])
            self._sizes[name] = list(gp(key).value)

        # ---------------- state ----------------
        self._revision = 0
        self._last = {}          # name -> position[3]
        self._js = None
        self._seq = 0

        self._cbg = ReentrantCallbackGroup()
        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self, spin_thread=False)
        self.create_subscription(
            JointState, gp('joint_states_topic').value, self._on_js, 50,
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
            'Observe server up | tracked=%s eps=%.4fm base=%s ee=%s'
            % (self._tracked, self._eps, self._base, self._ee))

    def _on_js(self, msg):
        self._js = msg

    def _snapshot(self, refresh):
        notes = []
        objects = []
        moved_any = False
        for name in self._tracked:
            sampled, err = sample_gz_pose(name)
            if sampled is None:
                notes.append('%s: unavailable (%s)' % (name, err))
                continue
            position, quat = sampled
            last = self._last.get(name)
            if last is None or dist3(position, last) > self._eps:
                self._revision += 1
                if last is not None:
                    moved_any = True
            self._last[name] = position
            wo = WorldObject()
            wo.name = name
            wo.pose = pose_msg(position, quat)
            wo.size = self._sizes[name]
            objects.append(wo)

        ee_note = 'ee: unavailable'
        try:
            tr = self._tf_buffer.lookup_transform(
                self._base, self._ee, Time(), Duration(seconds=1.0))
            t = tr.transform.translation
            ee_note = 'ee: [%.4f %.4f %.4f]' % (t.x, t.y, t.z)
        except Exception as exc:  # noqa: BLE001
            ee_note = 'ee: lookup failed (%s)' % exc
        notes.append(ee_note)
        if self._js is not None:
            notes.append('joints: %d states' % len(self._js.name))
        if moved_any:
            notes.append('revision bumped: tracked object moved past %.3fm' % self._eps)

        ws = WorldState()
        ws.header = Header()
        ws.header.stamp = self.get_clock().now().to_msg()
        ws.header.frame_id = self._base
        ws.revision = self._revision
        ws.objects = objects
        ws.notes = notes
        return ws, None

    def _execute(self, goal_handle):
        t0 = time.monotonic()
        goal = goal_handle.request
        self._seq += 1
        rid, evidence = new_evidence(goal.request_id if hasattr(goal, 'request_id') else '', self._seq)

        ws, err = self._snapshot(bool(goal.refresh))
        res = R()
        rec = {
            'request_id': rid,
            'evidence_id': evidence,
            'refresh': bool(goal.refresh),
            'revision': self._revision,
            'notes': list(ws.notes) if ws is not None else [],
        }
        if err is not None:
            res.outcome = R.OUTCOME_FAILED
            res.error_code = R.ERR_WORLD_STATE_UNAVAILABLE
            res.detail = err
            res.world_state = WorldState()
            rec.update(outcome='FAILED', error_code=res.error_code)
            self._log.write(rec)
            goal_handle.abort()
            return res

        self._pub.publish(ws)
        res.outcome = R.OUTCOME_SUCCEEDED
        res.error_code = R.ERR_NONE
        res.world_state = ws
        res.detail = '; '.join(ws.notes)
        rec.update(outcome='SUCCEEDED', detail=res.detail, evidence_id=evidence)
        self._log.write(rec)
        goal_handle.succeed()
        return res


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
