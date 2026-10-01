#!/usr/bin/env python3
"""Real two-process ROS probes; no physical action goals or policy calls."""
import argparse
import faulthandler
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import rclpy
from rclpy.action import ActionClient, ActionServer
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.context import Context
from rclpy.executors import MultiThreadedExecutor, SingleThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from rosgraph_msgs.msg import Clock
from moveit_msgs.srv import GetPlanningScene
from flexcell_interfaces.action import RunPickPlace

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src/flexcell/flexcell_skills'))
from flexcell_skills.contracts.action_result import AcceptedGoalResult  # noqa: E402

LOCK = threading.Lock()
STREAM = None


def event(kind, **fields):
    with LOCK:
        STREAM.write(json.dumps(dict(event=kind, mono_ns=time.monotonic_ns(),
                                     wall_ns=time.time_ns(),
                                     thread=threading.get_ident(), **fields)) + '\n')
        STREAM.flush()


class Server(ActionServer):
    def _send_result_response(self, header, future):
        reply = future.result()
        key = reply.result.evidence_id
        event('server_send_result_enter', evidence_id=key, sequence=header.sequence_number)
        if self.fault == 'all' or (self.fault == 'first' and key not in self.dropped):
            self.dropped.add(key)
            event('injected_response_drop', evidence_id=key)
            return
        super()._send_result_response(header, future)
        event('server_send_result_return', evidence_id=key, sequence=header.sequence_number)

    async def _execute_get_result_request(self, data):
        header, req = data
        event('server_result_request', goal_uuid=bytes(req.goal_id.uuid).hex(),
              sequence=header.sequence_number)
        await super()._execute_get_result_request(data)


class Client(ActionClient):
    def _get_result_async(self, handle):
        event('client_result_send_enter', goal_uuid=bytes(handle.goal_id.uuid).hex())
        f = super()._get_result_async(handle)
        sequences = [n for n, item in self._pending_result_requests.items() if item is f]
        event('client_result_registered', sequences=sequences)
        return f

    def take_data(self):
        data = super().take_data()
        if 'result' in data:
            event('client_result_taken', sequence=data['result'][0], status=data['result'][1].status)
        return data

    async def execute(self, data):
        if 'result' in data:
            event('client_result_execute', sequence=data['result'][0],
                  pending=data['result'][0] in self._pending_result_requests)
        await super().execute(data)


def wait(future, seconds):
    end = time.monotonic() + seconds
    while not future.done() and time.monotonic() < end:
        time.sleep(.002)
    return future.done()


def role(args):
    global STREAM
    out = Path(args.out)
    STREAM = (out / (args.role + '.jsonl')).open('w')
    faulthandler.enable()
    faulthandler.dump_traceback_later(10, repeat=True)
    event('before_rclpy_init')
    rclpy.init()
    event('after_rclpy_init')
    if args.role == 'external':
        node = Node('dds_probe_external')
        event('external_participant_created')
        try:
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                rclpy.spin_once(node, timeout_sec=.05)
        finally:
            node.destroy_node()
            rclpy.shutdown()
        return 0
    node = Node('dds_probe_' + args.role,
                parameter_overrides=[Parameter('use_sim_time', value=bool(args.clock_hz))])
    event('after_node_creation')
    ex = (SingleThreadedExecutor() if args.threads == 1 else
          MultiThreadedExecutor(num_threads=args.threads))
    ex.add_node(node)
    if args.role == 'server':
        count = [0]

        def execute(handle):
            count[0] += 1
            event('server_execute', evidence_id=handle.request.object_name, executions=count[0])
            time.sleep(.02)
            handle.succeed()
            reply = RunPickPlace.Result()
            reply.evidence_id = handle.request.object_name
            reply.detail = 'probe only; no physical skill dispatched'
            event('server_completed', evidence_id=reply.evidence_id)
            return reply

        server = Server(node, RunPickPlace, '/dds_probe/action', execute,
                        callback_group=ReentrantCallbackGroup())
        server.fault, server.dropped = args.fault, set()
        node.create_service(GetPlanningScene, '/dds_probe/planning_scene', lambda q, r: r,
                            callback_group=ReentrantCallbackGroup())
        driver = None
        if args.clock_hz:
            driver = Node('dds_probe_clock')
            ex.add_node(driver)
            pub = driver.create_publisher(Clock, '/clock', 10)
            origin = time.monotonic()

            def tick():
                msg = Clock()
                ns = int((time.monotonic() - origin + 1) * 1e9)
                msg.clock.sec, msg.clock.nanosec = divmod(ns, 1_000_000_000)
                pub.publish(msg)

            driver.create_timer(1 / args.clock_hz, tick)
        event('server_ready', clock_hz=args.clock_hz)
        try:
            ex.spin()
        finally:
            ex.shutdown()
            server.destroy()
            node.destroy_node()
            if driver: driver.destroy_node()
            if rclpy.ok(): rclpy.shutdown()
        return 0
    cli = Client(node, RunPickPlace, '/dds_probe/action', callback_group=ReentrantCallbackGroup())
    event('after_action_client_creation')
    scene = node.create_client(GetPlanningScene, '/dds_probe/planning_scene', callback_group=ReentrantCallbackGroup())
    thread = threading.Thread(target=ex.spin, daemon=True)
    thread.start()
    event('before_wait_for_server')
    rows = []
    try:
        if not cli.wait_for_server(timeout_sec=8):
            event('failed_discovery_graph', nodes=node.get_node_names(),
                  services=node.get_service_names_and_types(),
                  status_publishers=len(node.get_publishers_info_by_topic('/dds_probe/action/_action/status')),
                  feedback_publishers=len(node.get_publishers_info_by_topic('/dds_probe/action/_action/feedback')))
            if args.recovery_control == 'wait':
                began = time.monotonic()
                while time.monotonic() - began < 4 and not cli.server_is_ready():
                    time.sleep(.05)
                event('time_matched_wait_control', action_ready=cli.server_is_ready(),
                      elapsed_s=time.monotonic()-began, scene_ready=scene.service_is_ready(),
                      nodes=node.get_node_names())
                raise RuntimeError('initial discovery failed; time control recorded')
            if args.recovery_control == 'same':
                clone = ActionClient(node, RunPickPlace, '/dds_probe/action',
                                     callback_group=ReentrantCallbackGroup())
                clone_seen = clone.wait_for_server(timeout_sec=4)
                event('same_participant_control', clone_ready=clone_seen,
                      old_ready=cli.server_is_ready(), scene_ready=scene.service_is_ready(),
                      nodes=node.get_node_names())
                clone.destroy()
                raise RuntimeError('initial discovery failed; same-participant control recorded')
            if args.recovery_control == 'external':
                with (out / 'external.log').open('w') as log:
                    external = subprocess.Popen(
                        [sys.executable, __file__, '--out', str(out), '--role', 'external'],
                        stdout=log, stderr=log)
                    try:
                        began = time.monotonic()
                        while time.monotonic() - began < 4 and not cli.server_is_ready():
                            time.sleep(.05)
                        old_ready = cli.server_is_ready()
                        scene_ready = scene.service_is_ready()
                        scene_reply = wait(scene.call_async(GetPlanningScene.Request()), 1) if scene_ready else False
                        action_reply = False
                        if old_ready:
                            goal = RunPickPlace.Goal()
                            goal.object_name = 'external-participant-proof'
                            sent = cli.send_goal_async(goal)
                            if wait(sent, 1) and sent.result().accepted:
                                reply = sent.result().get_result_async()
                                action_reply = wait(reply, 1) and reply.result().result.evidence_id == goal.object_name
                        event('external_participant_control', old_ready=old_ready,
                              scene_ready=scene_ready, scene_reply=scene_reply,
                              action_reply=action_reply, elapsed_s=time.monotonic()-began,
                              nodes=node.get_node_names())
                    finally:
                        external.terminate()
                        try: external.wait(3)
                        except subprocess.TimeoutExpired:
                            external.kill(); external.wait()
                raise RuntimeError('initial discovery failed; external-participant control recorded')
            context = Context()
            rclpy.init(context=context)
            fresh = Node('dds_probe_fresh', context=context)
            fresh_ex = SingleThreadedExecutor(context=context)
            fresh_ex.add_node(fresh)
            fresh_cli = ActionClient(fresh, RunPickPlace, '/dds_probe/action')
            fresh_thread = threading.Thread(target=fresh_ex.spin, daemon=True)
            fresh_thread.start()
            seen = fresh_cli.wait_for_server(timeout_sec=4)
            event('fresh_participant_discovery', available=seen, nodes=fresh.get_node_names(),
                  services=fresh.get_service_names_and_types())
            fresh_scene = fresh.create_client(GetPlanningScene, '/dds_probe/planning_scene')
            fresh_scene_ready = fresh_scene.wait_for_service(timeout_sec=1)
            fresh_scene_reply = (wait(fresh_scene.call_async(GetPlanningScene.Request()), 1)
                                 if fresh_scene_ready else False)
            fresh_action_reply = False
            if seen:
                probe_goal = RunPickPlace.Goal()
                probe_goal.object_name = 'fresh-participant-proof'
                proof_send = fresh_cli.send_goal_async(probe_goal)
                if wait(proof_send, 1) and proof_send.result().accepted:
                    fresh_action_reply = wait(proof_send.result().get_result_async(), 1)
            event('old_after_fresh_before_new_client', ready=cli.server_is_ready(),
                  nodes=node.get_node_names(), scene_ready=scene.service_is_ready())
            same_participant = ActionClient(node, RunPickPlace, '/dds_probe/action',
                                            callback_group=ReentrantCallbackGroup())
            same_ready = same_participant.wait_for_server(timeout_sec=.5)
            old_scene_ready = scene.wait_for_service(timeout_sec=.5)
            old_scene_reply = wait(scene.call_async(GetPlanningScene.Request()), 1) if old_scene_ready else False
            event('participant_recovery_comparison', fresh_scene_ready=fresh_scene_ready,
                  fresh_scene_reply=fresh_scene_reply, fresh_action_reply=fresh_action_reply,
                  old_action_ready=cli.server_is_ready(), same_participant_new_client_ready=same_ready,
                  old_scene_ready=old_scene_ready, old_scene_reply=old_scene_reply,
                  old_nodes=node.get_node_names())
            same_participant.destroy()
            fresh_scene.destroy()
            fresh_ex.shutdown(timeout_sec=2)
            fresh_thread.join(2)
            fresh_cli.destroy()
            fresh.destroy_node()
            context.shutdown()
            raise RuntimeError('isolated probe server not discovered')
        event('after_wait_for_server')
        for trial in range(args.trials):
            event('before_scene_wait', trial=trial)
            available = scene.wait_for_service(timeout_sec=.5)
            event('after_scene_wait', trial=trial, available=available)
            query_done = False
            if available:
                event('before_scene_request', trial=trial)
                query_done = wait(scene.call_async(GetPlanningScene.Request()), 1)
                event('after_scene_request', trial=trial, done=query_done)
            goal = RunPickPlace.Goal()
            goal.object_name = 'probe-' + str(trial)
            event('before_goal_send', trial=trial)
            send = cli.send_goal_async(goal)
            event('after_goal_send', trial=trial)
            if not wait(send, 2):
                rows.append(dict(trial=trial, error='goal_reply_timeout')); continue
            gh = send.result()
            if not gh.accepted:
                rows.append(dict(trial=trial, error='goal_rejected')); continue
            if args.result_timing == 'late': time.sleep(.06)
            result = AcceptedGoalResult(gh, retry_interval_s=.15)
            first = result._reads[0]
            got = wait(first, .12)
            end = time.monotonic() + .8
            while not result.done() and time.monotonic() < end: time.sleep(.002)
            done = result.done()
            evidence = result.result().result.evidence_id if done else None
            row = dict(trial=trial, scene_available=available, scene_reply=query_done,
                       first_reply=got, final_reply=done, read_requests=result.request_count,
                       evidence_matches=evidence == goal.object_name)
            rows.append(row)
            event('client_trial_end', **row)
        summary = dict(rmw=os.environ.get('RMW_IMPLEMENTATION'), threads=args.threads,
                       clock_hz=args.clock_hz, fault=args.fault, result_timing=args.result_timing,
                       trials=args.trials, rows=rows,
                       first_missed=sum(not r.get('first_reply', False) for r in rows),
                       final_missed=sum(not r.get('final_reply', False) for r in rows),
                       scene_unavailable=sum(not r.get('scene_available', False) for r in rows))
        (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        print(json.dumps({k: v for k, v in summary.items() if k != 'rows'}), flush=True)
    finally:
        ex.shutdown(timeout_sec=3)
        thread.join(3)
        cli.destroy()
        node.destroy_node()
        rclpy.shutdown()
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--role', choices=('server', 'client', 'external'))
    ap.add_argument('--out', required=True)
    ap.add_argument('--threads', type=int, default=6)
    ap.add_argument('--clock-hz', type=int, default=0)
    ap.add_argument('--fault', choices=('none', 'first', 'all'), default='none')
    ap.add_argument('--trials', type=int, default=40)
    ap.add_argument('--result-timing', choices=('early', 'late'), default='early')
    ap.add_argument('--start-case', type=int, default=0)
    ap.add_argument('--end-case', type=int, default=99)
    ap.add_argument('--base-domain', type=int, default=70)
    ap.add_argument('--stagger-s', type=float, default=0)
    ap.add_argument('--recovery-control', choices=('wait', 'same', 'fresh', 'external'), default='fresh')
    ap.add_argument('--udp-only', action='store_true')
    ap.add_argument('--max-message-size', type=int, default=0,
                    help='UDP transport size control; 0 keeps the middleware default')
    args = ap.parse_args()
    if args.role: return role(args)
    root = Path(args.out)
    root.mkdir(parents=True, exist_ok=False)
    if args.udp_only:
        size = f'<maxMessageSize>{args.max_message_size}</maxMessageSize>' if args.max_message_size else ''
        (root / 'udp_only.xml').write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<profiles xmlns="http://www.eprosima.com/XMLSchemas/fastRTPS_Profiles">
<transport_descriptors><transport_descriptor><transport_id>probe_udp</transport_id><type>UDPv4</type>{size}</transport_descriptor></transport_descriptors>
<participant profile_name="probe_udp" is_default_profile="true"><rtps><useBuiltinTransports>false</useBuiltinTransports>
<userTransports><transport_id>probe_udp</transport_id></userTransports></rtps></participant></profiles>''')
    cases = []
    for rmw in ('rmw_cyclonedds_cpp', 'rmw_fastrtps_cpp'):
        for threads in (1, 6):
            for hz in (0, 200):
                cases.append((rmw, threads, hz, 'none', 'early', args.trials))
        cases.append((rmw, 6, 200, 'none', 'late', args.trials))
        cases.extend((rmw, 6, 200, fault, 'early', 4 if fault == 'first' else 1)
                     for fault in ('first', 'all'))
    for index, (rmw, threads, hz, fault, timing, trials) in enumerate(cases):
        if index < args.start_case or index >= args.end_case: continue
        directory = root / f'{index:02d}_{rmw}_{threads}_{hz}_{fault}_{timing}'
        directory.mkdir()
        env = dict(os.environ, ROS_DOMAIN_ID=str(args.base_domain + index), RMW_IMPLEMENTATION=rmw)
        for var in ('FASTDDS_DEFAULT_PROFILES_FILE', 'FASTRTPS_DEFAULT_PROFILES_FILE'):
            env.pop(var, None)
        if args.udp_only and rmw == 'rmw_fastrtps_cpp':
            env['FASTDDS_DEFAULT_PROFILES_FILE'] = str((root / 'udp_only.xml').resolve())
            env['FASTRTPS_DEFAULT_PROFILES_FILE'] = env['FASTDDS_DEFAULT_PROFILES_FILE']
        (directory / 'config.json').write_text(json.dumps(dict(
            rmw=rmw, domain=args.base_domain+index, threads=threads, clock_hz=hz,
            fault=fault, result_timing=timing, trials=trials, udp_only=args.udp_only,
            max_message_size=args.max_message_size, stagger_s=args.stagger_s,
            recovery_control=args.recovery_control), indent=2)+'\n')
        cmd = [sys.executable, __file__, '--out', str(directory), '--threads', str(threads),
               '--clock-hz', str(hz), '--fault', fault, '--trials', str(trials), '--result-timing', timing]
        cmd += ['--recovery-control', args.recovery_control]
        with (directory / 'server.log').open('w') as log:
            server = subprocess.Popen(cmd + ['--role', 'server'], env=env, stdout=log, stderr=log)
            try:
                if args.stagger_s: time.sleep(args.stagger_s)
                with (directory / 'client.log').open('w') as client_log:
                    try:
                        client = subprocess.run(cmd + ['--role', 'client'], env=env,
                                                stdout=client_log, stderr=client_log, timeout=35)
                    except subprocess.TimeoutExpired:
                        (directory / 'process_timeout.json').write_text(json.dumps(dict(timeout_s=35,
                            role='client', domain=args.base_domain+index, rmw=rmw, udp_only=args.udp_only))+'\n')
                        print(directory.name, 'client_process_timeout', flush=True)
                        continue
                print(directory.name, 'client_rc=' + str(client.returncode), flush=True)
                if (directory / 'summary.json').exists():
                    summary = json.loads((directory / 'summary.json').read_text())
                    print({k: summary[k] for k in ('trials', 'first_missed', 'final_missed', 'scene_unavailable')}, flush=True)
            finally:
                server.terminate()
                try: server.wait(5)
                except subprocess.TimeoutExpired:
                    server.kill(); server.wait()
    return 0


if __name__ == '__main__':
    sys.exit(main())
