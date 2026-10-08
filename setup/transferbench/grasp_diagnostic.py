"""Once-only A/B direct-skill diagnostics under an unchanged FSM deployment."""
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

import qualification_prepare as q

TOOL_FILES = ('setup/136_grasp_diagnostic.py', 'setup/transferbench/grasp_diagnostic.py',
              'setup/transferbench/qualification_prepare.py', 'setup/131_prebatch_readiness.py',
              'setup/flexcell_admin.py', 'src/flexcell/flexcell_skills/test/w1_client.py')
AUTHORITY = Path('/home/ros/agentic_workcell_ws')
LOGS = Path.home() / '.ros/flexcell'
RUNTIME = Path.home() / '.local/share/flexcell/mainline/runtime'


def write(path, value):
    with path.open('xb') as f:
        f.write(q.encoded(value)); f.flush(); os.fsync(f.fileno())


def files(path):
    if path.is_file():
        return {'sha256': q.sha(path), 'bytes': path.stat().st_size}
    q.require(path.is_dir(), 'protected path missing: ' + str(path))
    return {str(p.relative_to(path)): files(q.regular(path, str(p.relative_to(path))))
            for p in sorted(path.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}


def module(path):
    spec = importlib.util.spec_from_file_location('grasp_readiness', path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


def register(root, workspace, deployment, revision, protected):
    q.sha_value(revision, 40)
    q.require(not root.exists() and not any(p.is_symlink() for p in (root, *root.parents))
              and '..' not in root.parts, 'diagnostic root must be new and regular')
    d = q.loads(deployment.read_bytes())
    q.require(d['policy'] == 'fsm' and d['threshold'] == .85, 'frozen FSM 0.85 required')
    module(workspace / 'setup/131_prebatch_readiness.py').verify_deployment(d, workspace)
    pins = {str(p.resolve()): files(p) for p in protected}
    if workspace.resolve() == AUTHORITY:
        required = (LOGS / 'episodes', Path(os.environ['FLEXCELL_JEV_CALIBRATION']),
                    Path(os.environ['FLEXCELL_LLM_BUDGET_FILE']))
        q.require(all(str(p.resolve()) in pins for p in required), 'history, calibration and budget protection required')
    q.require(all(not root.resolve().is_relative_to(p.resolve())
                  and not p.resolve().is_relative_to(root.resolve()) for p in protected),
              'diagnostic cannot overlap protected evidence')
    plan = dict(schema_version=1, record_kind='REGISTERED_DIRECT_GRASP_DIAGNOSTIC',
                revision=revision, workspace=str(workspace.resolve()),
                deployment=str(deployment.resolve()), deployment_sha256=q.sha(deployment),
                runtime_fingerprint=d['runtime_fingerprint'], objects=list(q.OBJECTS),
                initial_objects=q.SOURCE, max_pick_goals=2, replacement_trials=False,
                cleanup='CANONICAL_RESET_AFTER_CONFIRMED_PICK_TERMINAL',
                source_sha256={rel: q.sha(q.regular(workspace, rel)) for rel in TOOL_FILES},
                protected=pins, policy_inference_calls=0, qualification_sampling_authorized=False,
                ready_for_large_test=False, n_ge_50='FROZEN', physical_hardware='NOT_RUN')
    root.mkdir(parents=True); write(root / 'plan.json', plan)
    return status(root, q.sha(root / 'plan.json'), workspace)


def verify(root, expected, workspace):
    q.sha_value(expected)
    q.require(q.sha(q.regular(root, 'plan.json')) == expected, 'plan identity changed')
    plan = q.loads((root / 'plan.json').read_bytes())
    q.require(plan['workspace'] == str(workspace.resolve()) and plan['objects'] == list(q.OBJECTS)
              and plan['max_pick_goals'] == 2 and plan['replacement_trials'] is False
              and q.same_typed(plan['initial_objects'], q.SOURCE), 'diagnostic protocol changed')
    q.require(q.sha(Path(plan['deployment'])) == plan['deployment_sha256'], 'deployment changed')
    for rel, digest in plan['source_sha256'].items():
        q.require(q.sha(q.regular(workspace, rel)) == digest, 'instrument source changed: ' + rel)
    q.require(set(plan['source_sha256']) == set(TOOL_FILES), 'instrument file set changed')
    for path, pin in plan['protected'].items():
        q.require(q.same_typed(files(Path(path)), pin), 'protected evidence changed: ' + path)
    return plan


def status(root, expected, workspace):
    verify(root, expected, workspace)
    path = root / 'execution/report.json'
    if path.exists():
        result = q.loads(path.read_bytes())
    else:
        result = dict(state='UNKNOWN_TAIL' if (root / 'execution').exists() else 'REGISTERED',
                      trials=[], pick_goals=0 if not (root / 'execution').exists() else 'UNKNOWN')
    return dict(result, ok=True, plan_sha256=expected, dispatch_authorized=False,
                qualification_sampling_authorized=False, ready_for_large_test=False, n_ge_50='FROZEN')


def command_ok(value):
    return type(value.get('return_code')) is int and value['return_code'] == 0


def result_json(command, action):
    q.require(type(command.get('return_code')) is int and command['return_code'] in (0, 1),
              'signaled, timed-out or unconfirmed client process')
    lines = command['stdout'].splitlines()
    marked = [s[7:] for s in lines if s.startswith('RESULT ')]
    goals = [s[10:] for s in lines if s.startswith('GOAL_UUID ')]
    q.require(len(marked) == len(goals) == 1 and re.fullmatch('[0-9a-f]{32}', goals[0]),
              'one correlated goal and terminal result required')
    # w1_client prints indent=2 JSON; consume the complete terminal payload.
    value = q.loads(command['stdout'].split('RESULT ', 1)[1])
    q.require(type(value) is dict and value.get('goal_uuid') == goals[0] and value.get('action') == action
              and type(value.get('outcome_val')) is int and type(value.get('action_status')) is int,
              'typed, correlated action result required')
    combos = {(4, 0, 0), (6, 1, 1), (5, 2, 1)}
    q.require((value['action_status'], value['outcome_val'], command['return_code']) in combos,
              'action status, outcome and process disagree')
    q.require(type(value.get('error_code')) is str and value['error_code'].startswith('ERR_'),
              'typed error code required')
    if value['outcome_val'] == 0:
        q.require(value.get('error_code') == 'ERR_NONE', 'success error code mismatch')
    if action == 'pick' and value['outcome_val'] == 0:
        q.require(value.get('grasp_attached') is True and type(value.get('motion_error_code')) is int
                  and value['motion_error_code'] == 0, 'success grasp marker required')
    return value


def positions(result, released=False):
    q.require(result['outcome_val'] == 0, 'Observe failed')
    if released:
        q.require(result.get('carry', {}).get('engaged') is False
                  and result['carry'].get('object_id') == '', 'carry release not confirmed')
    objects = result.get('objects')
    q.require(type(objects) is list and all(type(o) is dict for o in objects), 'objects missing')
    q.require(len({o.get('name') for o in objects}) == len(objects), 'duplicate observed objects')
    found = {o['name']: o.get('position') for o in objects if o.get('available') is True}
    q.require(all(name in found and q.point(found[name]) for name in q.OBJECTS), 'measured positions missing')
    return {name: found[name] for name in q.OBJECTS}


def audit_pick(result, records, target):
    selected = [r for r in records if r.get('evidence_id') == result.get('evidence_id')]
    q.require(bool(result.get('evidence_id')) and len(selected) == 1, 'one matching raw pick record required')
    rec = selected[0]
    q.require(rec.get('object_name') == target and rec.get('outcome') == str(result['outcome_val'])
              and type(rec.get('error_code')) is int and type(rec.get('motion_error_code')) is int
              and type(rec.get('status')) is int and rec['status'] == (1, 2, 4)[result['outcome_val']]
              and rec['motion_error_code'] == result.get('motion_error_code')
              and rec.get('detail') == result.get('detail'), 'raw pick/client disagree')
    q.require((rec['error_code'] == 0) == (result['outcome_val'] == 0), 'raw success error code mismatch')
    detail = rec['detail'].lower()
    q.require(rec['error_code'] != 2 and 'timeout' not in detail and 'timed out' not in detail,
              'internal error or nested acknowledgement timeout leaves ownership unknown')
    measured = {}
    for name in ('box_before', 'box_after', 'carry_offset'):
        if name in rec:
            q.require(q.point(rec[name]), 'nonfinite measured ' + name); measured[name] = rec[name]
    for name in ('attach_gap_m', 'box_rise_m'):
        if name in rec:
            q.require(type(rec[name]) in (int, float) and q.point([rec[name], 0, 0]), 'invalid measured ' + name)
            q.require(name != 'attach_gap_m' or rec[name] >= 0, 'negative attach gap')
            measured[name] = rec[name]
    if 'box_rise_m' in rec:
        q.require('box_before' in measured and 'box_after' in measured
                  and abs(measured['box_after'][2] - measured['box_before'][2] - rec['box_rise_m']) < 1e-9,
                  'measured rise inconsistent')
    if result['outcome_val'] == 0:
        q.require(set(measured) == {'box_before', 'box_after', 'carry_offset', 'attach_gap_m', 'box_rise_m'}
                  and rec.get('carry_engage_confirmed') is True and measured['box_rise_m'] >= .03,
                  'measured successful follow not established')
    return dict(object=target, outcome=('SUCCEEDED', 'FAILED', 'CANCELED')[result['outcome_val']],
                goal_uuid=result['goal_uuid'], evidence_id=result['evidence_id'], raw_pick=rec,
                measured=measured, carry_engage_confirmed=rec.get('carry_engage_confirmed', 'NOT_MEASURED'),
                mechanism_root_cause='UNKNOWN', success_rate='NOT_ESTIMATED', decision_latency_ms='NOT_RUN')


def controller_audit(raw):
    events = []
    for path in raw.glob('*transport.jsonl'):
        events.extend(q.loads(s) for s in path.read_text().splitlines() if s.strip())
    q.require(not any('quarantin' in str(e.get('event')) or e.get('event') in
                        ('goal_send_timeout', 'goal_response_unknown', 'goal_response_error') for e in events),
              'unknown transport ownership; no reset or next goal')
    controllers = [e for e in events if e.get('kind') == 'controller_transport']
    requested = {e.get('controller_goal_uuid') for e in controllers if e.get('event') == 'controller_goal_send_requested'}
    terminal = {e.get('controller_goal_uuid') for e in controllers if e.get('event') == 'controller_goal_terminal'
                and type(e.get('status')) is int and e['status'] in (4, 5, 6)}
    rejected = {e.get('controller_goal_uuid') for e in controllers if e.get('event') == 'controller_goal_response'
                and e.get('accepted') is False}
    q.require(all(type(g) is str and re.fullmatch('[0-9a-f]{32}', g) for g in requested)
              and requested.issubset(terminal | rejected), 'controller terminal ownership unconfirmed')
    return dict(requested_goals=len(requested), terminal_goals=len(terminal), rejected_goals=len(rejected))


class LiveBackend:
    def __init__(self, workspace):
        q.require(workspace.resolve() == AUTHORITY, 'live execution requires WSL authority')
        self.workspace = workspace
        self.client = workspace / 'src/flexcell/flexcell_skills/test/w1_client.py'

    def command(self, directory, name, argv, timeout):
        start = time.perf_counter_ns()
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
            value = dict(return_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
        except subprocess.TimeoutExpired as exc:
            text = lambda s: s.decode(errors='replace') if isinstance(s, bytes) else s or ''
            value = dict(return_code=None, timeout=True, stdout=text(exc.stdout), stderr=text(exc.stderr))
        value.update(command=argv, elapsed_ms=(time.perf_counter_ns() - start) / 1e6)
        write(directory / (name + '.json'), value); return value

    def health(self, directory, plan):
        current = sorted(RUNTIME.glob('*/deployment.json'))[-1]
        d = q.loads(current.read_bytes())
        q.require(d['runtime_fingerprint'] == plan['runtime_fingerprint'] and d['policy'] == 'fsm',
                  'active deployment identity changed')
        report = directory / 'health_report.json'
        cmd = self.command(directory, 'health', [sys.executable, str(self.workspace / 'setup/131_prebatch_readiness.py'),
            '--live', '--workspace', str(self.workspace), '--deployment', str(current), '--out', str(report)], 85)
        q.require(command_ok(cmd) and q.loads(report.read_bytes()).get('read_only_preflight_ok') is True,
                  'strict idle/released preflight failed')

    def reset(self, directory, name):
        cmd = self.command(directory, name, [sys.executable, str(self.workspace / 'setup/flexcell_admin.py'), 'reset'], 150)
        q.require(command_ok(cmd) and q.loads(cmd['stdout']).get('ok') is True,
                  'reset unconfirmed; no next goal')

    def clear(self, directory, target):
        rid = 'grasp-diagnostic-' + uuid.uuid4().hex
        cmd = self.command(directory, 'clear', [sys.executable, str(self.client), '--action', 'inject',
            '--inject-request-id', rid, '--expect-inject-state', 'cleared'], 25)
        q.require(command_ok(cmd) and cmd['stdout'].count(' observed=') == 1, 'injection clear unconfirmed')
        state = q.loads(cmd['stdout'].split(' observed=', 1)[1].splitlines()[0])
        q.require(state.get('request_id') == rid and state.get('state') == 'cleared', 'injection receipt mismatch')

    def observe(self, directory, name):
        return result_json(self.command(directory, name,
            [sys.executable, str(self.client), '--action', 'observe', '--timeout', '25'], 35), 'observe')

    def offsets(self):
        return {p.name: files(p) for p in LOGS.glob('*.jsonl')}

    def capture(self, directory, before):
        directory.mkdir()
        for name, pin in before.items():
            raw = (LOGS / name).read_bytes()
            q.require(q.sha_bytes(raw[:pin['bytes']]) == pin['sha256'], 'raw log truncated or rewritten: ' + name)
            with (directory / name).open('xb') as f: f.write(raw[pin['bytes']:])

    def pick(self, directory, target):
        return self.command(directory, 'pick', [sys.executable, str(self.client),
            '--action', 'pick', '--object', target, '--timeout', '90'], 105)


def run(root, expected, workspace, backend):
    plan = verify(root, expected, workspace)
    execution = root / 'execution'; execution.mkdir()  # exclusive claim; interrupted runs cannot repeat
    def event(kind, **fields):
        with (execution / 'events.jsonl').open('ab') as f:
            f.write(q.encoded(dict(event=kind, wall_ns=time.time_ns(), **fields)).replace(b'\n', b' ') + b'\n')
            f.flush(); os.fsync(f.fileno())
    report = dict(state='RUNNING', trials=[], pick_goals=0, policy_inference_calls=0,
                  task_episode_generation='NOT_EXPECTED; VERIFY_PROTECTED_HISTORY',
                  evidence_scope='TWO_ONCE_ONLY_DIRECT_PICKS; RESET_AFTER_EACH',
                  mechanism_root_cause='UNKNOWN', n_ge_50='FROZEN', ready_for_large_test=False)
    event('STARTED', plan_sha256=expected)
    try:
        for index, target in enumerate(plan['objects']):
            verify(root, expected, workspace)
            trial = execution / ('%02d-' % index + target); trial.mkdir()
            boundary = trial / 'before'; boundary.mkdir(); backend.health(boundary, plan)
            backend.reset(trial, 'reset_before'); backend.clear(trial, target)
            observed = backend.observe(trial, 'observe_before')
            layout = positions(observed, released=True)
            q.require(q.near(layout, plan['initial_objects']), 'canonical initial layout differs')
            write(trial / 'exposure_before.json', dict(record_kind='DIRECT_SKILL_DIAGNOSTIC_EXPOSURE', initial_objects=layout))
            before = backend.offsets()
            write(trial / 'raw_offsets.json', before)
            event('PICK_INTENT', object=target, slot=index); report['pick_goals'] += 1
            cmd = backend.pick(trial, target)
            backend.capture(trial / 'pick_raw', before)
            result = result_json(cmd, 'pick')
            controller = controller_audit(trial / 'pick_raw')
            records = [q.loads(s) for s in (trial / 'pick_raw/pick.jsonl').read_text().splitlines() if s.strip()]
            summary = audit_pick(result, records, target); summary['controllers'] = controller
            q.require(summary['outcome'] != 'SUCCEEDED' or controller['terminal_goals'] > 0,
                      'successful pick lacks controller terminal evidence')
            write(trial / 'pick_audit.json', summary); report['trials'].append(summary)
            event('PICK_TERMINAL', object=target, outcome=summary['outcome'], goal_uuid=result['goal_uuid'])
            # The known terminal permits cleanup even if post-pick observation fails.
            try:
                try:
                    post = positions(backend.observe(trial, 'observe_after'))
                    write(trial / 'exposure_after.json', dict(record_kind='DIRECT_SKILL_DIAGNOSTIC_EXPOSURE', initial_objects=post))
                finally:
                    backend.reset(trial, 'reset_after')
                    boundary = trial / 'after'; boundary.mkdir(); backend.health(boundary, plan)
                    event('RESET_CONFIRMED', object=target)
            finally:
                # Read-only capture also preserves a failed observation/cleanup tail.
                backend.capture(trial / 'full_raw', before)
            verify(root, expected, workspace)
        report['state'] = 'COMPLETE'
    except Exception as exc:
        report.update(state='STOPPED', stop_reason=type(exc).__name__ + ': ' + str(exc))
        event('STOPPED', reason=report['stop_reason'], no_automatic_reset=True)
    write(execution / 'report.json', report)
    event('FINISHED', state=report['state'], pick_goals=report['pick_goals'])
    return dict(report, ok=report['state'] == 'COMPLETE', plan_sha256=expected,
                qualification_sampling_authorized=False, dispatch_authorized=False)
