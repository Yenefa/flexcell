#!/usr/bin/env python3
"""Inject stale carry-topic state at IDLE; confirm Observe uses live authority."""
import json
import time
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
from std_msgs.msg import String
from flexcell_interfaces.msg import CarryState
from flexcell_interfaces.action import Observe
from flexcell_interfaces.srv import QueryCarry


def main():
    rclpy.init()
    node = Node('carry_freshness_probe')
    qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                     reliability=ReliabilityPolicy.RELIABLE)
    task = []
    node.create_subscription(String, '/flexcell/task_state', lambda msg: task.append(msg.data), qos)
    publisher = node.create_publisher(CarryState, '/flexcell/carry_state', qos)
    query = node.create_client(QueryCarry, '/flexcell/carry_snapshot')
    observe = ActionClient(node, Observe, '/observe')
    def await_future(future, timeout=10):
        rclpy.spin_until_future_complete(node, future, timeout_sec=timeout)
        if not future.done(): raise TimeoutError('probe response timeout')
        return future.result()
    try:
        deadline = time.monotonic()+8
        while not task and time.monotonic() < deadline: rclpy.spin_once(node, timeout_sec=.1)
        if not task or task[-1] != 'IDLE': raise RuntimeError('freshness probe requires IDLE')
        if not query.wait_for_service(timeout_sec=8): raise RuntimeError('carry snapshot absent')
        current = await_future(query.call_async(QueryCarry.Request()))
        if not current.success or current.state.engaged: raise RuntimeError('requires confirmed carry off')
        if not observe.wait_for_server(timeout_sec=8): raise RuntimeError('Observe absent')
        stale = CarryState()
        stale.engaged = True
        stale.object_id = 'target_box_a'
        # Deliberately ancient timestamp with valid topic/QoS.
        for _ in range(8):
            publisher.publish(stale)
            rclpy.spin_once(node, timeout_sec=.1)
        goal = await_future(observe.send_goal_async(Observe.Goal(refresh=True, max_age_s=0.)))
        if not goal.accepted: raise RuntimeError('Observe rejected')
        result = await_future(goal.get_result_async(), 30).result
        carry = result.world_state.carry
        ok = result.outcome == 0 and not carry.engaged and carry.object_id == ''
        print(json.dumps(dict(ok=ok, injected={'engaged': True, 'object_id': 'target_box_a', 'stamp': 0},
                              observed={'engaged': carry.engaged, 'object_id': carry.object_id},
                              query_revision=current.revision, observe_error=result.error_code)))
        return 0 if ok else 1
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
