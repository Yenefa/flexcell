"""Durable, once-only development slots. Large qualification stays frozen."""
import fcntl
import json
from pathlib import Path
import shutil

import qualification_prepare as q

EXECUTOR_FILES = ('setup/133_bounded_runner.py', 'setup/transferbench/bounded_runner.py',
                  'setup/transferbench/bounded_live.py', 'setup/131_prebatch_readiness.py',
                  'setup/transferbench/bounded_pose.py',
                  'setup/102_mainline_runtime.sh', 'setup/96_s7_perturb.py',
                  'src/flexcell/flexcell_skills/test/w1_client.py')


def jobs(package, order='paired'):
    q.require(order in ('paired', 'local-first'), 'unsupported development job order')
    cases = q.loads((package / 'cases.json').read_bytes())
    source = q.loads((package / 'regressions.json').read_bytes())[0]
    result = []
    for axis in ('T1', 'T3', 'S1'):
        item = source if axis == 'S1' else next(c for c in cases if c['axis'] == axis)
        for arm in ('fsm', 'hybrid'):
            request = q.loads(q.encoded(item['request']))
            name = 'development_' + item['case_id']
            if request['action'] == 'composite':
                request['plan']['scenario_id'] = name
            else:
                request['scenario_id'] = name
            result.append({'slot': len(result), 'slot_id': '%02d-%s-%s' % (len(result), axis, arm),
                'axis': axis, 'arm': arm, 'case_id': item['case_id'],
                'purpose': 'source_regression' if axis == 'S1' else 'development',
                'initial_objects': item['initial_objects'], 'request': request,
                'native_episode_limit': item['native_episodes_per_task']})
    if order == 'local-first':
        result = [job for arm in ('fsm', 'hybrid') for job in result if job['arm'] == arm]
        for slot, job in enumerate(result):
            job['slot'] = slot
            job['slot_id'] = '%02d-%s-%s' % (slot, job['axis'], job['arm'])
    return result


def preview(package, expected_sha, workspace, order='paired'):
    verified = q.verify(package, expected_sha, workspace=workspace)
    schedule = q.loads((package / 'schedule.json').read_bytes())
    selected = jobs(package, order)
    return {'record_kind': 'BOUNDED_RUNNER_DRY_RUN', 'ok': True,
        'input_package_sha256': verified['package_sha256'],
        'full_schedule_slots': len(schedule), 'full_schedule_sha256': q.digest(schedule),
        'jobs': selected, 'job_order': order, 'logical_task_limit': 6,
        'native_episode_limit': sum(j['native_episode_limit'] for j in selected),
        'model_calls': 0, 'native_episodes_executed': 0,
        'dispatch_authorized': False, 'qualification_sampling_authorized': False,
        'ready_for_large_test': False, 'n_ge_50': 'FROZEN'}


def write(path, value):
    with path.open('xb') as stream:
        stream.write(q.encoded(value)); stream.flush()
        import os
        os.fsync(stream.fileno())


def seal_attempt(directory):
    manifest = {str(p.relative_to(directory)): {'bytes': p.stat().st_size, 'sha256': q.sha(p)}
                for p in sorted(directory.rglob('*')) if p.is_file() and p.name != 'artifact_manifest.json'}
    write(directory / 'artifact_manifest.json', manifest)
    return q.sha(directory / 'artifact_manifest.json')


def verify_attempt(directory, expected):
    q.require(q.sha(q.regular(directory, 'artifact_manifest.json')) == expected, 'attempt seal changed')
    manifest = q.loads((directory / 'artifact_manifest.json').read_bytes())
    actual = {str(p.relative_to(directory)) for p in directory.rglob('*') if p.is_file() and p.name != 'artifact_manifest.json'}
    q.require(actual == set(manifest), 'attempt artifact set changed')
    for rel, pin in manifest.items():
        p = q.regular(directory, rel)
        q.require(type(pin['bytes']) is int and pin['bytes'] == p.stat().st_size and q.sha(p) == pin['sha256'], 'attempt artifact changed')


def append(root, rows, event, **fields):
    payload = {'seq': len(rows), 'previous_sha256': rows[-1]['sha256'] if rows else None,
               'event': event, **fields}
    payload['sha256'] = q.digest(payload)
    with (root / 'events.jsonl').open('ab') as stream:
        raw = json.dumps(payload, sort_keys=True, allow_nan=False).encode() + b'\n'
        stream.write(raw); stream.flush()
        import os
        os.fsync(stream.fileno())
    rows.append(payload)


def predecessor_pin(root, package_sha, workspace):
    """Link a stopped legacy run only when no slot was ever claimed."""
    plan_path = q.regular(root, 'plan.json'); journal_path = q.regular(root, 'events.jsonl')
    plan = q.loads(plan_path.read_bytes()); raw = journal_path.read_bytes()
    q.require(raw.endswith(b'\n'), 'predecessor has an incomplete journal')
    rows = [q.loads(line) for line in raw.splitlines()]
    q.require(len(rows) == 2 and rows[0]['event'] == 'REGISTERED'
              and rows[1]['event'] == 'STOPPED' and type(rows[1]['completed_slots']) is int
              and rows[1]['completed_slots'] == 0, 'predecessor has claimed or completed work')
    for index, row in enumerate(rows):
        q.require(type(row['seq']) is int and row['seq'] == index
                  and row['previous_sha256'] == (rows[0]['sha256'] if index else None)
                  and row['sha256'] == q.digest({k:v for k,v in row.items() if k != 'sha256'}),
                  'predecessor journal chain changed')
    q.require(rows[0]['plan_sha256'] == q.sha(plan_path)
              and plan['input_package_sha256'] == package_sha
              and q.same_typed(plan['jobs'], jobs(root / 'inputs', plan.get('job_order', 'paired'))),
              'predecessor plan or input identity changed')
    q.verify(root / 'inputs', package_sha, workspace=workspace)
    attempts = root / 'attempts'
    q.require(not attempts.exists() or not any(attempts.iterdir()), 'predecessor has attempt evidence')
    return dict(root=str(root.resolve()), plan_sha256=q.sha(plan_path),
                journal_sha256=q.sha(journal_path), input_package_sha256=package_sha,
                native_dispatch_quota_used=0, disposition='RETAINED_ZERO_CLAIM_STOP')


def register(root, package, expected_sha, workspace, history_root, budget_path, revision,
             order='paired', predecessor=None):
    q.require(not root.exists(), 'run root already exists; never replace registered trials')
    report = preview(package, expected_sha, workspace, order)
    q.verify(package, expected_sha, workspace=workspace, history_root=history_root)
    q.sha_value(revision, 40)
    budget_raw = budget_path.read_bytes(); budget = q.budget_snapshot(budget_raw)
    link = predecessor_pin(predecessor, expected_sha, workspace) if predecessor is not None else None
    plan = {'schema_version': 1, 'record_kind': 'REGISTERED_BOUNDED_DEVELOPMENT',
        'input_package_sha256': expected_sha, 'executor_revision': revision,
        'executor_sha256': {rel: q.sha(q.regular(workspace, rel)) for rel in EXECUTOR_FILES},
        'jobs': report['jobs'], 'job_order': order, 'predecessor': link,
        'logical_task_limit': 6, 'native_episode_limit': 10,
        'budget_path': str(budget_path.resolve()), 'registration_budget': budget,
        'history_path': str(history_root.resolve()),
        'history_files': q.history_snapshot(history_root)['files'],
        'qualification_sampling_authorized': False, 'ready_for_large_test': False,
        'n_ge_50': 'FROZEN', 'AC90': 'NOT_RUN',
        'failure_policy': 'retain known target failure; next registered slot requires fresh idle/released/reset; source failure or unknown/signal/quarantine halts; no replacement'}
    root.mkdir(parents=True, exist_ok=False)
    shutil.copytree(package, root / 'inputs')
    (root / 'attempts').mkdir()
    write(root / 'plan.json', plan)
    rows = []; append(root, rows, 'REGISTERED', plan_sha256=q.sha(root / 'plan.json'))
    return status(root, workspace)


def read(root, workspace):
    plan = q.loads(q.regular(root, 'plan.json').read_bytes())
    q.require(type(plan['schema_version']) is int and plan['schema_version'] == 1
              and plan['record_kind'] == 'REGISTERED_BOUNDED_DEVELOPMENT', 'invalid bounded plan')
    q.require(type(plan['logical_task_limit']) is int and plan['logical_task_limit'] == 6
              and type(plan['native_episode_limit']) is int and plan['native_episode_limit'] == 10
              and plan['qualification_sampling_authorized'] is False
              and plan['ready_for_large_test'] is False and plan['n_ge_50'] == 'FROZEN',
              'large collection or coercive quota refused')
    q.verify(root / 'inputs', plan['input_package_sha256'], workspace=workspace)
    q.require(q.same_typed(plan['jobs'], jobs(root / 'inputs', plan.get('job_order', 'paired'))), 'registered job order or input changed')
    if plan.get('predecessor') is not None:
        link = plan['predecessor']
        q.require(q.same_typed(link, predecessor_pin(Path(link['root']), plan['input_package_sha256'], workspace)),
                  'predecessor changed')
    for rel, digest in plan['executor_sha256'].items():
        q.require(q.sha(q.regular(workspace, rel)) == digest, 'executor source drift: ' + rel)
    q.require(set(plan['executor_sha256']) == set(EXECUTOR_FILES), 'executor identity set changed')
    raw = q.regular(root, 'events.jsonl').read_bytes()
    q.require(raw and raw.endswith(b'\n'), 'incomplete journal; unknown tail cannot resume')
    rows = [q.loads(line) for line in raw.splitlines()]
    pending, committed, episode_ids = None, [], []
    for index, row in enumerate(rows):
        body = {k:v for k,v in row.items() if k != 'sha256'}
        q.require(type(row['seq']) is int and row['seq'] == index
                  and row['previous_sha256'] == (rows[index-1]['sha256'] if index else None)
                  and row['sha256'] == q.digest(body), 'journal chain/sequence changed')
        event = row['event']
        if index == 0:
            q.require(event == 'REGISTERED' and row['plan_sha256'] == q.sha(root / 'plan.json'), 'registered plan identity changed')
        elif event == 'CLAIMED':
            q.require(pending is None and len(committed) < 6
                      and type(row['slot']) is int and row['slot'] == len(committed), 'slot already claimed or out of order')
            pending = row['slot']
        elif event == 'COMMITTED':
            q.require(type(row['slot']) is int and row['slot'] == pending
                      and row['outcome'] in ('SUCCEEDED', 'FAILED', 'HARNESS_ERROR', 'UNKNOWN'), 'unclaimed terminal')
            q.require(row['result_sha256'] == q.sha(q.regular(root, 'attempts/' + plan['jobs'][pending]['slot_id'] + '/result.json')),
                      'terminal result drift')
            result = q.loads((root / 'attempts' / plan['jobs'][pending]['slot_id'] / 'result.json').read_bytes())
            verify_attempt(root / 'attempts' / plan['jobs'][pending]['slot_id'], row['artifact_sha256'])
            q.require(row['outcome'] == result['outcome'] and row['native_episode_ids'] == result['native_episode_ids'], 'terminal differs from result')
            ids = row['native_episode_ids']
            q.require(type(ids) is list and len(ids) <= plan['jobs'][pending]['native_episode_limit']
                      and all(type(n) is str and n and n not in episode_ids for n in ids)
                      and len(ids) == len(set(ids)), 'repeated episode or native quota exceeded')
            episode_ids.extend(ids); committed.append(row); pending = None
        elif event in ('PAUSED', 'STOPPED', 'COMPLETE'):
            q.require(pending is None and type(row['completed_slots']) is int and row['completed_slots'] == len(committed), 'control boundary unconfirmed')
            if event == 'COMPLETE': q.require(len(committed) == 6, 'incomplete collection called complete')
        else:
            raise ValueError('unexpected journal event')
        if index and rows[index-1]['event'] in ('STOPPED', 'COMPLETE'):
            raise ValueError('collection continued after stop/completion')
    actual = {p.name for p in (root / 'attempts').iterdir()}
    expected = {plan['jobs'][r['slot']]['slot_id'] for r in committed}
    if pending is not None: expected.add(plan['jobs'][pending]['slot_id'])
    q.require(actual.issubset(expected), 'unregistered attempt directory; unknown tail')
    q.require(len(episode_ids) <= 10, 'total native quota exceeded')
    return plan, rows, pending, committed, episode_ids


def status(root, workspace):
    plan, rows, pending, committed, ids = read(root, workspace)
    state = 'UNKNOWN_TAIL' if pending is not None else rows[-1]['event']
    return {'ok': True, 'record_kind': 'BOUNDED_DEVELOPMENT_STATUS', 'state': state,
        'completed_slots': len(committed), 'native_episode_count': len(ids),
        'native_episode_count_status': 'UNKNOWN_TOTAL' if pending is not None or any(r['outcome'] == 'UNKNOWN' for r in committed) else 'MEASURED_SNAPSHOT',
        'native_dispatch_quota_used': sum(plan['jobs'][r['slot']]['native_episode_limit'] for r in rows if r['event'] == 'CLAIMED'),
        'outcomes': [r['outcome'] for r in committed], 'job_order': plan.get('job_order', 'paired'),
        'pending_jobs': [{'axis': j['axis'], 'arm': j['arm']} for j in plan['jobs'][len(committed):]],
        'resume_allowed': pending is None and state not in ('STOPPED', 'COMPLETE'),
        'development_complete': state == 'COMPLETE',
        'all_trials_succeeded': state == 'COMPLETE' and all(r['outcome'] == 'SUCCEEDED' for r in committed),
        'qualification_sampling_authorized': False, 'ready_for_large_test': False, 'n_ge_50': 'FROZEN', 'AC90': 'NOT_RUN'}


def run(root, workspace, backend, max_slots=6):
    q.require(type(max_slots) is int and 1 <= max_slots <= 6, 'bounded slot count must be 1..6')
    with (root / 'runner.lock').open('a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc: raise ValueError('another runner holds this collection') from exc
        plan, rows, pending, committed, ids = read(root, workspace)
        q.require(pending is None and rows[-1]['event'] not in ('STOPPED', 'COMPLETE'),
                  'unknown, stopped or completed collection cannot resume')
        try: backend.boundary(root, plan, len(committed))
        except Exception as exc:
            append(root, rows, 'STOPPED', completed_slots=len(committed), reason=type(exc).__name__ + ': ' + str(exc))
            return status(root, workspace)
        start = len(committed)
        for slot in range(start, min(6, start + max_slots)):
            job = plan['jobs'][slot]
            try:
                if hasattr(backend, 'dependencies'): backend.dependencies(root, plan, job)
            except Exception as exc:
                append(root, rows, 'STOPPED', completed_slots=len(committed), reason=type(exc).__name__ + ': ' + str(exc))
                break
            append(root, rows, 'CLAIMED', slot=slot)
            directory = root / 'attempts' / job['slot_id']; directory.mkdir(exist_ok=False)
            try:
                result = backend.execute(directory, job, plan)
                q.require(type(result) is dict and result['outcome'] in ('SUCCEEDED', 'FAILED', 'HARNESS_ERROR', 'UNKNOWN'),
                          'backend returned no recognized terminal')
                native = result['native_episode_ids']
                q.require(type(native) is list and len(native) <= job['native_episode_limit'] and len(set(native)) == len(native)
                          and all(type(n) is str and n and n not in ids for n in native), 'episode reused or quota exceeded')
                q.require(result['outcome'] != 'SUCCEEDED' or len(native) == job['native_episode_limit'], 'success without all native episodes')
                if result['outcome'] == 'SUCCEEDED':
                    rc = result.get('client_return_code')
                    q.require(type(rc) is int and rc >= 0 and not 128 < rc <= 192,
                              'signal or unconfirmed process cannot be success')
            except Exception as exc:
                observed = []
                for p in (directory / 'episodes').glob('*.json'):
                    try:
                        value = q.loads(p.read_bytes()).get('run_id')
                        if type(value) is str and value not in observed: observed.append(value)
                    except Exception: pass
                result = {'outcome': 'UNKNOWN', 'native_episode_ids': observed,
                          'error': type(exc).__name__ + ': ' + str(exc), 'stop': True}
            write(directory / 'result.json', result)
            artifact_sha = seal_attempt(directory)
            append(root, rows, 'COMMITTED', slot=slot, outcome=result['outcome'],
                   native_episode_ids=result['native_episode_ids'], result_sha256=q.sha(directory / 'result.json'), artifact_sha256=artifact_sha)
            ids.extend(result['native_episode_ids']); committed.append(rows[-1])
            print(json.dumps({'slot': slot, 'arm': job['arm'], 'axis': job['axis'], 'outcome': result['outcome'], 'native_episode_count': len(ids)}), flush=True)
            stop = (result.get('stop') is True or result['outcome'] in ('UNKNOWN', 'HARNESS_ERROR')
                    or job['purpose'] == 'source_regression' and result['outcome'] != 'SUCCEEDED')
            if stop:
                append(root, rows, 'STOPPED', completed_slots=len(committed), reason=result.get('error', result['outcome']))
                break
            try: backend.boundary(root, plan, len(committed))
            except Exception as exc:
                append(root, rows, 'STOPPED', completed_slots=len(committed), reason=type(exc).__name__ + ': ' + str(exc))
                break
        else:
            append(root, rows, 'COMPLETE' if len(committed) == 6 else 'PAUSED', completed_slots=len(committed))
        return status(root, workspace)
