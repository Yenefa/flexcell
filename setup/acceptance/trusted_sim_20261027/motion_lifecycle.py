#!/usr/bin/env python3
"""Two declared MTC motion fixtures: measured mid-motion cancel and deadline stop."""
import argparse
import hashlib
import json
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


def worker(out):
    import rclpy
    from rclpy.node import Node
    from rclpy.parameter import Parameter
    from rclpy.executors import MultiThreadedExecutor
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import JointState
    from flexcell_skills.mtc_motion import MtcMotionClient
    from flexcell_interfaces.action import MoveToPose
    rclpy.init()
    node = Node('mtc_motion_lifecycle', parameter_overrides=[Parameter('use_sim_time', value=True)])
    executor = MultiThreadedExecutor(num_threads=3)
    executor.add_node(node)
    observed = dict(enabled=False, started=None)
    def joints(msg):
        values = [abs(value) for name, value in zip(msg.name, msg.velocity) if name in ('joint1', 'joint2', 'joint3', 'joint4')]
        if observed['enabled'] and observed['started'] is None and values and max(values) > .005:
            observed['started'] = time.monotonic()
    subscription = node.create_subscription(JointState, '/joint_states', joints, qos_profile_sensor_data)
    thread = threading.Thread(target=executor.spin, daemon=True); thread.start()
    result = dict(schema_version=1, status='FAIL', cases=[], logical_robot_tasks=0,
                  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    client = MtcMotionClient(node)
    try:
        time.sleep(1)
        for case in ('cancel', 'timeout'):
            targets = [[.22, 0., z] for z in (.2375, .1775, .2775)]
            ok, detail = client.prepare('PICK', 'target_box_a', [.22, 0., .0175], targets,
                                        'demo_veryslow', 30000)
            assert ok, detail
            observed.update(enabled=True, started=None)
            cancel = (lambda: observed['started'] is not None and time.monotonic() - observed['started'] > .2)
            response, error = client.call(targets[0], profile='demo_veryslow',
                deadline_ms=30000 if case == 'cancel' else 400, request_id='fixture-' + case,
                cancel_check=cancel if case == 'cancel' else None)
            observed['enabled'] = False
            assert error is None and response is not None
            row = dict(case=case, outcome=int(response.outcome), error_code=int(response.error_code),
                       execution_started=response.execution_started, preempted=response.preempted,
                       stop_confirmed=response.stop_confirmed, evidence_id=response.evidence_id,
                       observed_motion=observed['started'] is not None, handoff=client.audit)
            result['cases'].append(row)
            expected = MoveToPose.Result.ERR_CANCELED if case == 'cancel' else MoveToPose.Result.ERR_EXECUTION_TIMEOUT
            assert response.error_code == expected, response.detail
            assert response.execution_started and response.preempted and response.stop_confirmed, response.detail
            assert observed['started'] is not None, 'no measured motion before stop'
            time.sleep(.3)
        result['status'] = 'PASS'
    except Exception as exc:
        result['error'] = repr(exc)
    finally:
        executor.shutdown(timeout_sec=5); thread.join(timeout=5)
        node.destroy_node(); rclpy.shutdown()
        (out / 'worker.json').write_text(json.dumps(result, indent=2) + '\n')
    return 0 if result['status'] == 'PASS' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    if args.worker:
        return worker(args.out)
    out = args.out / ('motion-lifecycle-' + uuid.uuid4().hex[:12]); out.mkdir(parents=True, exist_ok=False)
    params, world = profile(out, 'velocity_servo', False, 'mtc')
    result = dict(schema_version=1, status='FAIL', out=str(out), logical_robot_tasks=0)
    stack, log = None, (out / 'stack.log').open('x')
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
                got = json.loads(path.with_suffix('.stdout').read_text())
                if got['ok'] and got['hard_fail'] == [] and got['checks']['task_state'] == 'IDLE' and not got['checks']['carry_engaged']:
                    ready = True; break
        assert ready
        assert command([sys.executable, str(ROOT / 'setup/flexcell_admin.py'), 'reset'], out / 'reset_before') == 0
        assert command([sys.executable, __file__, '--worker', '--out', str(out)], out / 'worker', timeout=120) == 0
        assert json.loads((out / 'worker.json').read_text())['status'] == 'PASS'
        # Require the controller's terminal result as well as physical stop.
        motions = [json.loads(line) for line in (out / 'skills/move_to_pose.jsonl').read_text().splitlines()]
        stopped = [row for row in motions if row.get('motion_backend') == 'mtc']
        assert len(stopped) == 2 and all(row['execution_terminated'] is True and row['stop_confirmed'] is True for row in stopped)
        assert command([sys.executable, str(ROOT / 'setup/flexcell_admin.py'), 'health'], out / 'health_after') == 0
        result['status'] = 'PASS'
    except (Exception, KeyboardInterrupt) as exc:
        result['error'] = repr(exc)
    finally:
        if stack is not None: terminate_owned(stack)
        log.close()
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n'); print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
