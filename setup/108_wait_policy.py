#!/usr/bin/env python3
"""Fleet startup readiness: actions present and deployed policy matches."""
import argparse
import time
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rcl_interfaces.srv import GetParameters
from std_srvs.srv import Trigger
from flexcell_interfaces.action import RunDemo, RunPickPlace


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('policy', choices=('fsm', 'jev', 'llm', 'hybrid'))
    args = ap.parse_args()
    rclpy.init()
    node = Node('flexcell_fleet_startup')
    try:
        for cls, name in ((RunPickPlace, '/run_pick_place'), (RunDemo, '/run_demo')):
            client = ActionClient(node, cls, name)
            if not client.wait_for_server(timeout_sec=25):
                raise RuntimeError(name + ' did not become ready')
        client = node.create_client(GetParameters, '/task_fsm_server/get_parameters')
        if not client.wait_for_service(timeout_sec=5):
            raise RuntimeError('policy parameter service unavailable')
        request = GetParameters.Request(names=['decision_policy'])
        future = client.call_async(request)
        rclpy.spin_until_future_complete(node, future, timeout_sec=8)
        if not future.done() or future.result().values[0].string_value != args.policy:
            raise RuntimeError('deployed policy does not match request')
        ready = node.create_client(Trigger, '/flexcell/place_ready')
        if not ready.wait_for_service(timeout_sec=5):
            raise RuntimeError('PLACE dependency readiness service unavailable')
        deadline = time.monotonic() + 12.0
        release_ready = False
        while time.monotonic() < deadline:
            pending = ready.call_async(Trigger.Request())
            rclpy.spin_until_future_complete(node, pending, timeout_sec=3)
            if pending.done() and pending.result().success:
                release_ready = True
                break
            ready.remove_pending_request(pending)
        if not release_ready:
            raise RuntimeError('PLACE cannot discover carry release; fleet is not ready')
        print('READY: task actions and policy=' + args.policy, flush=True)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
