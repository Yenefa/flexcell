#!/usr/bin/env python3
"""Re-adjudicate issue #22 from committed bytes only.

Issue #22 (posted 2026-10-03) asserted four facts about cells S3/S4.  This
checker re-derives each of them from files that are already in the tree, so the
re-adjudication can be re-run by anyone without ROS, Gazebo, pytest or network.

Exit codes
    0  every claim is re-adjudicated exactly as README.md documents
    1  a claim no longer holds -> the RECORD must be updated, do not silence
       the checker
    2  the evidence archive is missing (wrong --root, or partial checkout)

Nothing is written.  Every assertion below names both the claim it tests and
the file that carries the refutation.
"""
import argparse
import ast
import json
import os
import re
import sys

REL_ARCHIVE = 'setup/acceptance/m3_online_v2_20260930/fsm_s3_s4'
REL_PROTOCOL = ('src/flexcell/flexcell_skills/flexcell_skills/contracts/'
                'benchmark_protocol_v2.json')
REL_SERVER = ('src/flexcell/flexcell_skills/flexcell_skills/'
              'task_fsm_server.py')
REL_ACTION = ('src/flexcell/flexcell_interfaces/action/RunPickPlace.action')
REL_RUNNER = 'setup/94_scenario_runner.py'
REL_REPORT = 'setup/95_metrics_report.py'


def squash(text):
    """Collapse whitespace so a re-indent does not read as a semantic change."""
    return re.sub(r'\s+', ' ', text).strip()


def read_text(root, rel):
    with open(os.path.join(root, rel), encoding='utf-8') as stream:
        return stream.read()


class Ledger(object):
    """Ordered PASS/FAIL rows; failures never abort the run."""

    def __init__(self):
        self.rows = []

    def check(self, claim, ok, evidence, detail=''):
        self.rows.append((claim, bool(ok), evidence, detail))

    def failures(self):
        return [r for r in self.rows if not r[1]]


def function_source(source, name):
    """Return the source segment of every top-level-or-method def `name`."""
    tree = ast.parse(source)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            out.append(ast.get_source_segment(source, node) or '')
    return out


def calls_in(source, needle):
    """True when `needle` (squashed) appears verbatim in squashed source."""
    return squash(needle) in squash(source)


def load_cell_mapping(source):
    """literal_eval the CELL_OF_SCENARIO assignment; never exec the module."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == 'CELL_OF_SCENARIO'
                for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError('CELL_OF_SCENARIO assignment not found in %s' % REL_REPORT)


def episodes_by_scenario(archive):
    found = {}
    eps = os.path.join(archive, 'episodes')
    if not os.path.isdir(eps):
        return found
    for name in sorted(os.listdir(eps)):
        if not name.endswith('.json'):
            continue
        with open(os.path.join(eps, name), encoding='utf-8') as stream:
            record = json.load(stream)
        found.setdefault(record.get('scenario_id'), []).append((name, record))
    return found


def batch_rows(archive):
    path = os.path.join(archive, 'batch_original.jsonl')
    rows = []
    if not os.path.isfile(path):
        return rows
    with open(path, encoding='utf-8') as stream:
        for line in stream:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def adjudicate(root):
    ledger = Ledger()
    archive = os.path.join(root, REL_ARCHIVE)

    # ---- claim C1: S4 records an episode and is on the policy seam ----------
    server = read_text(root, REL_SERVER)
    execute = function_source(server, '_execute')
    execute_plan = function_source(server, '_execute_plan')
    delegates = bool(execute) and all(
        calls_in(body, 'self._execute_plan(goal_handle, single=True)') for body in execute)
    ledger.check(
        'C1a _execute delegates to _execute_plan(single=True)',
        delegates,
        REL_SERVER + ' -> _execute',
        'no delegation call found' if not delegates else '')

    shared = bool(execute_plan) and all(
        calls_in(body, 'EpisodeRecorder(')
        and calls_in(body, 'self._policy.decide(')
        and calls_in(body, 'self._episodes.write(')
        for body in execute_plan)
    ledger.check(
        'C1b _execute_plan owns recorder + decide + episode write',
        shared,
        REL_SERVER + ' -> _execute_plan',
        'shared seam no longer holds all three' if not shared else '')

    by_scenario = episodes_by_scenario(archive)
    s4_eps = by_scenario.get('pick_place_v1') or []
    ok_ep, ep_detail = bool(s4_eps), 'no pick_place_v1 episode in archive'
    if ok_ep:
        name, ep = s4_eps[0]
        steps = ep.get('steps') or []
        ok_ep = (
            len(steps) >= 1
            and all(s.get('policy_input') is not None for s in steps)
            and all(s.get('policy_output') is not None for s in steps)
            and any((s.get('policy_output') or {}).get('action') == 'PLACE'
                    and ((s.get('executor_result') or {}).get('outcome') == 1)
                    for s in steps)
            and (ep.get('final_state') or {}).get('error_code') == 50)
        ep_detail = '' if ok_ep else (
            'episode does not show N policy_input + PLACE failure + error_code 50')
    ledger.check(
        'C1c S4 episode carries per-step policy_input and a real PLACE failure',
        ok_ep, REL_ARCHIVE + '/episodes/*.json', ep_detail)

    # ---- claim C2: S3 exists in SCENARIOS -----------------------------------
    protocol = json.loads(read_text(root, REL_PROTOCOL))
    s3 = (protocol.get('scenarios') or {}).get('S3') or {}
    s3_ok = (s3.get('scenario') == 'recovery_b_demo_v1'
             and ':once' in (s3.get('inject') or '')
             and bool(by_scenario.get('recovery_b_demo_v1')))
    ledger.check(
        'C2a S3 exists and maps to a B-only once injection',
        s3_ok, REL_PROTOCOL + ' -> scenarios.S3',
        '' if s3_ok else 'S3 missing, mis-wired, or has no archived episode')

    s4_spec = (protocol.get('scenarios') or {}).get('S4') or {}
    ledger.check(
        'C2b S4 declares the failure the cell must exercise',
        s4_spec.get('required_failed_action') == 'PLACE'
        and s4_spec.get('expect') == 'FAILED',
        REL_PROTOCOL + ' -> scenarios.S4')

    # ---- claim C3: S4 reports into its own cell and replays clean -----------
    rows = batch_rows(archive)
    s4_rows = [r for r in rows if r.get('scenario') == 'S4']
    s4_row_ok = bool(s4_rows) and all(
        r.get('outcome') == r.get('expected') == 'FAILED'
        and r.get('scenario_exercised') is True
        and r.get('replay_ok') is True
        and r.get('harness_error') is None
        for r in s4_rows)
    ledger.check(
        'C3a runner grades the S4 row as expected + exercised + replay-clean',
        s4_row_ok, REL_ARCHIVE + '/batch_original.jsonl',
        '' if s4_row_ok else 'no S4 row, or its grading changed')

    report = read_text(root, REL_ARCHIVE + '/95_metrics_report.md')
    ledger.check(
        'C3b metrics report emits a Cell S4 section',
        'Cell S4 ' in report and 'REPORT: PASS' in report,
        REL_ARCHIVE + '/95_metrics_report.md')

    # ---- claim C4: the runner already interleaves cells ---------------------
    runner = read_text(root, REL_RUNNER)
    ledger.check(
        'C4 runner schedules cells round-robin, not sequentially',
        calls_in(runner, "'order': 'round_robin'")
        and calls_in(runner,
                     'for i in range(max(n for _, n in plan))'
                     ' for sid, n in plan if i < n'),
        REL_RUNNER + ' -> schedule', 'round-robin schedule not found')

    # ---- the part #22 got right: pick_place_v1 must not be hard-mapped ------
    mapping = load_cell_mapping(read_text(root, REL_REPORT))
    ledger.check(
        'R1 CELL_OF_SCENARIO maps S3 but NOT pick_place_v1 -> S4',
        mapping.get('recovery_b_demo_v1') == 'S3'
        and 'pick_place_v1' not in mapping,
        REL_REPORT + ' -> CELL_OF_SCENARIO',
        'pick_place_v1 became a hard-mapped cell: the reason in R3 no longer holds')

    ledger.check(
        'R2 cell identity for S4 comes from batch metadata',
        calls_in(read_text(root, REL_REPORT),
                 "rec['benchmark_cell'] = batch_rows[p]['scenario']"),
        REL_REPORT + ' -> load_episodes')

    server_single = calls_in(server, "'pick_place_v1' if single else")
    goal_section = read_text(root, REL_ACTION).split('---')[0]
    ledger.check(
        'R3 every single-object run records the same scenario id',
        server_single and 'scenario' not in goal_section,
        REL_SERVER + ' + ' + REL_ACTION,
        'RunPickPlace gained a scenario field: re-adjudicate R1, it may now be mappable')
    return ledger


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    default_root = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', default=default_root,
                    help='repository root (default: three levels above this file)')
    args = ap.parse_args()

    if not os.path.isdir(os.path.join(args.root, REL_ARCHIVE)):
        print('MISSING: %s under %s' % (REL_ARCHIVE, args.root))
        return 2

    ledger = adjudicate(args.root)
    width = max(len(r[0]) for r in ledger.rows)
    for claim, ok, evidence, detail in ledger.rows:
        # the detail string explains the FAILURE mode; printing it on a PASS
        # reads as if the failure had happened
        hint = ('  ' + detail) if (detail and not ok) else ''
        print('%-*s %s  (%s)%s' % (width, claim, 'PASS' if ok else 'FAIL',
                                   evidence, hint))
    failed = ledger.failures()
    print()
    if failed:
        print('ISSUE22 READJUDICATION: STALE (%d claim(s) no longer hold)' % len(failed))
        return 1
    print('ISSUE22 READJUDICATION: CONFIRMED (%d claims)' % len(ledger.rows))
    return 0


if __name__ == '__main__':
    sys.exit(main())
