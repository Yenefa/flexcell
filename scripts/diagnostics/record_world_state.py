#!/usr/bin/env python3
"""Record real WorldState snapshots without changing the observe publisher.

The publisher at 30fa2066 is RELIABLE/VOLATILE and publishes on /observe,
not on a timer. --observe-period requests snapshots, with one request in flight.
This is diagnostic acquisition, not a task evaluator or proof of a push.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import time


def emit(stream, value):
    stream.write(json.dumps(value, allow_nan=False) + '\n')
    stream.flush()


def issues(world, objects, max_object_age=0.5):
    """Keep unavailable/default robot poses out of usable diagnostic samples."""
    problems = []
    robot = world['robot']
    if not world['header']['frame_id'] or not robot['ee_frame']:
        problems.append('missing coordinate frame')
    if not robot['has_gripper_state'] or not robot['gripper_joint_name']:
        problems.append('gripper state unavailable')
    if any(note.startswith('ee: lookup failed') for note in world['notes']):
        problems.append('end-effector TF lookup failed; pose is a default')
    if world['source'] != 'SIMULATION_GROUND_TRUTH':
        problems.append('unexpected state source: ' + world['source'])
    observed = {obj['name']: obj for obj in world['objects']}
    for name in objects:
        if name not in observed or not observed[name]['available']:
            problems.append('object unavailable: ' + name)
        elif not 0 <= observed[name]['pose_age_s'] <= max_object_age:
            problems.append('object sample stale or age unavailable: ' + name)
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='new output directory')
    parser.add_argument('--duration', type=float, default=90.)
    parser.add_argument('--topic', default='/flexcell/world_state')
    parser.add_argument('--observe-action', default='/observe')
    parser.add_argument('--observe-period', type=float, default=0.,
                        help='0 = passive; >0 = seconds between completed requests')
    parser.add_argument('--request-timeout', type=float, default=15.)
    parser.add_argument('--max-object-age', type=float, default=0.5,
                        help='diagnostic usability bound, not a task acceptance rule')
    parser.add_argument('--push-feedback', default='/push_object/_action/feedback')
    parser.add_argument('--stop-file', type=Path,
                        help='finish normally when this file appears')
    parser.add_argument('--object', action='append', default=[])
    args = parser.parse_args(argv)
    if (not all(math.isfinite(v) for v in
                (args.duration, args.observe_period, args.request_timeout, args.max_object_age))
            or args.duration <= 0 or args.observe_period < 0 or args.request_timeout <= 0
            or args.max_object_age <= 0):
        parser.error('duration/timeout must be positive; observe period must be nonnegative')
    args.out.mkdir(parents=True, exist_ok=False)  # Never overwrite evidence.
    objects = args.object or ['target_box_a', 'target_box_b']
    summary = dict(kind='WORLDSTATE_DIAGNOSTIC', status='STARTING',
                   robot_capability_claim=False, objects=objects,
                   script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   source_revision=os.environ.get('FLEXCELL_SOURCE_REV', 'UNKNOWN'),
                   context={key: os.environ.get(key) for key in
                            ('ROS_DOMAIN_ID', 'RMW_IMPLEMENTATION', 'GZ_PARTITION')},
                   topic_samples=0, result_samples=0, usable_topic_samples=0,
                   usable_result_samples=0, observe_requests=0, observe_failures=0,
                   errors=[], acquisition_started_utc_ns=time.time_ns())
    node = None
    rclpy = None
    pending = None
    handle = None
    with (args.out / 'events.jsonl').open('x') as events, \
            (args.out / 'world_state.jsonl').open('x') as samples:
        def event(kind, **fields):
            emit(events, dict(kind=kind, rx_mono_ns=time.monotonic_ns(),
                              rx_utc_ns=time.time_ns(), **fields))

        def record(msg, channel, request=None):
            world = message_to_ordereddict(msg)
            problems = issues(world, objects, args.max_object_age)
            record = dict(channel=channel, request=request, rx_mono_ns=time.monotonic_ns(),
                          rx_utc_ns=time.time_ns(), issues=problems, world_state=world)
            # No rounding, invented zeros, silent NaN replacement or timestamp deduplication.
            emit(samples, record)
            summary[channel + '_samples'] += 1
            if not problems:
                summary['usable_' + channel + '_samples'] += 1

        try:
            import rclpy
            from rclpy.action import ActionClient
            from rclpy.node import Node
            from rclpy.qos import (DurabilityPolicy, QoSProfile, ReliabilityPolicy,
                                   qos_check_compatible)
            from rosidl_runtime_py.convert import message_to_ordereddict
            from flexcell_interfaces.action import Observe, PushObject
            from flexcell_interfaces.msg import WorldState

            rclpy.init()
            node = Node('worldstate_diagnostic')
            qos = QoSProfile(depth=100, reliability=ReliabilityPolicy.RELIABLE,
                             durability=DurabilityPolicy.VOLATILE)
            subscription = node.create_subscription(
                WorldState, args.topic, lambda msg: record(msg, 'topic'), qos)
            feedback_subscription = node.create_subscription(
                PushObject.Impl.FeedbackMessage, args.push_feedback,
                lambda msg: event('PUSH_FEEDBACK', goal_uuid=bytes(msg.goal_id.uuid).hex(),
                                  feedback=message_to_ordereddict(msg.feedback)), qos)
            client = ActionClient(node, Observe, args.observe_action)
            event('READY', topic=args.topic, observe_action=args.observe_action,
                  requested_qos=dict(reliability='RELIABLE', durability='VOLATILE', depth=100),
                  observe_period_s=args.observe_period)
            deadline = time.monotonic() + args.duration
            next_request = next_graph = 0.
            old_graph = None
            request_id = None
            stage = None
            while (rclpy.ok() and time.monotonic() < deadline
                   and not (args.stop_file and args.stop_file.exists())):
                rclpy.spin_once(node, timeout_sec=0.05)
                now = time.monotonic()
                if now >= next_graph:
                    graph = []
                    for info in node.get_publishers_info_by_topic(args.topic):
                        compatibility, reason = qos_check_compatible(info.qos_profile, qos)
                        graph.append(dict(node_name=info.node_name,
                                          node_namespace=info.node_namespace,
                                          topic_type=info.topic_type,
                                          qos_reliability=info.qos_profile.reliability.name,
                                          qos_durability=info.qos_profile.durability.name,
                                          qos_compatibility=compatibility.name, reason=reason))
                    if graph != old_graph:
                        event('PUBLISHERS', endpoints=graph)
                        old_graph = graph
                    next_graph = now + 1.
                if pending is not None:
                    if pending.done():
                        response = pending.result()  # Exceptions are recorded below.
                        if stage == 'accept':
                            handle = response
                            if handle is None or not handle.accepted:
                                event('OBSERVE_REJECTED', request=request_id)
                                summary['observe_failures'] += 1
                                pending = None
                            else:
                                pending = handle.get_result_async()
                                stage = 'result'
                        else:
                            event('OBSERVE_RESULT', request=request_id, status=response.status,
                                  outcome=response.result.outcome,
                                  error_code=response.result.error_code, detail=response.result.detail)
                            if response.status == 4 and response.result.outcome == 0:
                                record(response.result.world_state, 'result', request_id)
                            else:
                                summary['observe_failures'] += 1
                            pending = None
                            handle = None
                        if pending is None:
                            next_request = now + args.observe_period
                    elif now >= request_deadline:
                        raise TimeoutError('observe request %s timed out in %s' % (request_id, stage))
                elif args.observe_period > 0 and now >= next_request and client.server_is_ready():
                    goal = Observe.Goal()
                    goal.refresh = True
                    summary['observe_requests'] += 1
                    request_id = summary['observe_requests']
                    event('OBSERVE_REQUEST', request=request_id)
                    pending = client.send_goal_async(goal)
                    stage = 'accept'
                    request_deadline = now + args.request_timeout
            summary['status'] = ('CAPTURED' if summary['usable_topic_samples'] >= 2
                                 else 'INSUFFICIENT_USABLE_TOPIC_SAMPLES')
        except KeyboardInterrupt:
            summary['status'] = 'INTERRUPTED'
        except Exception as exc:
            summary['status'] = 'ERROR'
            summary['errors'].append('%s: %s' % (type(exc).__name__, exc))
            event('ERROR', detail=summary['errors'][-1])
        finally:
            if pending is not None:
                event('REQUEST_PENDING_AT_STOP')
                if handle is not None and handle.accepted and rclpy is not None and rclpy.ok():
                    canceled = handle.cancel_goal_async()
                    rclpy.spin_until_future_complete(node, canceled, timeout_sec=1.)
                    event('CANCEL_RESPONSE', received=canceled.done())
            if node is not None:
                node.destroy_node()
            if rclpy is not None and rclpy.ok():
                rclpy.shutdown()
            summary['acquisition_finished_utc_ns'] = time.time_ns()
            with (args.out / 'summary.json').open('x') as stream:
                json.dump(summary, stream, indent=2, allow_nan=False)
    print(json.dumps(summary, allow_nan=False))
    return 0 if summary['status'] == 'CAPTURED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
