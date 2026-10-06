#!/usr/bin/env python3
"""Bounded read-only clock/joint graph probe using monotonic observation time."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import JointState


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    assert not args.out.exists()
    rclpy.init()
    node = Node('flexcell_clock_probe')
    counts, last, gids = defaultdict(int), {}, defaultdict(set)
    samples, regressions, wall_steps = [], [], []
    started = time.monotonic()
    last_wall_pair = [time.time_ns(), time.monotonic_ns()]

    def receive(topic, stamp, info):
        mono, wall = time.monotonic_ns(), time.time_ns()
        value = stamp.sec * 1_000_000_000 + stamp.nanosec
        row = dict(topic=topic, stamp_ns=value, mono_ns=mono, wall_ns=wall,
                   gid=bytes(info['publisher_gid']).hex())
        counts[topic] += 1
        gids[topic].add(row['gid'])
        if topic in last and value < last[topic]['stamp_ns']:
            regressions.append(dict(row, previous=last[topic]))
        if counts[topic] == 1 or mono-last.get(topic, {}).get('sampled_ns', 0) > 100_000_000:
            samples.append(row)
            sampled = mono
        else:
            sampled = last[topic]['sampled_ns']
        last[topic] = dict(row, sampled_ns=sampled)
        difference = (wall-last_wall_pair[0])-(mono-last_wall_pair[1])
        if abs(difference) > 10_000_000:
            wall_steps.append(dict(mono_ns=mono, wall_ns=wall, delta_wall_minus_monotonic_ns=difference))
        last_wall_pair[:] = [wall, mono]

    node.create_subscription(Clock, '/clock', lambda msg, info: receive('/clock', msg.clock, info), qos_profile_sensor_data)
    node.create_subscription(JointState, '/joint_states', lambda msg, info: receive('/joint_states', msg.header.stamp, info), qos_profile_sensor_data)
    try:
        while time.monotonic()-started < 25:
            rclpy.spin_once(node, timeout_sec=.1)
        graph = {topic:[dict(node=i.node_name, namespace=i.node_namespace,
                             gid=bytes(i.endpoint_gid).hex())
                       for i in node.get_publishers_info_by_topic(topic)] for topic in ('/clock','/joint_states')}
        args.out.write_text(json.dumps(dict(duration_s=time.monotonic()-started,
            physical_dispatches=0, counts=dict(counts), graph=graph,
            received_gids={key:sorted(value) for key,value in gids.items()},
            stamp_regressions=regressions, wall_steps=wall_steps, samples=samples),indent=2)+'\n')
        print(json.dumps(dict(counts=dict(counts),graph=graph,stamp_regressions=len(regressions),wall_steps=len(wall_steps)),indent=2))
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
