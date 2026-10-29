#!/usr/bin/env python3
"""One owned, bounded simulation task; no model, retry campaign or hardware."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid
import yaml
import math

from sim_profile import profile, ROOT
from camera_preflight import preflight_rendering


def json_result(value):
    """Represent unavailable numeric metadata without changing raw action output."""
    missing = {}
    def visit(item, path):
        if isinstance(item, float) and not math.isfinite(item):
            missing[path] = str(item)
            return None
        if isinstance(item, dict):
            return {key: visit(val, path + '.' + key if path else key) for key, val in item.items()}
        if isinstance(item, list):
            return [visit(val, '%s[%d]' % (path, i)) for i, val in enumerate(item)]
        return item
    result = visit(value, '')
    result['unavailable_numeric_fields'] = missing
    return result


def command(argv, out, timeout=120):
    with out.with_suffix('.stdout').open('x') as stdout, out.with_suffix('.stderr').open('x') as stderr:
        proc = subprocess.run(argv, stdout=stdout, stderr=stderr, timeout=timeout)
    return proc.returncode


def terminate_owned(proc):
    if proc.poll() is None:
        os.killpg(proc.pid, signal.SIGINT)
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=5)


def remember_owned(out, proc):
    stat = Path('/proc/%d/stat' % proc.pid).read_text().rsplit(')', 1)[1].split()
    with (out / 'owned_processes.jsonl').open('a') as stream:
        stream.write(json.dumps(dict(pid=proc.pid, start_ticks=stat[19])) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--backend', choices=['velocity_servo', 'detachable_joint', 'teleport'], default='velocity_servo')
    parser.add_argument('--skill-backend', choices=['legacy', 'mtc'], default='legacy')
    parser.add_argument('--object', choices=['target_box_a', 'target_box_b'], default='target_box_a')
    parser.add_argument('--camera', action='store_true')
    parser.add_argument('--joint-hold-sim-s', type=float, default=0.)
    parser.add_argument('--physics-step-s', type=float)
    parser.add_argument('--min-preflight-rtf', type=float, default=0.)
    parser.add_argument('--expected-world-sha256')
    parser.add_argument('--expected-config-sha256')
    parser.add_argument('--expected-fingerprint')
    parser.add_argument('--expected-egl-vendor-sha256')
    parser.add_argument('--contact-trace', action='store_true')
    parser.add_argument('--release-clearance-m', type=float)
    parser.add_argument('--qualification-no-recovery', action='store_true')
    parser.add_argument('--case', choices=['normal', 'dual_object', 'recovery_once', 'budget_exhaustion',
                                           'unreachable_place'], default='normal')
    args = parser.parse_args()
    out = args.out / ('run-' + uuid.uuid4().hex[:12])
    out.mkdir(parents=True, exist_ok=False)
    options = {}
    if args.contact_trace: options['contact_trace'] = True
    if args.release_clearance_m is not None: options['release_clearance_m'] = args.release_clearance_m
    if args.qualification_no_recovery: options['qualification_no_recovery'] = True
    params, world = profile(out, args.backend, args.camera, args.skill_backend,
                            args.joint_hold_sim_s, args.physics_step_s, **options)
    if args.physics_step_s is not None:
        os.environ['FLEXCELL_PHYSICS_STEP_LOG'] = str(out / 'physics_steps.jsonl')
    if args.contact_trace:
        os.environ['FLEXCELL_CONTACT_STEP_LOG'] = str(out / 'contact_steps.jsonl')
    else:
        os.environ.pop('FLEXCELL_CONTACT_STEP_LOG', None)
    os.environ['FLEXCELL_EPISODE_DIR'] = str(out / 'episodes')
    result = dict(schema_version=1, status='HARNESS_ERROR', backend=args.backend,
                  skill_backend=args.skill_backend, physical_tasks_dispatched=0,
                  qualification='FUNCTIONAL_SMOKE_ONLY', case=args.case, object=args.object, out=str(out))
    stack = None
    recorder = None
    log = (out / 'stack.log').open('x')
    def interrupted(signum, _frame):
        raise RuntimeError('harness interrupted by signal %d' % signum)
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        rc = command([sys.executable, str(ROOT / 'infra/runtime_identity.py')], out / 'identity')
        if rc:
            raise RuntimeError('installed/source identity mismatch')
        identity = json.loads((out / 'identity.stdout').read_text())
        semantic_config = yaml.safe_load(params.read_text())
        for node in semantic_config.values():
            for key, value in list(node.get('ros__parameters', {}).items()):
                if key in ('log_dir', 'episode_dir'):
                    node['ros__parameters'][key] = '$RUN/' + key
        config_digest = __import__('hashlib').sha256(json.dumps(semantic_config, sort_keys=True).encode()).hexdigest()
        world_digest = __import__('hashlib').sha256(world.read_bytes()).hexdigest()
        result['world_sha256'] = world_digest
        result['semantic_config_sha256'] = config_digest
        if args.expected_world_sha256 and world_digest != args.expected_world_sha256:
            raise RuntimeError('world differs from declaration; no robot task dispatched')
        if args.expected_config_sha256 and config_digest != args.expected_config_sha256:
            raise RuntimeError('configuration differs from declaration; no robot task dispatched')
        provenance = dict(identity=identity, config=semantic_config)
        if args.camera:
            result['camera_preflight'] = preflight_rendering(out)
            provenance['camera_preflight'] = result['camera_preflight']
        if args.expected_egl_vendor_sha256 and (
                not args.camera or result['camera_preflight']['vendor_files'].get(
                    '/usr/share/glvnd/egl_vendor.d/50_mesa.json') != args.expected_egl_vendor_sha256):
            raise RuntimeError('camera EGL vendor differs from declaration; no robot task dispatched')
        fingerprint = __import__('hashlib').sha256(json.dumps(
            provenance, sort_keys=True).encode() + world.read_bytes()).hexdigest()
        result['runtime_fingerprint'] = fingerprint
        if args.expected_fingerprint and fingerprint != args.expected_fingerprint:
            raise RuntimeError('runtime fingerprint changed; no robot task dispatched')
        os.environ['FLEXCELL_RUNTIME_FINGERPRINT'] = fingerprint
        stack = subprocess.Popen(['ros2', 'launch', 'flexcell_skills', 'trusted_sim.launch.py',
                                  'world:=' + str(world), 'params_file:=' + str(params),
                                  'camera:=' + str(args.camera).lower()],
                                 stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        remember_owned(out, stack)
        ready = False
        for attempt in range(1, 7):
            if stack.poll() is not None:
                raise RuntimeError('owned launch exited during startup')
            time.sleep(3)
            target = out / ('health_before_%d' % attempt)
            if command([sys.executable, str(ROOT / 'setup/flexcell_admin.py'), 'health'], target, timeout=40) == 0:
                doc = json.loads(target.with_suffix('.stdout').read_text())
                if (doc.get('ok') is True and doc.get('hard_fail') == []
                        and doc['checks'].get('task_state') == 'IDLE'
                        and doc['checks'].get('carry_engaged') is False):
                    ready = True
                    break
        if not ready:
            raise RuntimeError('strict startup health failed; no robot task dispatched')
        if args.physics_step_s is not None:
            step_path = out / 'physics_steps.jsonl'
            step_ready = False
            for _ in range(25):
                if step_path.exists():
                    with step_path.open('rb') as stream:
                        offset = max(0, step_path.stat().st_size - 512_000)
                        stream.seek(offset)
                        data = stream.read()
                        if offset:
                            data = data.split(b'\n', 1)[-1]
                        complete = data.rsplit(b'\n', 1)[0].splitlines()
                    if len(complete) >= 2:
                        last = [json.loads(line) for line in complete[-2:]]
                        step_ready = (last[1]['sim_ns'] - last[0]['sim_ns'] == 2_000_000 and
                                      last[1]['step_ns'] == 2_000_000)
                        if args.min_preflight_rtf:
                            step_ready = step_ready and len(complete) >= 251
                            if step_ready:
                                first = json.loads(complete[-251])
                                wall = last[-1]['monotonic_ns'] - first['monotonic_ns']
                                sim = last[-1]['sim_ns'] - first['sim_ns']
                                measured = sim / wall if wall > 0 else 0.
                                result['preflight_rtf'] = measured
                                step_ready = measured >= args.min_preflight_rtf
                        if step_ready: break
                time.sleep(.2)
            if not step_ready:
                raise RuntimeError('per-step physics trace unavailable; no robot task dispatched')
        recorder_log = (out / 'recorder.log').open('x')
        recorder = subprocess.Popen([sys.executable, str(ROOT / 'scripts/record_sim_data.py'),
            '--out', str(out / 'data'), *(['--camera'] if args.camera else [])],
            stdout=recorder_log, stderr=subprocess.STDOUT, start_new_session=True)
        remember_owned(out, recorder)
        time.sleep(2)
        if recorder.poll() is not None:
            raise RuntimeError('data recorder exited before task')
        if command([sys.executable, str(ROOT / 'setup/flexcell_admin.py'), 'reset'], out / 'reset_before'):
            raise RuntimeError('canonical reset failed; no robot task dispatched')
        if args.camera and command([sys.executable, str(ROOT / 'scripts/prepare_recording.py')],
                                    out / 'prepare_recording'):
            raise RuntimeError('recording preparation failed; no task dispatched')
        if args.camera:
            camera_ready = False
            for _ in range(50):
                frames = out / 'data/frames.jsonl'
                if frames.exists() and frames.stat().st_size:
                    rows = [json.loads(line) for line in frames.read_text().split('\n')[:-1]]
                    if rows and rows[-1]['valid'] is True:
                        camera_ready = True
                        break
                time.sleep(.2)
            if not camera_ready:
                raise RuntimeError('aligned camera/state/action stream not ready; no task dispatched')
        if args.case in ('recovery_once', 'budget_exhaustion'):
            injection = 'trusted_smoke@%s:%s' % (args.object,
                         'once' if args.case == 'recovery_once' else 'always')
            if command([sys.executable, str(ROOT / 'src/flexcell/flexcell_skills/test/w1_client.py'),
                        '--action', 'inject', '--inject', injection, '--inject-request-id', uuid.uuid4().hex,
                        '--expect-inject-state', 'armed'], out / 'injection_arm'):
                raise RuntimeError('injection arm not sealed; no task dispatched')
        result['physical_tasks_dispatched'] = 1
        if args.camera:
            result['recording_start_monotonic_ns'] = time.monotonic_ns()
            result['recording_context_s'] = 1.0
            time.sleep(1.)
        result['task_start_monotonic_ns'] = time.monotonic_ns()
        pose = ['.44', '.40', '.0175'] if args.case == 'unreachable_place' else ['.12', '-.15', '.0175']
        result['goal_pose'] = [float(value) for value in pose]
        rc = command([sys.executable, str(ROOT / 'src/flexcell/flexcell_skills/test/w1_client.py'),
                      '--action', 'demo' if args.case == 'dual_object' else 'task',
                      '--object', args.object, '--pose', *pose,
                      '--timeout', '150'], out / 'task', timeout=170)
        task_output = (out / 'task.stdout').read_text()
        result['task_end_monotonic_ns'] = time.monotonic_ns()
        if args.camera:
            time.sleep(1.)
            result['recording_end_monotonic_ns'] = time.monotonic_ns()
        if 'RESULT ' not in task_output:
            result['status'] = 'ACTION_TERMINAL_UNKNOWN'
            raise RuntimeError('task has no terminal result; subsequent reset is forbidden')
        task = json.loads(task_output.split('RESULT ', 1)[1])
        result['task'] = task
        skill_records = []
        for name in ('pick', 'place'):
            path = out / ('skills/%s.jsonl' % name)
            if path.exists():
                skill_records.extend(json.loads(line) for line in path.read_text().splitlines())
        if any('MotionTerminalUnknown' in row.get('detail', '') for row in skill_records):
            result['status'] = 'ACTION_TERMINAL_UNKNOWN'
            raise RuntimeError('child motion terminal unknown; subsequent reset is forbidden')
        expected_failure = (
            args.case == 'budget_exhaustion' and task.get('outcome_val') == 1
            and task.get('error_code') == 'ERR_RECOVERY_EXHAUSTED'
            and sum(row.get('injected') is True for row in skill_records) == 2)
        expected_failure = expected_failure or (
            args.case == 'unreachable_place' and task.get('outcome_val') == 1
            and task.get('error_code') == 'ERR_SKILL_FAILED'
            and any(row.get('skill_backend') == 'mtc' and row.get('outcome') != '0'
                    for row in skill_records))
        succeeded = rc == 0 and task.get('outcome_val') == 0 and (
            task.get('object_a_at_zone') is True and task.get('object_b_at_zone') is True
            if args.case == 'dual_object' else task.get('object_at_place') is True)
        if args.case == 'recovery_once':
            succeeded = succeeded and sum(row.get('injected') is True for row in skill_records) == 1
        if not succeeded and not expected_failure:
            result['status'] = 'ROBOT_FAILURE'
            raise RuntimeError('typed task failure retained; no replacement task')
        if args.case in ('recovery_once', 'budget_exhaustion'):
            if command([sys.executable, str(ROOT / 'src/flexcell/flexcell_skills/test/w1_client.py'),
                        '--action', 'inject', '--inject', '', '--inject-request-id', uuid.uuid4().hex,
                        '--expect-inject-state', 'cleared'], out / 'injection_clear'):
                raise RuntimeError('injection clear not sealed')
        if command([sys.executable, str(ROOT / 'setup/flexcell_admin.py'), 'reset'], out / 'reset_after'):
            raise RuntimeError('post-task reset failed')
        if command([sys.executable, str(ROOT / 'setup/flexcell_admin.py'), 'health'], out / 'health_after'):
            raise RuntimeError('post-task strict health failed')
        result['status'] = 'EXPECTED_FAILURE' if expected_failure else 'PASS'
        result['expectation_met'] = True
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        result['error'] = str(exc)
        if result['physical_tasks_dispatched'] and 'task' not in result:
            result['status'] = 'ACTION_TERMINAL_UNKNOWN'
    finally:
        if recorder is not None:
            terminate_owned(recorder)
            recorder_log.close()
            result['recorder_exit'] = recorder.returncode
            if recorder.returncode != 0 and result['status'] in ('PASS', 'EXPECTED_FAILURE'):
                result['status'] = 'EVIDENCE_FAILURE'
                result['expectation_met'] = False
        if stack is not None:
            terminate_owned(stack)
            result['owned_launch_exit'] = stack.returncode
        log.close()
        result = json_result(result)
        (out / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
        print(json.dumps(result, indent=2), flush=True)
    return 0 if result['status'] in ('PASS', 'EXPECTED_FAILURE') else 1


if __name__ == '__main__':
    sys.exit(main())
