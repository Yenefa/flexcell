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


MODEL_SOURCES = ('llm', 'jev')


def summarize_routing(rows):
    """Summarise what the decision log actually shows. Pure: no ROS, no I/O.

    A hybrid row keeps the router metadata at the top and the real arm responses under
    ``proposals``; every other policy row is a single leaf. Calls are counted per leaf,
    so a fast call that escalated to the slow arm reports fast 1 + slow 1 instead of
    nothing, and identity is reported separately from the call itself.
    """
    sources, leaves, models, backends = {}, {}, set(), set()
    fast = slow = unknown = fallbacks = 0
    for row in rows:
        trace = row.get('policy_trace') or {}
        outer = trace.get('source') or ('fallback' if trace.get('fallback') else row.get('policy'))
        sources[str(outer)] = sources.get(str(outer), 0) + 1
        if trace.get('fallback'):
            fallbacks += 1
        proposals = trace.get('proposals') or []
        leaf_traces = ([proposal.get('policy_trace') or {} for proposal in proposals]
                       or [trace or {'source': row.get('policy')}])
        for leaf in leaf_traces:
            source = str(leaf.get('source') or '')
            leaves[source] = leaves.get(source, 0) + 1
            if source not in MODEL_SOURCES:
                continue
            if source == 'jev':
                fast += 1
            else:
                slow += 1
            # The slow arm reports response_model, the fast arm reports model; neither is
            # guaranteed. A missing identity must not erase a call that did happen.
            identity = leaf.get('response_model') if source == 'llm' else leaf.get('model')
            if identity:
                models.add(str(identity))
            else:
                unknown += 1
            if leaf.get('backend'):
                backends.add(str(leaf['backend']))
    return dict(decisions=len(rows), sources=sources, leaves=leaves, fallbacks=fallbacks,
                models=sorted(models), backends=sorted(backends),
                fast_calls=fast, slow_calls=slow, model_calls=fast + slow,
                calls_without_identity=unknown)


def completion_expectation(decision_policy, resume_completed):
    """Skill calls an already_placed task must show, or None when a model may legally
    verify an object that is already at its goal instead of carrying it."""
    if resume_completed:
        return {'pick': 0, 'place': 0, 'verify': 1}
    if decision_policy == 'fsm':
        return {'pick': 1, 'place': 1, 'verify': 1}
    return None


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
    parser.add_argument('--planner-diagnostics', action='store_true')
    parser.add_argument('--level-release-tolerance-deg', type=float,
                        help='issue #121: opt-in level-release box-tilt tolerance for the '
                             'mtc place path; requires --skill-backend mtc')
    parser.add_argument('--resume-completed', action='store_true')
    parser.add_argument('--decision-policy', choices=['fsm', 'jev', 'llm', 'hybrid'], default='fsm')
    parser.add_argument('--hybrid-threshold', type=float,
                        help='declared router threshold; required for, and only for, the hybrid policy')
    parser.add_argument('--case', choices=['normal', 'dual_object', 'recovery_once', 'budget_exhaustion',
                                           'unreachable_place', 'false_attach', 'already_placed', 'regrasp'], default='normal')
    parser.add_argument('--false-attach', default='',
                        help='declared live false-attach spec, object:offset_m[:hold_s]')
    args = parser.parse_args()
    out = args.out / ('run-' + uuid.uuid4().hex[:12])
    out.mkdir(parents=True, exist_ok=False)
    options = {}
    if args.contact_trace: options['contact_trace'] = True
    if args.release_clearance_m is not None: options['release_clearance_m'] = args.release_clearance_m
    if args.qualification_no_recovery: options['qualification_no_recovery'] = True
    if args.resume_completed: options['resume_completed_objects'] = True
    options['decision_policy'] = args.decision_policy
    if args.hybrid_threshold is not None: options['hybrid_threshold'] = args.hybrid_threshold
    params, world = profile(out, args.backend, args.camera, args.skill_backend,
                            args.joint_hold_sim_s, args.physics_step_s, **options)
    if args.level_release_tolerance_deg is not None:
        if args.skill_backend != 'mtc':
            raise ValueError('the level-release tolerance belongs to the mtc place path only')
        if not 0. <= args.level_release_tolerance_deg <= 45.:
            raise ValueError('the level-release tolerance must be within [0, 45] deg')
        config = yaml.safe_load(params.read_text())
        config.setdefault('mtc_planner', {}).setdefault('ros__parameters', {})[
            'level_release_pitch_tolerance_deg'] = float(args.level_release_tolerance_deg)
        with params.open('w') as stream:
            yaml.safe_dump(config, stream, sort_keys=False)
    if args.physics_step_s is not None:
        os.environ['FLEXCELL_PHYSICS_STEP_LOG'] = str(out / 'physics_steps.jsonl')
    if args.contact_trace:
        os.environ['FLEXCELL_CONTACT_STEP_LOG'] = str(out / 'contact_steps.jsonl')
    else:
        os.environ.pop('FLEXCELL_CONTACT_STEP_LOG', None)
    os.environ['FLEXCELL_EPISODE_DIR'] = str(out / 'episodes')
    if args.false_attach:
        if args.case != 'false_attach':
            raise ValueError('the false-attach spec belongs to the false_attach case only')
        os.environ['FLEXCELL_FALSE_ATTACH'] = args.false_attach
    else:
        os.environ.pop('FLEXCELL_FALSE_ATTACH', None)
    if args.planner_diagnostics:
        os.environ['FLEXCELL_MTC_DIAGNOSTIC_DIR'] = str(out / 'planner')
    else:
        os.environ.pop('FLEXCELL_MTC_DIAGNOSTIC_DIR', None)
    result = dict(schema_version=1, status='HARNESS_ERROR', backend=args.backend,
                  skill_backend=args.skill_backend, physical_tasks_dispatched=0,
                  qualification='FUNCTIONAL_SMOKE_ONLY', case=args.case, object=args.object, out=str(out))
    # Declared routing, plus the non-secret model configuration the child processes
    # inherit. The actual routing is summarised from the decision log after the task,
    # so a silent fallback to the FSM cannot be reported as a model sample.
    result['decision_policy'] = args.decision_policy
    result['hybrid_threshold'] = args.hybrid_threshold
    result['resume_completed'] = bool(args.resume_completed)
    result['model_env'] = {name: os.environ.get(name) for name in
                           ('FLEXCELL_LLM_ENDPOINT', 'FLEXCELL_LLM_MODEL',
                            'FLEXCELL_LLM_BACKEND', 'FLEXCELL_JEV_ENDPOINT',
                            'FLEXCELL_JEV_MODEL', 'FLEXCELL_JEV_BACKEND')}
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
        if args.contact_trace:
            from contact_probe import mapped_libraries
            names = ('flexcell_physics_trace', 'flexcell_contact_trace', 'flexcell_detachable_carry',
                     'mtc_planner', 'libdart')
            loaded = mapped_libraries(stack.pid, names)
            (out / 'runtime_native_mapping.json').write_text(json.dumps(loaded, indent=2) + '\n')
            required = ['lib/libflexcell_physics_trace.so', 'lib/libflexcell_contact_trace.so',
                        'lib/libflexcell_detachable_carry.so']
            if args.skill_backend == 'mtc': required.append('lib/flexcell_mtc/mtc_planner')
            for relative in required:
                actual = [digest for path, digest in loaded.items() if Path(path).name == Path(relative).name]
                expected = identity['native_libraries'].get(relative)
                if expected is None or actual != [expected]:
                    raise RuntimeError('actually mapped native identity mismatch: ' + relative)
            result['native_identity_verified_before_dispatch'] = True
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
        if args.case == 'already_placed':
            # The declared task goal equals this object's canonical spawn. No
            # fixture teleport or changed verifier is needed for this control.
            pose = (['.22', '0', '.0175'] if args.object == 'target_box_a' else ['.20', '-.18', '.0175'])
        result['goal_pose'] = [float(value) for value in pose]
        rc = command([sys.executable, str(ROOT / 'src/flexcell/flexcell_skills/test/w1_client.py'),
                      '--action', 'demo' if args.case == 'dual_object' else 'task',
                      '--object', args.object, '--pose', *pose,
                      '--timeout', '150'], out / 'task', timeout=170)
        task_output = (out / 'task.stdout').read_text()
        result['task_end_monotonic_ns'] = time.monotonic_ns()
        if args.camera and args.case != 'regrasp':
            # A regrasp run keeps recording through the second task; the
            # boundary is finalised below so the exported episode covers both.
            time.sleep(1.)
            result['recording_end_monotonic_ns'] = time.monotonic_ns()
        if 'RESULT ' not in task_output:
            result['status'] = 'ACTION_TERMINAL_UNKNOWN'
            raise RuntimeError('task has no terminal result; subsequent reset is forbidden')
        task = json.loads(task_output.split('RESULT ', 1)[1])
        result['task'] = task
        # Issue #121 regrasp window: a second pick-place on the SAME live stack,
        # picking the object from wherever the first task left it (the pick
        # samples gz ground truth at grasp time, so no reset happens). The final
        # judgement covers both tasks.
        if args.case == 'regrasp':
            # Stop for reconciliation: never dispatch a second physical task when
            # the first failed, or when a skill row reports an unknown motion
            # terminal - the previous motion/attachment state is unresolved.
            first_ok = rc == 0 and task.get('outcome_val') == 0
            result['regrasp_first_task_ok'] = first_ok
            first_rows = []
            first_place = out / 'skills/place.jsonl'
            if first_place.exists():
                first_rows = [json.loads(line) for line in first_place.read_text().splitlines() if line.strip()]
            unknown_terminal = any('MotionTerminalUnknown' in str(row.get('detail', '')) for row in first_rows)
            if not first_ok or unknown_terminal:
                result['regrasp_blocked'] = dict(first_task_ok=first_ok, unknown_terminal=unknown_terminal)
                result['status'] = 'REGRASP_BLOCKED_FIRST_TASK'
                raise RuntimeError('regrasp not dispatched: first task not clean (ok=%s unknown_terminal=%s)'
                                   % (first_ok, unknown_terminal))
            result['physical_tasks_dispatched'] = 2
            regrasp_pose = ['0.25', '0.05', '.0175']  # zone_2, declared in the FSM
            result['regrasp_goal_pose'] = [float(value) for value in regrasp_pose]
            result['regrasp_start_monotonic_ns'] = time.monotonic_ns()
            rc = command([sys.executable, str(ROOT / 'src/flexcell/flexcell_skills/test/w1_client.py'),
                          '--action', 'task', '--object', args.object, '--pose', *regrasp_pose,
                          '--timeout', '150'], out / 'task_regrasp', timeout=170)
            result['regrasp_end_monotonic_ns'] = time.monotonic_ns()
            if args.camera:
                # Cover the second pick-place in the exported episode: the
                # ledger filters frames by this boundary.
                time.sleep(1.)
                result['recording_end_monotonic_ns'] = time.monotonic_ns()
            regrasp_output = (out / 'task_regrasp.stdout').read_text()
            if 'RESULT ' not in regrasp_output:
                result['status'] = 'ACTION_TERMINAL_UNKNOWN'
                raise RuntimeError('regrasp task has no terminal result; subsequent reset is forbidden')
            task = json.loads(regrasp_output.split('RESULT ', 1)[1])
            result['task_regrasp'] = task
        # Actual routing for this run, read back from the decision log: the declared
        # policy alone cannot show whether a model answered or the FSM fell back.
        decisions = out / 'skills' / 'decisions.jsonl'
        if decisions.exists():
            rows = [json.loads(line) for line in decisions.read_text().splitlines() if line.strip()]
            result['actual_routing'] = summarize_routing(rows)
            result['model_calls'] = result['actual_routing']['model_calls']
            result['fast_calls'] = result['actual_routing']['fast_calls']
            result['slow_calls'] = result['actual_routing']['slow_calls']
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
        # The injection record is written after the last injected frame, which can be
        # later than the moment the skill notices the fault, so reading carry.jsonl here
        # races the writer (it did in CI while passing locally). The trial therefore
        # decides on the typed reason, and `false_attach_gate` asserts afterwards that the
        # injection happened exactly once on the declared frames.
        expected_failure = expected_failure or (
            args.case == 'false_attach' and task.get('outcome_val') == 1
            and task.get('error_code') == 'ERR_SKILL_FAILED'
            and 'physical follow unconfirmed' in str(task.get('detail', '')))
        expected_failure = expected_failure or (
            args.case == 'unreachable_place' and task.get('outcome_val') == 1
            and task.get('error_code') == 'ERR_SKILL_FAILED'
            and any(row.get('skill_backend') == 'mtc' and row.get('outcome') != '0'
                    for row in skill_records))
        succeeded = rc == 0 and task.get('outcome_val') == 0 and (
            task.get('object_a_at_zone') is True and task.get('object_b_at_zone') is True
            if args.case == 'dual_object' else task.get('object_at_place') is True)
        if args.case == 'regrasp':
            succeeded = succeeded and bool(result.get('regrasp_first_task_ok'))
        if args.case == 'recovery_once':
            succeeded = succeeded and sum(row.get('injected') is True for row in skill_records) == 1
        if args.case == 'already_placed':
            counts = {}
            for skill in ('pick', 'place', 'verify'):
                path = out / ('skills/%s.jsonl' % skill)
                counts[skill] = len(path.read_text().splitlines()) if path.exists() else 0
            expected = completion_expectation(args.decision_policy, args.resume_completed)
            result['completion_check'] = dict(resume_enabled=args.resume_completed,
                                              declared_policy=args.decision_policy,
                                              expected=expected, skill_calls=counts)
            if expected is None:
                # A model may legally verify an object that is already at its goal instead
                # of carrying it. Judge the goal and the verification, never the carrying.
                succeeded = succeeded and counts.get('verify', 0) >= 1
            else:
                succeeded = succeeded and counts == expected
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
