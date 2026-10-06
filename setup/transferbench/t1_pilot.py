#!/usr/bin/env python3
"""Register and execute a bounded T1 simulation pilot; never certify AC@90."""

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


REPO = Path(__file__).resolve().parents[2]
LOGS = Path.home() / '.ros/flexcell'
RUNTIME = Path.home() / '.local/share/flexcell/mainline/runtime'
OBJECTS = ('target_box_a', 'target_box_b')
SOURCE = {OBJECTS[0]: [0.22, 0., 0.0175], OBJECTS[1]: [0.20, -0.18, 0.0175]}
SEEDS = (2026100601, 2026100602)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


COST = module('transfer_cost', REPO / 'setup/125_transfer_cost.py')


def clean(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    return value


def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(clean(value), stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def positions(world):
    objects = {obj['name']: obj['pose']['position']
               for obj in world.get('world_state', {}).get('objects', [])}
    if not all(name in objects for name in OBJECTS):
        return None
    return {name: [objects[name][axis] for axis in ('x', 'y', 'z')] for name in OBJECTS}


def same_layout(left, right, tolerance=0.001):
    return bool(left and right and set(left) == set(right) == set(OBJECTS)
                and all(len(left[name]) == len(right[name]) == 3
                        and all(type(v) in (float, int) and math.isfinite(v)
                                for v in (*left[name], *right[name]))
                        and math.dist(left[name], right[name]) <= tolerance for name in OBJECTS))


def result_from_output(output):
    marker = 'RESULT '
    if marker not in output:
        return None
    try:
        result = json.JSONDecoder().raw_decode(output.split(marker, 1)[1].lstrip())[0]
        return result if type(result) is dict else None
    except ValueError:
        return None


def success_predicate(episode, result, return_code):
    """Only a confirmed completed task with both measured verifications passes."""
    if return_code is None or signal_return_code(return_code) or not result or not episode:
        return False
    final = episode.get('final_state') or {}
    # EpisodeSchemaVersion 1 serializes TaskFSM's outcome as canonical text.
    # Accept the integer representation for direct logical fixtures only;
    # never coerce bool, float, padded text, or arbitrary numeric strings.
    outcome = final.get('outcome')
    if not ((type(outcome) is str and outcome == '0')
            or (type(outcome) is int and outcome == 0)):
        return False
    if type(final.get('error_code')) is not int or final['error_code'] != 0:
        return False
    if type(result.get('outcome_val')) is not int or result['outcome_val'] != 0:
        return False
    if final.get('goal_uuid') != result.get('goal_uuid') or episode.get('run_id') != result.get('run_id'):
        return False
    if not final.get('goal_uuid') or not episode.get('run_id'):
        return False
    for tag, target in zip(('a', 'b'), OBJECTS):
        if final.get('object_%s_at_zone' % tag) is not True or result.get('object_%s_at_zone' % tag) is not True:
            return False
        for source in (final, result):
            error = source.get('zone_%s_error_m' % tag)
            if type(error) not in (int, float) or not math.isfinite(error) or not 0 <= error <= 0.06:
                return False
        for action in ('PICK', 'PLACE', 'VERIFY'):
            if not any(step.get('policy_output', {}).get('action') == action
                       and step['policy_output'].get('target') == target
                       and type((step.get('executor_result') or {}).get('outcome')) is int
                       and step['executor_result']['outcome'] == 0 for step in episode.get('steps', [])):
                return False
    return True


def signal_return_code(code):
    return type(code) is int and (code < 0 or 128 < code <= 192)


def profile(deployment):
    return {key: value for key, value in deployment.items()
            if key not in ('head', 'install', 'runtime_fingerprint')}


def verify_deployment(deployment):
    fingerprint = hashlib.sha256(json.dumps(profile(deployment), sort_keys=True).encode()).hexdigest()
    if fingerprint != deployment['runtime_fingerprint']:
        raise ValueError('deployment digest mismatch')
    for mapping in ('source_sha256', 'harness_sha256', 'interface_sources_sha256'):
        for rel, expected in deployment[mapping].items():
            if sha(REPO / rel) != expected:
                raise ValueError('source changed: ' + rel)
    installed = Path(deployment['install']) / 'flexcell_skills/lib/python3.12/site-packages/flexcell_skills'
    for rel, expected in deployment['installed_source_sha256'].items():
        if sha(installed / rel) != expected:
            raise ValueError('installed source changed: ' + rel)


def register(root, deployment_path, revision):
    deployment = json.loads(deployment_path.read_text())
    verify_deployment(deployment)
    if deployment['policy'] != 'hybrid' or deployment['threshold'] != 0.85:
        raise ValueError('starting deployment must be hybrid 0.85')
    budget = budget_snapshot()
    if not budget or budget.get('limit_microyuan') != 5_000_000:
        raise ValueError('existing persistent RMB5 budget must be configured; never reset it')
    root.mkdir()  # exclusive registration, never replace an earlier plan
    plan_dir = root / 'plan'
    plan_dir.mkdir()
    generator = module('s7_geometry', REPO / 'setup/96_s7_perturb.py')
    layouts = {str(seed): {k: list(v) for k, v in generator.sample_placements(
        generator.random.Random(seed), 0.025).items()} for seed in SEEDS}
    history, seen, unreadable = [], [], []
    for path in sorted((LOGS / 'episodes').glob('*.json')):
        history.append(dict(path=str(path), sha256=sha(path)))
        try:
            episode = json.loads(path.read_text())
            for step in episode.get('steps', []):
                raw = step.get('policy_input', {}).get('world_state_canonical')
                if raw:
                    got = positions(json.loads(raw))
                    if got:
                        seen.append(got)
        except (ValueError, KeyError, TypeError):
            unreadable.append(str(path))
    if unreadable or any(same_layout(layout, old) for layout in layouts.values() for old in seen):
        raise ValueError('history incomplete or candidate layout already observed')
    initial = dict(source=SOURCE, adaptation=layouts, seeds=list(SEEDS), amplitude_m=0.025,
                   novelty='not within 1mm of any recorded two-object state in available history',
                   future_qualification_states='NOT_GENERATED; no blind heldout qualification claim',
                   history_episode_files=len(history), history_state_count=len(seen))
    write(plan_dir / 'initial_states.json', initial)
    write(plan_dir / 'history_manifest.json', history)
    predicate = dict(version=1, source_sha256=sha(Path(__file__)),
                     definition='matching run/goal UUID; task/client outcome 0; both measured errors <=0.06m; successful PICK/PLACE/VERIFY per object; reject -6/134',
                     physical_hardware='NOT_RUN', confidence_label='FSM_ACTION_AGREEMENT is not task success')
    write(plan_dir / 'success_predicate.json', predicate)
    contracts = dict(skill_sources=deployment['source_sha256'],
                     interfaces=deployment['interface_sources_sha256'],
                     installed_sources=deployment['installed_source_sha256'],
                     config_sha256=deployment['params_sha256'], world_sha256=deployment['world_sha256'],
                     dds_sha256=deployment['dds_profile_sha256'])
    write(plan_dir / 'skill_contracts.json', contracts)
    expected = {}
    for arm in ('fsm', 'hybrid'):
        data = profile(deployment)
        data['policy'] = arm
        expected[arm] = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        write(plan_dir / ('baseline_' + arm + '.json'),
              dict(data, runtime_fingerprint=expected[arm], source_revision=revision,
                   coding_assistance='same Codex orchestration; no observed human engineering',
                   task_specific_source_changes_allowed=False))
    manifest = dict(protocol_id='flexcell-transferbench-t1-pilot-v1', migration_axis='T1',
                    source_task='week1_demo_v1', target_scenario='transfer_t1_layout01_v1',
                    source_case='T1-source-regression', target_case='T1-layout-01',
                    arms=['fsm', 'hybrid'], order='fsm then hybrid; fixed, not counterbalanced',
                    schedule_per_arm=['target-seed-2026100601', 'target-seed-2026100602', 'source-regression'],
                    max_target_attempts_per_arm=2, max_regression_attempts_per_arm=1,
                    max_runs_per_cell=5, total_planned_robot_episodes=6,
                    additional_paid_stop_threshold_cny=0.25,
                    paid_budget='existing persistent RMB5 absolute cap; no reset; stop threshold checked between episodes, not an invoice',
                    expected_fingerprints=expected, no_failure_replacement=True,
                    stop_conditions=['reset/placement failure', 'unknown goal/result', 'signal including -6/134',
                                     'identity mismatch', 'missing episode', 'routing audit failure', 'paid budget ceiling'],
                    adaptation='reuse frozen task/skills and set registered initial parameters; no policy/prompt/calibration tuning',
                    task_specific_code_change='0 iff frozen sources still match after pilot',
                    human_minutes='NOT_RUN; do not infer zero',
                    coding_agent_time='measured orchestration elapsed; common harness authoring not timed',
                    qualification='FROZEN; adaptation diagnostics only; AC@90 NOT_RUN',
                    rate_comparison='descriptive only, fixed-order two-state pilot cannot establish superiority',
                    ledger_cli_sha256=sha(REPO / 'setup/125_transfer_cost.py'),
                    pilot_harness_sha256=sha(Path(__file__)))
    write(plan_dir / 'task_manifest.json', manifest)
    write(plan_dir / 'registration_budget.json', budget)
    artifacts = {name: str(plan_dir / (name + '.json')) for name in
                 ('task_manifest', 'initial_states', 'success_predicate', 'skill_contracts', 'history_manifest', 'registration_budget')}
    artifacts.update({'baseline_config/' + arm: str(plan_dir / ('baseline_' + arm + '.json'))
                      for arm in manifest['arms']})
    spec = dict(schema_version=1, protocol_id=manifest['protocol_id'], record_kind='PROSPECTIVE_PLAN',
                migration_axis='T1', arms=manifest['arms'], cases=[manifest['target_case'], manifest['source_case']],
                baseline_revisions={arm: revision for arm in manifest['arms']},
                qualification=dict(status='FROZEN', target_success_rate=0.9), freeze_artifacts=artifacts)
    write(plan_dir / 'spec.json', spec)
    frozen = dict(spec, freeze_artifacts={name: COST.pin(path) for name, path in artifacts.items()})
    COST.initialize(root / 'cost.jsonl', frozen)
    print(json.dumps(dict(status='REGISTERED', root=str(root), seeds=list(SEEDS), layouts=layouts,
                          source_history_files=len(history), expected_fingerprints=expected)), flush=True)


def command(directory, name, argv, timeout=240, env=None):
    started = time.perf_counter_ns()
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=env)
        data = dict(command=argv, return_code=result.returncode, stdout=result.stdout, stderr=result.stderr)
    except subprocess.TimeoutExpired as exc:
        data = dict(command=argv, return_code=None, timeout=True,
                    stdout=(exc.stdout or b'').decode() if isinstance(exc.stdout, bytes) else exc.stdout or '',
                    stderr=(exc.stderr or b'').decode() if isinstance(exc.stderr, bytes) else exc.stderr or '')
    data['elapsed_ms'] = (time.perf_counter_ns() - started) / 1e6
    write(directory / (name + '.json'), data)
    return data


def budget_snapshot():
    path = os.environ.get('FLEXCELL_LLM_BUDGET_FILE')
    return json.loads(Path(path).read_text()) if path else None


def new_call_upper_bound(before, after):
    """Scope the ceiling to new IDs; settlement of old calls is not a refund here."""
    old = {row['id'] for row in (before or {}).get('calls', [])}
    return sum(row.get('settled_microyuan', row['reserved_microyuan'])
               for row in (after or {}).get('calls', []) if row['id'] not in old)


def append_trial(root, arm, index, case, outcome, rc, deployment, evidence, run_id=None):
    event = dict(event_id='%s-trial-%d' % (arm, index), kind='trial', arm=arm,
                 trial_id=run_id or '%s-attempt-%d-harness' % (arm, index), purpose='regression' if 'source' in case else 'adaptation',
                 case_id=case, runtime_fingerprint=deployment['runtime_fingerprint'],
                 calibration_sha256=deployment['active_backends']['fast']['calibration_sha256'] if arm == 'hybrid' else None,
                 reported_outcome=outcome, return_code=rc, evidence=[COST.pin(evidence)])
    COST.append(root / 'cost.jsonl', event)


def record_usage(root, arm, attempt, episode, budget_before, budget_after):
    usage_dir = attempt / 'usage'
    usage_dir.mkdir()
    old = {row['id'] for row in (budget_before or {}).get('calls', [])}
    for call in (budget_after or {}).get('calls', []):
        if call['id'] in old:
            continue
        receipt = usage_dir / ('slow-' + call['id'] + '.json')
        write(receipt, dict(record_kind='OBSERVED_BUDGET_RECEIPT', call=call,
                            charge='UNKNOWN: recorded tariff is a peak uncached upper bound, not an invoice'))
        COST.append(root / 'cost.jsonl', dict(event_id=arm+'-slow-'+call['id'], kind='api', arm=arm,
                    request_id=call['id'], scope='adaptation' if attempt.name != 'attempt03' else 'evaluation',
                    input_tokens=call.get('prompt_tokens'), output_tokens=call.get('completion_tokens'),
                    amount=None, currency='CNY', evidence=[COST.pin(receipt)]))
    if not episode:
        return
    for step in episode.get('steps', []):
        trace = step.get('policy_output', {}).get('policy_trace') or {}
        for n, proposal in enumerate(trace.get('proposals', [])):
            if proposal.get('policy') != 'jev' or proposal.get('skipped'):
                continue
            receipt = usage_dir / ('fast-%s-%d-%d.json' % (episode['run_id'], step['seq'], n))
            write(receipt, dict(record_kind='OBSERVED_POLICY_PROPOSAL', run_id=episode['run_id'],
                                seq=step['seq'], proposal=proposal, amount='UNKNOWN: GPU energy/ownership not measured'))
            COST.append(root / 'cost.jsonl', dict(event_id=receipt.stem, kind='api', arm=arm,
                        request_id=receipt.stem, scope='adaptation' if attempt.name != 'attempt03' else 'evaluation',
                        input_tokens=None, output_tokens=None, amount=None, currency='CNY', evidence=[COST.pin(receipt)]))


def run_arm(root, arm):
    from flexcell_skills.contracts.routing_audit import audit_routing_episode
    from flexcell_skills.contracts.episode import replay_episode
    from flexcell_skills.decision_policy import FSMPolicy
    rows = COST.read_ledger(root / 'cost.jsonl')
    spec = rows[0]['payload']['plan']
    manifest = json.loads((root / 'plan/task_manifest.json').read_text())
    initial = json.loads((root / 'plan/initial_states.json').read_text())
    if sha(Path(__file__)) != manifest['pilot_harness_sha256'] or sha(REPO / 'setup/125_transfer_cost.py') != manifest['ledger_cli_sha256']:
        raise ValueError('registered harness changed')
    if arm == 'hybrid':
        previous = json.loads((root / 'fsm/status.json').read_text())
        if previous['stop_reason'] or previous['completed_attempts'] != 3:
            raise ValueError('fixed-order pilot stopped in FSM; do not replace failures or continue')
    arm_dir = root / arm
    arm_dir.mkdir()  # no retry/overwrite after an arm starts
    session = arm + '-orchestration'
    COST.append(root / 'cost.jsonl', dict(event_id=arm+'-start', kind='effort_start', arm=arm,
                session_id=session, actor='coding_agent', activity='pilot orchestration elapsed, not human labor',
                clock_id=COST.clock_id(), start_ns=0), stamp_start=True)
    start_budget = budget_snapshot()
    registration_budget = json.loads((root / 'plan/registration_budget.json').read_text())
    write(arm_dir / 'budget_start.json', start_budget)
    before = set(RUNTIME.iterdir())
    switched = command(arm_dir, 'switch', ['bash', str(REPO / 'setup/102_mainline_runtime.sh'), 'switch', arm, '0.85'], 150)
    created = set(RUNTIME.iterdir()) - before
    if switched['return_code'] != 0 or len(created) != 1:
        raise RuntimeError('policy activation failed; preserve open session and stop pilot')
    runtime = created.pop()
    deployment = json.loads((runtime / 'deployment.json').read_text())
    verify_deployment(deployment)
    if deployment['runtime_fingerprint'] != manifest['expected_fingerprints'][arm]:
        raise ValueError('new runtime differs from registered baseline')
    shutil.copyfile(runtime / 'deployment.json', arm_dir / 'deployment.json')
    summaries = []
    stop_reason = None
    for index in range(1, 4):
        if new_call_upper_bound(registration_budget, budget_snapshot()) >= 250000:
            stop_reason = 'additional paid upper-bound stop threshold reached before next attempt'
            break
        attempt = arm_dir / ('attempt%02d' % index)
        attempt.mkdir()
        case = manifest['source_case'] if index == 3 else manifest['target_case']
        layout = initial['source'] if index == 3 else initial['adaptation'][str(SEEDS[index-1])]
        budget_before = budget_snapshot()
        write(attempt / 'budget_before.json', budget_before)
        offsets = {p.name: p.stat().st_size for p in LOGS.glob('*.jsonl')}
        write(attempt / 'offsets.json', offsets)
        reset = command(attempt, 'reset', [sys.executable, str(REPO / 'setup/flexcell_admin.py'), 'reset'], 300)
        reset_ok = False
        failed_command = reset
        if reset['return_code'] is not None and not signal_return_code(reset['return_code']):
            try:
                reset_ok = json.loads(reset['stdout'])['ok'] is True
            except (ValueError, KeyError, TypeError):
                pass
        harness = None if reset_ok else 'reset did not return JSON ok:true without SIGABRT'
        if not harness and index != 3:
            for name, xyz in layout.items():
                pose = command(attempt, 'pose-'+name,
                    [sys.executable, '-m', 'flexcell_skills.pose_request_worker', name, *map(str, xyz)], 6,
                    dict(os.environ, PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION='python'))
                try:
                    ack = json.loads(pose['stdout'])
                    pose_ok = pose['return_code'] == 0 and ack['transport_ok'] is True and ack['response_data'] is True
                except (ValueError, KeyError, TypeError):
                    pose_ok = False
                if not pose_ok:
                    harness = 'initial pose RPC not confirmed: '+name
                    failed_command = pose
                    break
        if not harness:
            clear = command(attempt, 'clear-injection', [sys.executable,
                str(REPO / 'src/flexcell/flexcell_skills/test/w1_client.py'), '--action', 'inject',
                '--inject', '', '--inject-request-id', arm+'-t1-'+str(index), '--expect-inject-state', 'cleared'], 30)
            if clear['return_code'] != 0:
                harness = 'injection clear not confirmed'
                failed_command = clear
        episode, result, audit, client = None, None, None, None
        if not harness:
            client = command(attempt, 'client', [sys.executable,
                str(REPO / 'src/flexcell/flexcell_skills/test/w1_client.py'), '--action', 'demo',
                '--scenario', 'week1_demo_v1' if index == 3 else manifest['target_scenario']], 220)
            result = result_from_output(client['stdout'])
            if not result or client['return_code'] is None or signal_return_code(client['return_code']):
                harness = 'task terminal result unconfirmed or process aborted'
            if result and result.get('run_id'):
                matches = list((LOGS / 'episodes').glob('*_'+result['run_id']+'.json'))
                if len(matches) == 1:
                    shutil.copyfile(matches[0], attempt / 'episode.json')
                    episode = json.loads((attempt / 'episode.json').read_text())
                else:
                    harness = 'terminal result lacks one matching episode'
            if episode:
                if episode['runtime_fingerprint'] != deployment['runtime_fingerprint']:
                    harness = 'episode fingerprint differs from baseline'
                states = [positions(json.loads(s['policy_input']['world_state_canonical']))
                          for s in episode['steps'] if s['policy_input'].get('world_state_canonical')]
                if not states or not same_layout(states[0], layout):
                    harness = 'policy first observed layout differs from registered initial state'
                if arm == 'hybrid':
                    audit = audit_routing_episode(episode, deployment)
                    if not audit['ok']:
                        harness = 'hybrid routing provenance failed'
                else:
                    replay = replay_episode(episode, FSMPolicy())
                    audit = dict(replay_status='PASS' if replay and all(r['ok'] for r in replay) else 'FAIL',
                                 replayed_steps=len(replay))
                    if audit['replay_status'] != 'PASS':
                        harness = 'FSM replay failed'
        passed = success_predicate(episode, result, (client or {}).get('return_code'))
        budget_after = budget_snapshot()
        write(attempt / 'budget_after.json', budget_after)
        record_usage(root, arm, attempt, episode, budget_before, budget_after)
        raw_dir = attempt / 'raw'
        raw_dir.mkdir()
        for path in LOGS.glob('*.jsonl'):
            previous = offsets.get(path.name, 0)
            if path.stat().st_size < previous:
                raise ValueError('runtime log truncated: '+path.name)
            (raw_dir / path.name).write_bytes(path.read_bytes()[previous:])
        controller_file = raw_dir / 'controller_transport.jsonl'
        if controller_file.exists() and any(json.loads(line).get('event') == 'controller_goal_quarantined'
                for line in controller_file.read_bytes().splitlines() if line.strip()):
            harness = 'controller goal quarantined; stop without resampling'
        outcome = 'HARNESS_ERROR' if harness else 'SUCCEEDED' if passed else 'FAILED'
        summary = dict(record_kind='ACTUAL_SIMULATION_EPISODE' if episode else 'HARNESS_ATTEMPT',
                       transfer_protocol_id=spec['protocol_id'], transfer_plan_sha256=COST.digest(spec),
                       arm=arm, attempt=index, case_id=case, purpose='regression' if index == 3 else 'adaptation',
                       seed=None if index == 3 else SEEDS[index-1], registered_layout=layout,
                       run_id=episode.get('run_id') if episode else None,
                       runtime_fingerprint=deployment['runtime_fingerprint'], outcome=outcome,
                       reported_client_result=result, command_rc=(client or failed_command)['return_code'],
                       harness_error=harness, audit=audit, qualification='NOT_RUN')
        write(attempt / 'summary.json', summary)
        append_trial(root, arm, index, case, outcome, summary['command_rc'], deployment, attempt / 'summary.json', summary['run_id'])
        summaries.append(summary)
        print(json.dumps(dict(arm=arm, attempt=index, case=case, outcome=outcome, harness_error=harness,
                              fast_selected=(audit or {}).get('fast_selected'))), flush=True)
        if harness:
            stop_reason = harness
            break
        if new_call_upper_bound(registration_budget, budget_after) >= 250000:
            stop_reason = 'additional paid upper-bound stop threshold reached'
            break
    verify_deployment(deployment)
    for name in ('fleet.log', 'moveit.log', 'move_to_pose.log', 'gazebo.log'):
        path = runtime / name
        if path.exists():
            shutil.copyfile(path, arm_dir / name)
    status = dict(arm=arm, completed_attempts=len(summaries), scheduled_attempts=3,
                  outcomes=dict(Counter(s['outcome'] for s in summaries)), stop_reason=stop_reason,
                  task_specific_code_added=0, task_specific_code_deleted=0,
                  per_arm_source_config_changes=0,
                  shared_new_initial_configuration=dict(layouts=2, object_poses=4, numeric_components=12),
                  common_harness_authoring_cost='NOT_RUN; not timed before sealed registration',
                  unchanged_skill_sources=True, human_minutes='NOT_RUN', qualification='NOT_RUN',
                  additional_paid_upper_bound_microyuan=new_call_upper_bound(registration_budget, budget_snapshot()),
                  final_budget=budget_snapshot(), runtime=str(runtime))
    write(arm_dir / 'status.json', status)
    COST.append(root / 'cost.jsonl', dict(event_id=arm+'-stop', kind='effort_stop', arm=arm,
                session_id=session, clock_id=COST.clock_id(), end_ns=time.perf_counter_ns(),
                evidence=[COST.pin(arm_dir / 'status.json')]))
    write(arm_dir / 'cost_report.json', COST.summarize(COST.read_ledger(root / 'cost.jsonl')))
    return 1 if stop_reason else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prepare = sub.add_parser('register')
    prepare.add_argument('--deployment', type=Path, required=True)
    prepare.add_argument('--revision', required=True)
    run = sub.add_parser('run-arm')
    run.add_argument('--arm', choices=('fsm', 'hybrid'), required=True)
    for command in (prepare, run):
        command.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'register':
        register(args.root, args.deployment, args.revision)
        return 0
    return run_arm(args.root, args.arm)


if __name__ == '__main__':
    sys.exit(main())
