#!/usr/bin/env python3
"""Initialize a recorded gripper target before the bounded data window."""
import json
import threading
import time
import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.parameter import Parameter
from flexcell_skills.common import GripperClient

def main():
    rclpy.init()
    node = Node('prepare_recording', parameter_overrides=[Parameter('use_sim_time', value=True)])
    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    try:
        client = GripperClient(node, '/gripper_controller/gripper_cmd', telemetry=True)
        time.sleep(1)
        result, error = client.command(.02)
        time.sleep(1)
        print(json.dumps(dict(ok=error is None, error=error, preparation='open gripper before task recording')))
        return 0 if error is None else 1
    finally:
        executor.shutdown(); thread.join(timeout=3); node.destroy_node(); rclpy.shutdown()

if __name__ == '__main__':
    raise SystemExit(main())
