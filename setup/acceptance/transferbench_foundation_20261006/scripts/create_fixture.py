#!/usr/bin/env python3
"""Exercise only the offline ledger, using clearly marked synthetic receipts."""

import argparse
import json
from pathlib import Path
import subprocess
import sys


def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[4])
    args = parser.parse_args()
    repo = args.repo.resolve()
    root = repo / 'setup/acceptance/transferbench_foundation_20261006/fixture'
    root.mkdir()  # never overwrite an earlier fixture
    cli = repo / 'setup/125_transfer_cost.py'
    ledger_path = root / 'cost.jsonl'
    commands = []
    def run(*argv, expected=0):
        command = [sys.executable, str(cli), *argv, '--ledger', str(ledger_path)]
        result = subprocess.run(command, text=True, capture_output=True)
        commands.append(dict(command=command, return_code=result.returncode,
                             expected_return_code=expected, stdout=result.stdout, stderr=result.stderr))
        # Retain the full command log even if a later exercise fails.
        with (root / 'commands.json').open('w') as stream:
            json.dump(commands, stream, indent=2)
            stream.write('\n')
        if result.returncode != expected:
            raise RuntimeError('unexpected command result: ' + result.stderr)
    plan = json.loads((repo / 'setup/transferbench/pilot_draft_v1.json').read_text())
    plan['record_kind'] = 'SYNTHETIC_TOOL_FIXTURE'
    write(root / 'plan.json', plan)
    run('init', '--spec', str(root / 'plan.json'))
    run('start', '--arm', 'hybrid', '--actor', 'coding_agent', '--session', 'fixture-cli',
        '--activity', 'offline synthetic receipt exercise')
    variants = [('SUCCEEDED', 0, 'a', 'b'), ('FAILED', 0, 'a', 'b'),
                ('HARNESS_ERROR', None, 'a', 'b'), ('SUCCEEDED', -6, 'a', 'b'),
                ('SUCCEEDED', 0, 'c', 'd')]
    for i, (outcome, rc, fp, calibration) in enumerate(variants, 1):
        raw = root / ('trial-%d-raw.json' % i)
        write(raw, dict(record_kind='SYNTHETIC_TOOL_FIXTURE', trial_id='fixture-%d' % i,
                        reported_outcome=outcome, return_code=rc,
                        note='invented test input; no robot episode'))
        event = dict(event_id='trial-%d' % i, kind='trial', arm='hybrid', trial_id='fixture-%d' % i,
                     purpose='adaptation', case_id='T1-layout-01', runtime_fingerprint=fp*64,
                     calibration_sha256=calibration*64, reported_outcome=outcome,
                     return_code=rc, evidence=[str(raw)])
        receipt = root / ('trial-%d-event.json' % i)
        write(receipt, event)
        run('record', '--event', str(receipt))
    for i, amount in enumerate((0.03, None), 1):
        raw = root / ('api-%d-raw.json' % i)
        write(raw, dict(record_kind='SYNTHETIC_TOOL_FIXTURE', request_id='fixture-api-%d' % i,
                        amount=amount, note='invented test input; no paid/model API call'))
        event = dict(event_id='api-%d' % i, kind='api', arm='hybrid', request_id='fixture-api-%d' % i,
                     scope='calibration', input_tokens=100 if i == 1 else None, output_tokens=20,
                     amount=amount, currency='USD', evidence=[str(raw)])
        receipt = root / ('api-%d-event.json' % i)
        write(receipt, event)
        run('record', '--event', str(receipt))
        if i == 1:
            alias = dict(event, event_id='api-alias', request_id='different-request-id')
            write(root / 'api-alias-rejected.json', alias)
            run('record', '--event', str(root / 'api-alias-rejected.json'), expected=2)
    run('stop', '--session', 'fixture-cli', '--evidence', str(root / 'trial-1-raw.json'))
    run('report', '--out', str(root / 'report.json'))
    run('report', '--out', str(root / 'report.json'), expected=2)
    report = json.loads((root / 'report.json').read_text())
    assert report['record_kind'] == 'SYNTHETIC_TOOL_FIXTURE'
    assert report['AC@90']['status'] == 'NOT_RUN'
    assert len(report['trial_cells']) == 2
    assert report['api_usage'][0]['requests'] == 2
    assert report['api_usage'][0]['amount_status'] == 'INCOMPLETE'
    print(json.dumps(dict(record_kind=report['record_kind'], commands=len(commands),
                          expected_rejections=2, trial_cells=2, retained_attempts=5,
                          migration_acceptance='NOT_RUN', robot_invoked=False, model_api_invoked=False)))


if __name__ == '__main__':
    main()
