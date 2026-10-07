"""Actual ROS adapter; imported only for explicit bounded execution."""
import json
import os
from pathlib import Path
import shutil
import sys

import qualification_prepare as q
import bounded_runner as runner
import t1_pilot as base
import t3_swap_pilot as old


def result_json(stdout):
    marker = 'RESULT '
    q.require(stdout.count(marker) == 1, 'exactly one native client result required')
    value = q.loads(stdout.split(marker, 1)[1])
    q.require(type(value) is dict and type(value.get('action_status')) is int
              and value['action_status'] in (4, 5, 6) and type(value.get('outcome_val')) is int,
              'typed terminal action status required')
    return value


def command_ok(value):
    return type(value.get('return_code')) is int and value['return_code'] == 0


def uncertain(value):
    return value.get('return_code') is None or base.signal_return_code(value.get('return_code'))


def transport_unknown(raw):
    for p in raw.glob('*transport.jsonl'):
        for line in p.read_text().splitlines():
            if not line.strip(): continue
            event = q.loads(line).get('event', '')
            if 'quarantin' in str(event) or event in ('goal_send_timeout', 'goal_response_unknown', 'goal_response_error'):
                return True
    return False


class LiveBackend:
    def __init__(self, workspace):
        q.require(workspace.resolve() == Path('/home/ros/agentic_workcell_ws'), 'actual execution requires WSL authority')
        self.workspace = workspace
        self.readiness = base.module('bounded_readiness', workspace / 'setup/131_prebatch_readiness.py')
        self.composite = base.module('bounded_composite_audit', workspace / 'setup/127_composite_audit.py')
        self.root = None

    def budget(self, plan):
        path = Path(os.environ['FLEXCELL_LLM_BUDGET_FILE'])
        q.require(str(path.resolve()) == plan['budget_path'], 'budget path changed')
        value = q.loads(path.read_bytes()); snapshot = q.budget_snapshot(path.read_bytes())
        old_ids = set(plan['registration_budget']['existing_call_ids'])
        q.require(old_ids.issubset(snapshot['existing_call_ids']), 'existing budget calls removed or reset')
        added = sum(c.get('settled_microyuan', c['reserved_microyuan']) for c in value['calls'] if c['id'] not in old_ids)
        q.require(added < 250000, 'cumulative new paid upper-bound stop threshold reached')
        return value

    def current(self):
        values = sorted(base.RUNTIME.glob('*/deployment.json'))
        q.require(bool(values), 'no deployed runtime')
        return values[-1]

    def health(self, directory, name, deployment):
        output = directory / (name + '_report.json')
        command = base.command(directory, name, [sys.executable, str(self.workspace / 'setup/131_prebatch_readiness.py'),
            '--live', '--workspace', str(self.workspace), '--deployment', str(deployment), '--out', str(output)], 85)
        q.require(command_ok(command), 'strict read-only health command failed or signaled')
        report = q.loads(output.read_bytes())
        q.require(report.get('read_only_preflight_ok') is True and report.get('ready_for_large_test') is False,
                  'idle, released carry, calibration and policy identity not confirmed')
        return report

    def boundary(self, root, plan, completed):
        self.root = root
        self.budget(plan)
        for rel, pin in plan['history_files'].items():
            p = q.regular(Path(plan['history_path']), rel)
            q.require(q.sha(p) == pin['sha256'] and p.stat().st_size == pin['bytes'], 'prior episode changed')
        folder = root / 'boundaries'; folder.mkdir(exist_ok=True)
        index = len(list(folder.glob('*.json')))
        self.health(folder, 'boundary-%03d' % index, self.current())

    def usage(self, directory, episodes, before, after):
        folder = directory / 'usage'; folder.mkdir()
        prior = {c['id'] for c in before['calls']}
        for call in after['calls']:
            if call['id'] not in prior:
                runner.write(folder / ('slow-' + call['id'] + '.json'),
                    {'record_kind': 'OBSERVED_BUDGET_RECEIPT', 'call': call, 'actual_fee': 'UNKNOWN'})
        for episode in episodes:
            for step in episode['steps']:
                for index, proposal in enumerate((step['policy_output'].get('policy_trace') or {}).get('proposals', [])):
                    if proposal.get('policy') == 'jev' and proposal.get('skipped') is not True:
                        runner.write(folder / ('fast-%s-%s-%s.json' % (episode['run_id'], step['seq'], index)),
                            {'record_kind': 'OBSERVED_POLICY_PROPOSAL', 'run_id': episode['run_id'],
                             'seq': step['seq'], 'proposal': proposal, 'gpu_cost': 'UNKNOWN'})

    def execute(self, directory, job, plan):
        offsets = {p.name:p.stat().st_size for p in base.LOGS.glob('*.jsonl')}
        files = set((base.LOGS / 'episodes').glob('*.json'))
        before = self.budget(plan); runner.write(directory / 'budget_before.json', before)
        episodes, audits, error, outcome, result, client = [], [], None, 'UNKNOWN', None, None
        deployment = None
        try:
            switch = base.command(directory, 'switch', ['bash', str(self.workspace / 'setup/102_mainline_runtime.sh'),
                                                          'switch', job['arm'], '0.85'], 180)
            q.require(command_ok(switch), 'policy activation failed or signaled')
            deployed = self.current(); deployment = q.loads(deployed.read_bytes())
            expected = q.loads((self.root / 'inputs/identity.json').read_bytes())['proposed_runtime_fingerprints'][job['arm']]
            q.require(deployment['runtime_fingerprint'] == expected and deployment['policy'] == job['arm'], 'active fingerprint differs from registered arm')
            shutil.copyfile(deployed, directory / 'deployment.json')
            self.health(directory, 'preflight', deployed)
            reset = base.command(directory, 'reset', [sys.executable, str(self.workspace / 'setup/flexcell_admin.py'), 'reset'], 300)
            q.require(command_ok(reset) and q.loads(reset['stdout']).get('ok') is True, 'reset unconfirmed or signal')
            clear = base.command(directory, 'clear-injection', [sys.executable, str(old.CLIENT), '--action', 'inject', '--inject', '',
                '--inject-request-id', self.root.name + '-' + job['slot_id'], '--expect-inject-state', 'cleared'], 35)
            q.require(command_ok(clear), 'fault injection clear unconfirmed')
            for name, xyz in job['initial_objects'].items():
                pose = base.command(directory, 'pose-' + name, [sys.executable, str(self.workspace / 'setup/transferbench/bounded_pose.py'),
                    '--object', name, '--xyz', *map(str, xyz)], 30)
                q.require(command_ok(pose) and q.loads(pose['stdout']).get('ok') is True, 'placement ack failed or signaled')
            observe = base.command(directory, 'observe-before', [sys.executable, str(old.CLIENT), '--action', 'observe', '--timeout', '35'], 45)
            q.require(command_ok(observe), 'pre-goal observation failed')
            observed = result_json(observe['stdout'])
            q.require(observed['outcome_val'] == 0 and observed['action_status'] == 4
                      and base.same_layout(old.observed_positions(observed), job['initial_objects']), 'fresh registered initial layout not measured')
            request = job['request']
            args = [sys.executable, str(old.CLIENT), '--action', request['action']]
            timeout = 240
            if request['action'] == 'composite':
                runner.write(directory / 'input_plan.json', request['plan'])
                args += ['--plan', str(directory / 'input_plan.json')]; timeout = 420
            else: args += ['--scenario', request['scenario_id']]
            args += ['--timeout', str(timeout)]
            client = base.command(directory, 'client', args, timeout + 30)
            q.require(not uncertain(client), 'native client timeout or signal; ownership unknown')
            result = result_json(client['stdout']); runner.write(directory / 'client_result.json', result)
            episode_dir = directory / 'episodes'; episode_dir.mkdir()
            new = set((base.LOGS / 'episodes').glob('*.json')) - files
            for path in sorted(new):
                episode = q.loads(path.read_bytes())
                final = episode.get('final_state') or {}
                belongs = final.get('parent_run_id') == result.get('run_id') if request['action'] == 'composite' else final.get('goal_uuid') == result.get('goal_uuid')
                q.require(belongs, 'unrelated new episode; concurrent execution detected')
                shutil.copyfile(path, episode_dir / path.name); episodes.append(episode)
            q.require(len(episodes) <= job['native_episode_limit'], 'native quota exceeded')
            if request['action'] == 'composite':
                receipt = Path(result['evidence_id'])
                q.require(receipt.parent.resolve() == (base.LOGS / 'composites').resolve() and receipt.name == result['run_id'] + '.jsonl'
                          and not receipt.is_symlink(), 'parent receipt not owned by this goal')
                shutil.copyfile(receipt, directory / 'parent.jsonl')
                events = [q.loads(line) for line in receipt.read_text().splitlines()]
                q.require(events[0]['goal_uuid'] == result['goal_uuid'] and events[-1]['event'] == 'TERMINAL', 'parent terminal identity unknown')
                q.require(events[-1]['component_run_ids'] == result['component_run_ids']
                          and set(e['run_id'] for e in episodes) == set(result['component_run_ids']), 'component episode identity mismatch')
                passed = result['outcome_val'] == 0 and result['action_status'] == 4
                if passed:
                    audit = self.composite.audit(directory / 'parent.jsonl', episode_dir, deployment)
                    runner.write(directory / 'composite_audit.json', audit)
            else:
                q.require(len(episodes) == 1 and episodes[0]['run_id'] == result['run_id'], 'exactly one native episode required')
                passed = result['action_status'] == 4 and base.success_predicate(episodes[0], result, client['return_code'])
            for episode in episodes:
                q.require(episode['runtime_fingerprint'] == deployment['runtime_fingerprint'], 'episode fingerprint drift')
                if job['arm'] == 'hybrid':
                    from flexcell_skills.contracts.routing_audit import audit_routing_episode
                    audit = audit_routing_episode(episode, deployment)
                    q.require(audit['ok'] is True, 'real hybrid routing audit failed'); audits.append(audit)
                else:
                    from flexcell_skills.contracts.episode import replay_episode
                    from flexcell_skills.decision_policy import FSMPolicy
                    replay = replay_episode(episode, FSMPolicy())
                    q.require(replay and all(row['ok'] is True for row in replay), 'frozen FSM replay failed')
                    audits.append({'ok': True, 'replay_steps': len(replay)})
            q.require(result['action_status'] in (4, 6), 'canceled task stops collection')
            outcome = 'SUCCEEDED' if passed else 'FAILED'
        except Exception as exc:
            error = type(exc).__name__ + ': ' + str(exc)
            outcome = 'UNKNOWN' if client is not None and (uncertain(client) or result is None) else 'HARNESS_ERROR'
            episode_dir = directory / 'episodes'; episode_dir.mkdir(exist_ok=True)
            for path in sorted(set((base.LOGS / 'episodes').glob('*.json')) - files):
                dest = episode_dir / path.name
                if not dest.exists(): shutil.copyfile(path, dest)
                try:
                    episode = q.loads(path.read_bytes())
                    if episode['run_id'] not in {e['run_id'] for e in episodes}: episodes.append(episode)
                except Exception: pass
        after = base.budget_snapshot(); runner.write(directory / 'budget_after.json', after)
        self.usage(directory, episodes, before, after)
        raw = directory / 'raw'; raw.mkdir()
        for path in base.LOGS.glob('*.jsonl'):
            q.require(path.stat().st_size >= offsets.get(path.name, 0), 'live log truncated')
            (raw / path.name).write_bytes(path.read_bytes()[offsets.get(path.name, 0):])
        if transport_unknown(raw): outcome, error = 'UNKNOWN', 'unknown/quarantined transport ownership'
        runner.write(directory / 'audit.json', {'routing_or_replay': audits, 'error': error})
        return {'record_kind': 'ACTUAL_DEVELOPMENT_ATTEMPT', 'outcome': outcome, 'error': error,
                'native_episode_ids': [e['run_id'] for e in episodes], 'client_return_code': client['return_code'] if client else None,
                'runtime_fingerprint': deployment['runtime_fingerprint'] if deployment else None,
                'calibration_sha256': deployment['active_backends']['fast']['calibration_sha256'] if deployment and job['arm'] == 'hybrid' else None,
                'actual_gpu_api_fees': 'UNKNOWN', 'qualification': 'FROZEN', 'stop': outcome in ('UNKNOWN', 'HARNESS_ERROR')}
