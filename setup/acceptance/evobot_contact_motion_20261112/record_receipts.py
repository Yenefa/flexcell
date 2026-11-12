"""Read-only ROS receipt consumer. Never dispatches robot commands."""
import argparse
import json
from pathlib import Path
import time

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSProfile,DurabilityPolicy
from std_msgs.msg import String
from flexcell_interfaces.msg import WorldState
from flexcell_skills.contact_receipt import ready_for_next


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out',type=Path);parser.add_argument('stop',type=Path)
    args=parser.parse_args();rclpy.init()
    node=Node('contact_receipt_consumer',parameter_overrides=[Parameter('use_sim_time',value=True)])
    revision=[None];pending=[];seen=0
    with args.out.open('x') as stream:
        def write(kind,**fields):
            stream.write(json.dumps(dict(kind=kind,monotonic_ns=time.monotonic_ns(),
                sim_ns=node.get_clock().now().nanoseconds,**fields),allow_nan=False)+'\n');stream.flush()
        def world(msg):revision[0]=msg.revision
        def receive(msg):
            nonlocal seen
            value=json.loads(msg.data);seen+=1
            now=time.monotonic_ns();sim=node.get_clock().now().nanoseconds
            ready=ready_for_next(value,sim,revision[0],now)
            write('RECEIPT_RECEIVED',receipt=value,observed_world_revision=revision[0],ready_checked=ready)
            pending.append((now,value))
        subscriptions=[node.create_subscription(WorldState,'/flexcell/world_state',world,10),
            node.create_subscription(String,'/flexcell/contact_push_receipt',receive,
                                     QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))]
        end=time.monotonic()+560.
        while time.monotonic()<end:
            rclpy.spin_once(node,timeout_sec=.02)
            now=time.monotonic_ns()
            for received,value in list(pending):
                if now-received>=300_000_000:
                    ready=ready_for_next(value,node.get_clock().now().nanoseconds,revision[0],now)
                    write('RECEIPT_RECHECK_AFTER_300MS',request_id=value['request_id'],ready_checked=ready)
                    pending.remove((received,value))
            if args.stop.exists() and not pending:break
        write('CONSUMER_FINISHED',received=seen,actuator_goals=0)
    node.destroy_node();rclpy.shutdown()


if __name__=='__main__':main()
