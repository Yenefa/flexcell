#!/usr/bin/env python3
"""Benchmark metrics report generator (issue #8 / §4.3 + §4.6).

Regenerates EVERY number from the replay store (~/.ros/flexcell/episodes):
no hand-written PASS lines anywhere.  Per scenario cell it reports:

  - task success rate with Wilson 95% CI (metric 1)
  - decision latency p50/p95/p99/max over decide() (metric 3)
  - safety-gate invalid-decisions-per-1000 with the evaluated/rejected base
    (metric 6)
  - replay integrity: FSM records are replayed with FSMPolicy; model replay
    is NOT_RUN until a pinned model backend is supplied

Usage (ROS env sourced):
  python3 setup/95_metrics_report.py [--store DIR] [--batch FILE.jsonl]
      [--out report.md] [--min-cell 50]

--batch restricts the report to one scenario-runner batch summary (the
audit-compliant way to keep benchmark numbers from mixing with dev-iteration
runs).  Without it, ALL episodes in the store are reported, grouped by
scenario id, with dev scenarios labelled as such.

Exit 0 = report PASS for replay integrity only; model replay is INCOMPLETE.
Sample targets are width warnings, not statistical-power guarantees.
"""
import argparse
import glob
import hashlib
import json
import os
import sys

from flexcell_skills.contracts.episode import replay_episode
from flexcell_skills.contracts.metrics import (
    aggregate_safety, latency_summary, wilson)
from flexcell_skills.decision_policy import FSMPolicy

# canonical scenario-id -> benchmark cell (§4.2).  Anything else is a dev
# iteration and reported separately so it can never pollute a cell.
CELL_OF_SCENARIO = {
    'week1_demo_v1': 'S1',
    'recovery_demo_v1': 'S2',
    'recovery_b_demo_v1': 'S3',
    'exhaust_demo_v1': 'S5',
    # S7 off-canonical placement is a primary-track cell (ratified decision 6),
    # not a dev iteration: it carries the adaptation probe.  Without this the
    # S7 cell silently degrades into a dev/ bucket (2026-09-28).
    's7_perturb_v1': 'S7',
}

POLICY = FSMPolicy()


def cell_of(record):
    scenario = record.get('scenario_id', 'unknown')
    base = record.get('benchmark_cell') or CELL_OF_SCENARIO.get(scenario, 'dev/' + scenario)
    name = record.get('policy', {}).get('name', 'unknown')
    arm = base if name == 'fsm' else base + '/' + name
    protocol = record.get('benchmark_protocol') or {}
    # Unmarked historical records are v1. Even two v2 definitions with different
    # digests must remain separate; never pool merely because the cell matches.
    label = ('%s:%s' % (protocol.get('id', 'unknown'), protocol.get('sha256', 'unknown'))
             if protocol else 'protocol-v1-legacy')
    profile = record.get('runtime_fingerprint') or 'unfingerprinted'
    if record.get('record_kind') == 'MODEL_INPUT_FIXTURE':
        arm = 'dev/MODEL_INPUT_FIXTURE/' + arm
    return arm + ' @ ' + label + ' / runtime=' + profile


def load_episodes(store, batch):
    """Return [(path, record)] - filtered to one batch when given."""
    if batch:
        paths = []
        batch_rows = {}
        with open(batch) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                p = row.get('episode')
                if p:
                    paths.append(p)
                    batch_rows[p] = row
    else:
        paths = sorted(glob.glob(os.path.join(store, '*.json')))
    out = []
    for p in paths:
        try:
            with open(p) as fh:
                rec = json.load(fh)
                if batch:
                    rec['benchmark_cell'] = batch_rows[p]['scenario']
                out.append((p, rec))
        except (OSError, ValueError) as exc:
            print('WARN: unreadable episode %s: %s' % (p, exc), file=sys.stderr)
    return out


def episode_rows(episodes, model_replay=None):
    """Group episodes into cells + compute per-episode facts."""
    cells = {}
    problems = []
    for path, rec in episodes:
        scenario = rec.get('scenario_id', 'unknown')
        cell = cell_of(rec)
        final = rec.get('final_state', {})
        steps = rec.get('steps', [])
        lat = [float(s['decide_latency_ms']) for s in steps
               if s.get('decide_latency_ms') is not None
               and s.get('decide_latency_clock') == 'perf_counter_ns']
        replay_status = 'NOT_RUN'
        try:
            if rec.get('policy', {}).get('name') == 'fsm':
                replayed = replay_episode(rec, POLICY)
                diverged = sum(1 for r in replayed if not r['ok'])
                replayed_n = len(replayed)
                replay_status = 'PASS' if replayed_n > 0 and diverged == 0 else 'FAIL'
            else:
                diverged, replayed_n = 0, 0
                digest = hashlib.sha256(open(path, 'rb').read()).hexdigest()
                result = (model_replay or {}).get(digest)
                if result is not None:
                    replayed = result['steps']
                    identity = rec.get('model_freeze', {}).get('identity')
                    if (not identity or identity != result['freeze_identity']
                            or not result['same_frozen_model']
                            or [r['seq'] for r in replayed] != [r['seq'] for r in steps]):
                        raise ValueError('model replay identity or step sequence mismatch')
                    diverged = sum(not r['ok'] for r in replayed)
                    replayed_n = len(replayed)
                    replay_status = 'PASS' if replayed_n and not diverged else 'FAIL'
        except Exception as exc:  # noqa: BLE001 - report, don't die
            diverged, replayed_n = -1, 0
            problems.append('%s: replay error %r' % (os.path.basename(path), exc))
        if rec.get('EpisodeSchemaVersion') != 1:
            problems.append('%s: unknown EpisodeSchemaVersion'
                            % os.path.basename(path))
        row = {
            'path': os.path.basename(path),
            'scenario': scenario,
            'outcome': str(final.get('outcome')),
            'steps': len(steps),
            'latency_ms': lat,
            'latency_unmeasured': len(steps) - len(lat),
            'safety': final.get('safety'),
            # a planted-proposal episode (safety_rejected>=1) records the
            # PLANTED decision, not a policy output - replay divergence is
            # the signature of the gate working, so these are gate evidence,
            # not policy traces, and stay out of the integrity denominator
            'is_safety_record': isinstance(final.get('safety'), dict)
            and int(final['safety'].get('rejected', 0)) > 0,
            'replay_ok': replay_status == 'PASS',
            'replay_status': replay_status,
            'replayed_n': replayed_n,
            'replay_diverged_steps': max(diverged, 0),
        }
        cells.setdefault(cell, []).append(row)
    return cells, problems


def report(episodes, min_cell, model_replay=None):
    cells, problems = episode_rows(episodes, model_replay)
    lines = ['# FlexCell benchmark metrics report', '',
             'generated from the replay store; every number regenerates - '
             'no hand-written PASS lines.', '']
    total_replay_bad = 0
    total_replay_not_run = 0
    for cell in sorted(cells):
        rows = cells[cell]
        n = len(rows)
        succ = sum(1 for r in rows if r['outcome'] == '0')
        lo, hi = wilson(succ, n)
        lat = latency_summary([v for r in rows for v in r['latency_ms']])
        safety = aggregate_safety([r['safety'] for r in rows
                                   if isinstance(r.get('safety'), dict)])
        replay_bad = sum(1 for r in rows
                         if r['replay_status'] == 'FAIL' and not r['is_safety_record'])
        replay_not_run = sum(r['replay_status'] == 'NOT_RUN' for r in rows)
        total_replay_not_run += replay_not_run
        safety_records = sum(1 for r in rows if r['is_safety_record'])
        total_replay_bad += replay_bad
        width_note = ''
        target = max(min_cell, 100) if cell.split(' @ ')[0].split('/')[0] in ('S2', 'S7') else min_cell
        if n < target:
            width_note = ' ⚠ n<%d (CI wide; prefer n≥%d)' % (target, target)
        lines.append('## Cell %s (n=%d)' % (cell, n))
        lines.append('')
        lines.append('| metric | value |')
        lines.append('| --- | --- |')
        lines.append('| success rate (metric 1) | %d/%d = %.2f, Wilson95 [%.2f, %.2f]%s'
                     % (succ, n, succ / n if n else 0.0, lo, hi, width_note))
        lines.append('| decision latency (metric 3) | %s'
                     % ((str(lat) + ('; %d NOT_RUN legacy/unmeasured decisions' %
                                    sum(r['latency_unmeasured'] for r in rows)
                                    if any(r['latency_unmeasured'] for r in rows) else ''))
                        if lat else 'NOT_RUN (legacy millisecond-truncated or absent timing)'))
        lines.append('| invalid decisions (metric 6) | %s'
                     % safety)
        replay_eligible = [r for r in rows if not r['is_safety_record']
                           and r['replay_status'] != 'NOT_RUN']
        lines.append('| replay integrity | %d/%d replayed episodes clean (%d diverged steps total; %d safety-rejection records excluded)'
                     % (sum(r['replay_ok'] for r in replay_eligible), len(replay_eligible),
                        sum(r['replay_diverged_steps'] for r in replay_eligible),
                        safety_records))
        if replay_not_run:
            lines.append('| model replay | NOT_RUN (%d episodes; pinned backend required) |' % replay_not_run)
        sources = {}
        for _, rec in episodes:
            if cell_of(rec) != cell:
                continue
            for step in rec.get('steps', []):
                trace = (step.get('policy_output') or {}).get('policy_trace') or {}
                source = trace.get('source') or rec.get('policy', {}).get('name', 'unknown')
                sources[source] = sources.get(source, 0) + 1
        lines.append('| actual decision sources | %s |' % sources)
        lines.append('')
        for r in rows:
            if r['is_safety_record']:
                flag = ' **SAFETY-REJECTION RECORD**'
            elif r['replay_status'] == 'NOT_RUN':
                flag = ' **REPLAY NOT_RUN**'
            elif r['replay_ok']:
                flag = ''
            else:
                flag = ' **REPLAY-DIRTY**'
            lines.append('- %s: outcome=%s steps=%d replayed=%d%s'
                         % (r['path'], r['outcome'], r['steps'],
                            r['replayed_n'], flag))
        lines.append('')
    if problems:
        lines.append('## Problems')
        lines.extend('- ' + p for p in problems)
        lines.append('')
    verdict = 'PASS' if total_replay_bad == 0 and not problems else 'FAIL'
    if verdict == 'PASS' and total_replay_not_run:
        verdict = 'INCOMPLETE'
    lines.append('REPORT: %s (%d episodes, %d replay-dirty)'
                 % (verdict, len(episodes), total_replay_bad))
    return '\n'.join(lines), verdict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--store', default=os.path.expanduser(
        '~/.ros/flexcell/episodes'))
    ap.add_argument('--batch', default=None,
                    help='restrict to one scenario-runner batch summary')
    ap.add_argument('--out', default=None, help='write markdown here')
    ap.add_argument('--min-cell', type=int, default=50,
                    help='preferred per-cell n (width warning below it)')
    ap.add_argument('--model-replay-results', help='119_policy_eval same frozen model replay JSON')
    args = ap.parse_args()

    episodes = load_episodes(args.store, args.batch)
    if not episodes:
        print('REPORT: FAIL (no episodes found in %s)' % args.store)
        return 2
    model_replay = {}
    if args.model_replay_results:
        data = json.load(open(args.model_replay_results))
        if data.get('mode') != 'SAME_FROZEN_MODEL_REPLAY':
            raise ValueError('counterfactual evaluation cannot satisfy model replay integrity')
        freeze = dict(data['freeze'])
        identity = freeze.pop('identity')
        if hashlib.sha256(json.dumps(freeze, sort_keys=True).encode()).hexdigest() != identity:
            raise ValueError('invalid frozen backend digest')
        model_replay = {r['episode_sha256']: dict(r, freeze_identity=identity) for r in data['episodes']}
    text, verdict = report(episodes, args.min_cell, model_replay)
    print(text)
    if args.out:
        with open(args.out, 'w') as fh:
            fh.write(text + '\n')
    return 0 if verdict == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
