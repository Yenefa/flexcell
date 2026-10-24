#!/usr/bin/env python3
"""Adversarial self-test for verify_issue22_claims.py.

A checker that cannot fail is not evidence.  Each case below copies the minimum
set of files into a scratch root, applies exactly one tamper, and requires the
checker to notice.  Nothing in the repository is modified.

Run:  python3 selftest_verify_issue22.py
Exit: 0 when every case behaves as declared, 1 otherwise.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
CHECKER = os.path.join(HERE, 'verify_issue22_claims.py')

ARCHIVE_REL = 'setup/acceptance/m3_online_v2_20260930/fsm_s3_s4'
FILES = [
    ARCHIVE_REL,
    'setup/94_scenario_runner.py',
    'setup/95_metrics_report.py',
    'src/flexcell/flexcell_skills/flexcell_skills/task_fsm_server.py',
    'src/flexcell/flexcell_skills/flexcell_skills/contracts/benchmark_protocol_v2.json',
    'src/flexcell/flexcell_interfaces/action/RunPickPlace.action',
]
S4_EPISODE = 'episodes/pick_place_v1_pick_place_v1-16d5aa87.json'
S3_EPISODE = 'episodes/recovery_b_demo_v1_recovery_b_demo_v1-69d7d17f.json'


def build_root():
    root = tempfile.mkdtemp(prefix='issue22-selftest-')
    for rel in FILES:
        src = os.path.join(REPO, rel)
        dst = os.path.join(root, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
    return root


def run(root):
    proc = subprocess.run([sys.executable, CHECKER, '--root', root],
                          capture_output=True, text=True)
    return proc.returncode, (proc.stdout or '') + (proc.stderr or '')


def edit_json(path, mutate):
    with open(path, encoding='utf-8') as stream:
        data = json.load(stream)
    mutate(data)
    with open(path, 'w', encoding='utf-8') as stream:
        json.dump(data, stream)


def edit_text(path, old, new):
    with open(path, encoding='utf-8') as stream:
        text = stream.read()
    if old not in text:
        raise AssertionError('tamper anchor not found in %s: %r' % (path, old))
    with open(path, 'w', encoding='utf-8') as stream:
        stream.write(text.replace(old, new, 1))


def tamper_place_outcome(root):
    """Turn the recorded PLACE failure into a success."""
    def mutate(ep):
        for step in ep['steps']:
            if (step.get('policy_output') or {}).get('action') == 'PLACE':
                step['executor_result']['outcome'] = 0
                return
        raise AssertionError('no PLACE step to tamper')
    edit_json(os.path.join(root, ARCHIVE_REL, S4_EPISODE), mutate)


def tamper_drop_policy_input(root):
    """Drop the recorded policy input of one step (unreplayable episode)."""
    def mutate(ep):
        ep['steps'][0]['policy_input'] = None
    edit_json(os.path.join(root, ARCHIVE_REL, S4_EPISODE), mutate)


def tamper_batch_row(root):
    """Claim the S4 row was exercised when it was not."""
    path = os.path.join(root, ARCHIVE_REL, 'batch_original.jsonl')
    with open(path, encoding='utf-8') as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    for row in rows:
        if row.get('scenario') == 'S4':
            row['scenario_exercised'] = False
    with open(path, 'w', encoding='utf-8') as stream:
        for row in rows:
            stream.write(json.dumps(row) + '\n')


def tamper_protocol_s3(root):
    """Remove S3 from the frozen scenario table."""
    path = os.path.join(root, FILES[4])
    with open(path, encoding='utf-8') as stream:
        spec = json.load(stream)
    spec['scenarios']['S3x'] = spec['scenarios'].pop('S3')
    with open(path, 'w', encoding='utf-8') as stream:
        json.dump(spec, stream)


def tamper_hard_map(root):
    """Do what issue #22 proposed: hard-map pick_place_v1 to S4."""
    edit_text(os.path.join(root, 'setup/95_metrics_report.py'),
              "    's7_perturb_v1': 'S7',",
              "    's7_perturb_v1': 'S7',\n    'pick_place_v1': 'S4',")


def tamper_delete_s3_episode(root):
    os.remove(os.path.join(root, ARCHIVE_REL, S3_EPISODE))


def tamper_goal_gains_scenario(root):
    """Add a scenario field to RunPickPlace.Goal: R1's premise must be re-reviewed."""
    edit_text(os.path.join(root, FILES[5]),
              'string object_name',
              'string object_name\nstring scenario_id')


CASES = [
    ('A  untouched archive verifies', None, 0),
    ('B  PLACE failure flipped to success rejected', tamper_place_outcome, 1),
    ('C  step stripped of policy_input rejected', tamper_drop_policy_input, 1),
    ('D  batch row claiming unexercised S4 rejected', tamper_batch_row, 1),
    ('E  S3 removed from the frozen protocol rejected', tamper_protocol_s3, 1),
    ('F  hard-mapping pick_place_v1 -> S4 rejected', tamper_hard_map, 1),
    ('G  missing S3 episode rejected', tamper_delete_s3_episode, 1),
    ('H  RunPickPlace gaining a scenario field rejected', tamper_goal_gains_scenario, 1),
]


def main():
    failures = 0
    for label, tamper, expect in CASES:
        root = build_root()
        try:
            if tamper:
                tamper(root)
            code, out = run(root)
        finally:
            shutil.rmtree(root, ignore_errors=True)
        ok = code == expect
        if not ok:
            failures += 1
            tail = [line for line in out.strip().split('\n') if line][-3:]
            print('%-52s %s  (expected exit %d, got %d)' % (label, 'FAIL', expect, code))
            for line in tail:
                print('      | ' + line)
        else:
            print('%-52s %s  (exit=%d)' % (label, 'PASS', code))
    print()
    if failures:
        print('SELFTEST: %d of %d cases did not behave as declared' % (failures, len(CASES)))
        return 1
    print('SELFTEST: %d/%d cases behave as declared' % (len(CASES), len(CASES)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
