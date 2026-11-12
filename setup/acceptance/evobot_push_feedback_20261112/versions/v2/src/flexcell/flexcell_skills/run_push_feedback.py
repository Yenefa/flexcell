#!/usr/bin/env python3
"""Bounded shots with measured post-return state; no independent verdict online."""
import argparse
import json
import math
from pathlib import Path
import signal
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from rosidl_runtime_py.convert import message_to_ordereddict
from sensor_msgs.msg import JointState
from flexcell_interfaces.action import Observe, PushObject
from flexcell_skills.contracts import push_recover as policy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task', type=Path)
    parser.add_argument('out', type=Path)
    parser.add_argument('--attempts', type=int, default=3)
    args = parser.parse_args()
    if args.attempts < 1:
        parser.error('attempts must be positive')
    args.out.mkdir(exist_ok=False)
    spec = json.loads(args.task.read_text())
    target, goal = next(iter(spec['expected_goal']['push'].items()))
    zone = next(z for z in spec['zones'] if z['name'] == goal['zone'])
    declared = {o['name']: o['initial_pose'][:3] for o in spec['objects']}
    protected = spec['constraints']['must_not_move']
    canceled = [False]
    latest = [None, 0.]
    active = [None, None]
    records = []
    status = 'STATE_UNAVAILABLE'
    detail = None
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = Node('push_feedback_controller')
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: canceled.__setitem__(0, True))
    observe = ActionClient(node, Observe, '/observe')
    push = ActionClient(node, PushObject, '/push_object')
    with (args.out / 'events.jsonl').open('x') as stream:
        def event(kind, **fields):
            stream.write(json.dumps(dict(kind=kind, monotonic_ns=time.monotonic_ns(),
                                         utc_ns=time.time_ns(), **fields), allow_nan=False) + '\n')
            stream.flush()

        def joints(msg):
            latest[:] = [msg, time.monotonic()]
        subscription = node.create_subscription(JointState, '/joint_states', joints, 100)

        def wait(future, timeout):
            end = time.monotonic() + timeout
            while not future.done() and time.monotonic() < end:
                rclpy.spin_once(node, timeout_sec=.05)
            if not future.done():
                raise TimeoutError('action response timeout')
            return future.result()

        def action(client, request, kind, timeout):
            if canceled[0]:
                raise InterruptedError('canceled before dispatch')
            event(kind + '_REQUEST')
            handle = wait(client.send_goal_async(request), 15.)
            if handle is None or not handle.accepted:
                raise RuntimeError(kind + ' rejected')
            future = handle.get_result_async()
            active[:] = [handle, future]
            end = time.monotonic() + timeout
            cancel_sent = False
            while not future.done() and time.monotonic() < end:
                if canceled[0] and not cancel_sent:
                    handle.cancel_goal_async()
                    cancel_sent = True
                    event(kind + '_CANCEL_SENT')
                rclpy.spin_once(node, timeout_sec=.05)
            if not future.done():
                raise TimeoutError(kind + ' did not finish; no further action allowed')
            result = future.result()
            active[:] = [None, None]
            event(kind + '_RESULT', goal_uuid=bytes(handle.goal_id.uuid).hex(), status=result.status)
            return result

        def quiet():
            end = time.monotonic() + 10.
            since = None
            first_stamp = None
            while time.monotonic() < end:
                if canceled[0]:
                    raise InterruptedError('canceled before settling')
                rclpy.spin_once(node, timeout_sec=.05)
                msg, received = latest
                if msg is not None and policy.arm_quiet(list(msg.name), list(msg.velocity), time.monotonic()-received):
                    stamp = (msg.header.stamp.sec, msg.header.stamp.nanosec)
                    if since is None:
                        since, first_stamp = time.monotonic(), stamp
                    if time.monotonic()-since >= .2 and stamp != first_stamp:
                        event('ARM_QUIET', velocity=list(msg.velocity), name=list(msg.name))
                        return
                else:
                    since = None
            raise RuntimeError('arm did not provide fresh quiet joint states')

        def snapshot(index):
            quiet()
            request = Observe.Goal()
            request.refresh = True
            request.max_age_s = .5
            wrapped = action(observe, request, 'OBSERVE', 20.)
            result = wrapped.result
            if wrapped.status != 4 or result.outcome != 0 or result.error_code != 0:
                raise RuntimeError('fresh Observe failed')
            world = message_to_ordereddict(result.world_state)
            with (args.out / ('state_%02d.json' % index)).open('x') as f:
                json.dump(world, f, allow_nan=False)
            if (world['source'] != 'SIMULATION_GROUND_TRUTH' or world['header']['frame_id'] != 'world'
                    or not world['robot']['has_gripper_state']
                    or any(note.startswith('ee: lookup failed') for note in world['notes'])):
                raise RuntimeError('unusable world source, frame or robot state')
            if world['carry']['engaged']:
                raise RuntimeError('carry engaged; contact-only explanation unavailable')
            positions = {}
            for obj in world['objects']:
                if not obj['available'] or not 0 <= obj['pose_age_s'] <= .5:
                    raise RuntimeError('object unavailable/stale: ' + obj['name'])
                p = obj['pose']['position']
                positions[obj['name']] = [p['x'], p['y'], p['z']]
            if any(n not in positions for n in [target, *protected]):
                raise RuntimeError('required object missing')
            return positions

        try:
            if not observe.wait_for_server(timeout_sec=20.) or not push.wait_for_server(timeout_sec=20.):
                raise RuntimeError('required action server missing')
            current = snapshot(0)
            if any(math.dist(current[n], declared[n]) > .001 for n in declared):
                raise RuntimeError('observed initial world does not match task')
            for index in range(args.attempts + 1):
                protection = max((math.dist(current[n], declared[n]) for n in protected), default=0.)
                decision, payload = policy.measured_next_request(
                    declared[target], current[target], goal, zone,
                    args.attempts-index, protected_motion_m=protection)
                event('DECISION', decision=decision, **payload)
                if decision != 'push':
                    status, detail = decision.upper(), payload
                    break
                request = PushObject.Goal()
                request.request_id = 'feedback-%02d' % index
                request.object_name = target
                request.direction.x, request.direction.y = [float(v) for v in goal['direction']]
                request.direction.z = 0.
                request.distance_m = payload['distance_m']
                request.contact_height_m = .0200
                request.overdrive_m = .005
                request.max_increments = 1
                wrapped = action(push, request, 'PUSH', 120.)
                result = message_to_ordereddict(wrapped.result)
                records.append(result)
                nonfinite = []
                def portable(value, path='result'):
                    if isinstance(value, float) and not math.isfinite(value):
                        nonfinite.append(path)
                        return None
                    if isinstance(value, dict):
                        return {k: portable(v, path + '.' + k) for k, v in value.items()}
                    if isinstance(value, list):
                        return [portable(v, path + '[%d]' % i) for i, v in enumerate(value)]
                    return value
                saved = portable(result)
                with (args.out / ('push_%02d.json' % index)).open('x') as f:
                    json.dump(dict(goal_status=wrapped.status, result=saved,
                                   nonfinite_fields=nonfinite), f, allow_nan=False)
                if canceled[0] or wrapped.status == 5 or result['outcome'] == 2:
                    raise InterruptedError('push canceled')
                if result['carry_engaged_during']:
                    raise RuntimeError('carry engaged during push')
                current = snapshot(index + 1)
        except InterruptedError as exc:
            status, detail = 'CANCELED', str(exc)
        except Exception as exc:
            status, detail = 'STATE_UNAVAILABLE', '%s: %s' % (type(exc).__name__, exc)
        finally:
            handle, future = active
            if handle is not None and future is not None:
                handle.cancel_goal_async()
                try:
                    wait(future, 15.)
                except Exception as exc:
                    event('STOP_UNCONFIRMED', detail=str(exc))
            summary = dict(kind='POST_RETURN_FEEDBACK', status=status, detail=detail,
                           attempts=len(records), independent_acceptance_claim=False)
            with (args.out / 'feedback.json').open('x') as f:
                json.dump(summary, f, indent=2, allow_nan=False)
            event('FINISHED', summary=summary)
            node.destroy_node()
            rclpy.shutdown()
    print(json.dumps(summary))
    return 0 if status in ('GOAL_GEOMETRY_REACHED', 'EXHAUSTED', 'BLOCKED') else 2


if __name__ == '__main__':
    raise SystemExit(main())
