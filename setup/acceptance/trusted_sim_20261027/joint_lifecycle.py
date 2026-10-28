#!/usr/bin/env python3
"""Three declared native attachment cycles; no task policy, models or hardware."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
from sim_profile import profile
from sim_smoke import command, terminate_owned


def worker(out, world):
    # Native transport is isolated from the ROS launch/admin interpreters.
    import gz.transport13
    from gz.msgs10 import pose_pb2, empty_pb2, stringmsg_pb2, boolean_pb2
    node = gz.transport13.Node()
    prefix = '/world/%s/flexcell/carry/' % world
    events = (out / 'native-events.jsonl').open('x')
    stop, heartbeat = threading.Event(), None
    errors = []

    def rpc(operation, message, response_type):
        started = time.monotonic_ns()
        transport, response = node.request(prefix + operation, message, type(message), response_type, 1000)
        if not transport:
            raise RuntimeError(operation + ' transport reply unknown; stop fixture')
        data = json.loads(response.data) if operation == 'status' else bool(response.data)
        events.write(json.dumps(dict(operation=operation, request_type=type(message).__name__,
            request_mono_ns=started, reply_mono_ns=time.monotonic_ns(), reply=data)) + '\n')
        events.flush()
        return data

    def status():
        return rpc('status', empty_pb2.Empty(), stringmsg_pb2.StringMsg)

    def pose(name, token):
        result = pose_pb2.Pose()
        result.name = name
        result.position.x, result.position.y, result.position.z = (
            (.22, 0., .0175) if name == 'target_box_a' else (.20, -.18, .0175))
        result.orientation.w = 1.
        header = result.header.data.add(); header.key = 'carry_session'; header.value.append(token)
        return result

    def engage(name, token):
        return rpc('engage', pose(name, token), boolean_pb2.Boolean)

    def release(token):
        return rpc('release', stringmsg_pb2.StringMsg(data=token), boolean_pb2.Boolean)

    def start_heartbeat(name, token):
        nonlocal heartbeat
        stop.clear()
        def loop():
            while not stop.wait(.08):
                try:
                    confirmed = rpc('pin', pose(name, token), boolean_pb2.Boolean)
                    if not confirmed and not stop.is_set(): errors.append('active heartbeat rejected')
                except Exception as exc:
                    errors.append(str(exc)); return
        heartbeat = threading.Thread(target=loop)
        heartbeat.start()

    def stop_heartbeat():
        stop.set()
        if heartbeat is not None:
            heartbeat.join(timeout=2)
            if heartbeat.is_alive(): raise RuntimeError('heartbeat terminal state unknown')

    result = dict(schema_version=1, status='FAIL', fixture='three native attachment cycles',
                  logical_robot_tasks=0, source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    try:
        initial = status()
        assert initial['backend'] == 'detachable_joint_v1' and initial['ready'] and not initial['engaged']
        old, current, other = (uuid.uuid4().hex for _ in range(3))
        assert engage('target_box_a', old)
        start_heartbeat('target_box_a', old)
        assert not engage('target_box_b', other), 'second object stole ownership'
        assert not rpc('pin', pose('target_box_b', old), boolean_pb2.Boolean), 'cross-object pin accepted'
        assert status()['session'] == old
        time.sleep(.3)
        stop_heartbeat()
        assert release(old)
        assert not status()['engaged']
        time.sleep(.2)
        assert engage('target_box_a', current), 'reattach after release failed'
        start_heartbeat('target_box_a', current)
        assert not release(old), 'retired release dropped the new session'
        assert status()['session'] == current and status()['engaged']
        time.sleep(.3)
        stop_heartbeat()
        last_heartbeat = time.monotonic()
        expired = None
        while time.monotonic() - last_heartbeat < 2.:
            got = status()
            if not got['engaged'] and not got['session']:
                expired = time.monotonic() - last_heartbeat
                break
            time.sleep(.03)
        assert expired is not None, 'lease expiry did not remove attachment'
        assert not engage('target_box_a', current), 'retired session re-engaged'
        assert engage('target_box_b', other), 'second-object lifecycle failed'
        start_heartbeat('target_box_b', other)
        assert status()['object'] == 'target_box_b'
        time.sleep(.3)
        stop_heartbeat()
        assert release(other)
        final = status()
        assert final['ready'] and not final['engaged'] and not final['session']
        assert not errors, errors
        result.update(status='PASS', lease_expiry_observed_s=expired, final=final)
    except Exception as exc:
        result['error'] = repr(exc)
    finally:
        stop_heartbeat()
        result['heartbeat_errors'] = errors
        events.close()
        (out / 'worker.json').write_text(json.dumps(result, indent=2) + '\n')
    return 0 if result['status'] == 'PASS' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--world', default='empty')
    args = parser.parse_args()
    if args.worker:
        return worker(args.out, args.world)
    out = args.out / ('joint-lifecycle-' + uuid.uuid4().hex[:12])
    out.mkdir(parents=True, exist_ok=False)
    params, world = profile(out, 'detachable_joint', False, 'legacy')
    result = dict(schema_version=1, status='FAIL', out=str(out), logical_robot_tasks=0,
                  kind='NATIVE_LIFECYCLE_ONLY; not contact grasp or task success rate')
    stack = None
    log = (out / 'stack.log').open('x')
    try:
        assert command([sys.executable, str(ROOT / 'infra/runtime_identity.py')], out / 'identity') == 0
        stack = subprocess.Popen(['ros2', 'launch', 'flexcell_skills', 'trusted_sim.launch.py',
            'world:=' + str(world), 'params_file:=' + str(params)], stdout=log,
            stderr=subprocess.STDOUT, start_new_session=True)
        ready = False
        for attempt in range(6):
            time.sleep(3)
            path = out / ('health_before_%d' % attempt)
            if command([sys.executable, str(ROOT / 'setup/flexcell_admin.py'), 'health'], path, timeout=40) == 0:
                doc = json.loads(path.with_suffix('.stdout').read_text())
                if doc['ok'] and doc['hard_fail'] == [] and doc['checks']['task_state'] == 'IDLE' and not doc['checks']['carry_engaged']:
                    ready = True; break
        if not ready:
            import xml.etree.ElementTree as ET
            name = ET.parse(world).getroot().find('world').get('name')
            command(['gz', 'sim', '--versions'], out / 'gz_version', timeout=10)
            command(['gz', 'service', '-s', '/world/%s/flexcell/carry/status' % name,
                     '--reqtype', 'gz.msgs.Empty', '--reptype', 'gz.msgs.StringMsg',
                     '--timeout', '1000', '--req', ''], out / 'native_startup_status', timeout=10)
            (out / 'plugin_environment.json').write_text(json.dumps(dict(
                plugin_path=os.environ.get('GZ_SIM_SYSTEM_PLUGIN_PATH'),
                install=os.environ.get('FLEXCELL_INSTALL')), indent=2) + '\n')
            raise RuntimeError('startup health failed; no backend cycle dispatched; native diagnostics saved')
        assert command([sys.executable, str(ROOT / 'setup/flexcell_admin.py'), 'reset'], out / 'reset_before') == 0
        import xml.etree.ElementTree as ET
        name = ET.parse(world).getroot().find('world').get('name')
        env = dict(os.environ, PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION='python')
        with (out / 'worker.log').open('x') as worker_log:
            proc = subprocess.run([sys.executable, __file__, '--worker', '--world', name, '--out', str(out)],
                stdout=worker_log, stderr=subprocess.STDOUT, env=env, timeout=90)
        result['worker_exit'] = proc.returncode
        assert proc.returncode == 0, 'native fixture failed or worker exit rejected'
        assert json.loads((out / 'worker.json').read_text())['status'] == 'PASS'
        assert command([sys.executable, str(ROOT / 'setup/flexcell_admin.py'), 'health'], out / 'health_after') == 0
        result['status'] = 'PASS'
    except (Exception, KeyboardInterrupt) as exc:
        result['error'] = repr(exc)
    finally:
        if stack is not None:
            terminate_owned(stack)
        log.close()
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
