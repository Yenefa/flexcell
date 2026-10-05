#!/usr/bin/env python3
"""Read-only comparison of external carry discovery and PLACE's readiness RPC."""
import argparse
import json
import os
from pathlib import Path
import time

import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    assert not args.out.exists(), 'Preserve previous observations'
    args.out.parent.mkdir(parents=True, exist_ok=True)
    rclpy.init()
    node = Node('flexcell_place_dependency_probe')
    ready = node.create_client(Trigger, '/flexcell/place_ready')
    # Discovery only: never call carry_release or command any physical skill.
    release = node.create_client(Trigger, '/flexcell/carry_release')
    records = []
    try:
        discovered = ready.wait_for_service(timeout_sec=5)
        for index in range(5):
            start = time.monotonic_ns()
            row = dict(index=index, mono_ns=start, wall_ts=time.time(),
                       external_release_ready=release.service_is_ready(),
                       place_readiness_endpoint_ready=ready.service_is_ready(),
                       graph_nodes=node.get_node_names_and_namespaces())
            if discovered:
                future = ready.call_async(Trigger.Request())
                rclpy.spin_until_future_complete(node, future, timeout_sec=5)
                row['rpc_completed'] = future.done()
                if future.done():
                    try:
                        response = future.result()
                        row.update(place_release_ready=response.success, detail=response.message)
                    except Exception as exc:
                        row['error'] = type(exc).__name__
            else:
                row['rpc_completed'] = False
            row['elapsed_ms'] = (time.monotonic_ns() - start) / 1e6
            records.append(row)
            rclpy.spin_once(node, timeout_sec=.5)
        result = dict(schema_version=1, ros_domain_id=os.environ.get('ROS_DOMAIN_ID'),
                      rmw_implementation=os.environ.get('RMW_IMPLEMENTATION'), samples=records,
                      carry_release_calls=0, physical_dispatches=0,
                      scope='Post-batch present discovery only; cannot reconstruct historical failure or prove root cause')
        args.out.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
