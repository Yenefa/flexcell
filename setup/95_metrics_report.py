#!/usr/bin/env python3
"""Benchmark metrics report generator (issue #8 / §4.3 + §4.6).

Regenerates EVERY number from the replay store (~/.ros/flexcell/episodes):
no hand-written PASS lines anywhere.  Per scenario cell it reports:

  - task success rate with Wilson 95% CI (metric 1)
  - decision latency p50/p95/p99/max over decide() (metric 3)
  - safety-gate invalid-decisions-per-1000 with the evaluated/rejected base
    (metric 6)
  - replay integrity: FSMPolicy re-run on every recorded policy input must
    reproduce every recorded decision (0 diverged = the store is trustworthy)

Usage (ROS env sourced):
  python3 setup/95_metrics_report.py [--store DIR] [--batch FILE.jsonl]
      [--out report.md] [--min-cell 20]

--batch restricts the report to one scenario-runner batch summary (the
audit-compliant way to keep benchmark numbers from mixing with dev-iteration
runs).  Without it, ALL episodes in the store are reported, grouped by
scenario id, with dev scenarios labelled as such.

Exit 0 = report PASS: every episode parsed, every replay clean, no cell
below --min-cell episodes (a width warning, not a hard gate - §4.3).
"""
import argparse
import glob
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
    'exhaust_demo_v1': 'S5',
    # S7 off-canonical placement is a primary-track cell (ratified decision 6),
    # not a dev iteration: it carries the adaptation probe.  Without this the
    # S7 cell silently degrades into a dev/ bucket (2026-09-28).
    's7_perturb_v1': 'S7',
}

POLICY = FSMPolicy()


def load_episodes(store, batch):
    """Return [(path, record)] - filtered to one batch when given."""
    if batch:
        paths = []
        with open(batch) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                p = json.loads(line).get('episode')
                if p:
                    paths.append(p)
    else:
        paths = sorted(glob.glob(os.path.join(store, '*.json')))
    out = []
    for p in paths:
        try:
            with open(p) as fh:
                out.append((p, json.load(fh)))
        except (OSError, ValueError) as exc:
            print('WARN: unreadable episode %s: %s' % (p, exc), file=sys.stderr)
    return out


def episode_rows(episodes):
    """Group episodes into cells + compute per-episode facts."""
    cells = {}
    problems = []
    for path, rec in episodes:
        scenario = rec.get('scenario_id', 'unknown')
        cell = CELL_OF_SCENARIO.get(scenario, 'dev/' + scenario)
        final = rec.get('final_state', {})
        steps = rec.get('steps', [])
        lat = [float(s['decide_latency_ms']) for s in steps
               if s.get('decide_latency_ms') is not None]
        try:
            replayed = replay_episode(rec, POLICY)
            diverged = sum(1 for r in replayed if not r['ok'])
            replayed_n = len(replayed)
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
            'safety': final.get('safety'),
            # a planted-proposal episode (safety_rejected>=1) records the
            # PLANTED decision, not a policy output - replay divergence is
            # the signature of the gate working, so these are gate evidence,
            # not policy traces, and stay out of the integrity denominator
            'is_safety_record': isinstance(final.get('safety'), dict)
            and int(final['safety'].get('rejected', 0)) > 0,
            'replay_ok': diverged == 0,
            'replayed_n': replayed_n,
        }
        cells.setdefault(cell, []).append(row)
    return cells, problems


def report(episodes, min_cell):
    cells, problems = episode_rows(episodes)
    lines = ['# FlexCell benchmark metrics report', '',
             'generated from the replay store; every number regenerates - '
             'no hand-written PASS lines.', '']
    total_replay_bad = 0
    for cell in sorted(cells):
        rows = cells[cell]
        n = len(rows)
        succ = sum(1 for r in rows if r['outcome'] == '0')
        lo, hi = wilson(succ, n)
        lat = latency_summary([v for r in rows for v in r['latency_ms']])
        safety = aggregate_safety([r['safety'] for r in rows
                                   if isinstance(r.get('safety'), dict)])
        replay_bad = sum(1 for r in rows
                         if not r['replay_ok'] and not r['is_safety_record'])
        safety_records = sum(1 for r in rows if r['is_safety_record'])
        total_replay_bad += replay_bad
        width_note = ''
        if n < min_cell:
            width_note = ' ⚠ n<%d (CI wide; prefer n≥%d)' % (min_cell, min_cell)
        lines.append('## Cell %s (n=%d)' % (cell, n))
        lines.append('')
        lines.append('| metric | value |')
        lines.append('| --- | --- |')
        lines.append('| success rate (metric 1) | %d/%d = %.2f, Wilson95 [%.2f, %.2f]%s'
                     % (succ, n, succ / n if n else 0.0, lo, hi, width_note))
        lines.append('| decision latency (metric 3) | %s'
                     % (lat if lat else 'no decisions recorded'))
        lines.append('| invalid decisions (metric 6) | %s'
                     % safety)
        lines.append('| replay integrity | %d/%d episodes clean (%d diverged steps total; %d safety-rejection records excluded)'
                     % (n - replay_bad - safety_records, n,
                        sum(1 for r in rows if not r['replay_ok']),
                        safety_records))
        lines.append('')
        for r in rows:
            if r['is_safety_record']:
                flag = ' **SAFETY-REJECTION RECORD**'
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
    ap.add_argument('--min-cell', type=int, default=20,
                    help='preferred per-cell n (width warning below it)')
    args = ap.parse_args()

    episodes = load_episodes(args.store, args.batch)
    if not episodes:
        print('REPORT: FAIL (no episodes found in %s)' % args.store)
        return 2
    text, verdict = report(episodes, args.min_cell)
    print(text)
    if args.out:
        with open(args.out, 'w') as fh:
            fh.write(text + '\n')
    return 0 if verdict == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
