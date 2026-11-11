#!/usr/bin/env python3
"""Show that one single-step contact invalidates a whole T08 evidence bundle.

Reads the sim lane's R/t4 bundle and runs the real schema.validate(). No simulator.
"""
import json
import os
import sys


def find_repo_root(start):
    cur = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(cur, 'benchmark', 'evidence')):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            raise SystemExit('REFUSED: repo root not found above %s' % start)
        cur = parent


REPO = find_repo_root(os.path.dirname(os.path.abspath(__file__)))
BUNDLE = os.path.join(REPO, 'setup', 'acceptance', 'evobot_t08_evidence_loop_20261112',
                      'evidence', 'R', 't4', 'evidence_bundle.json')
RECORD = os.path.join(os.path.dirname(BUNDLE), 'trial_record.json')


def main():
    if not os.path.exists(BUNDLE):
        raise SystemExit('REFUSED: bundle not found at %s' % BUNDLE)
    sys.path.insert(0, REPO)
    from benchmark.evidence import schema
    bundle = json.load(open(BUNDLE))
    intervals = ((bundle.get('contacts') or {}).get('intervals') or [])
    if not intervals:
        raise SystemExit('REFUSED: bundle has no contact intervals to inspect')
    print('contacts.intervals: %d' % len(intervals))
    zero = 0
    for i, iv in enumerate(intervals):
        if not isinstance(iv, dict):
            continue
        start, end = iv.get('start_sim_ns'), iv.get('end_sim_ns')
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        span = end - start
        mark = '   <== ZERO LENGTH' if span == 0 else ''
        if span == 0:
            zero += 1
        print('  [%2d] start=%d end=%d span=%d ns%s' % (i, start, end, span, mark))
    problems = schema.validate(bundle)
    print()
    print('schema.validate -> %d problem(s)' % len(problems))
    for p in problems:
        print('  %s' % p)
    print()
    if os.path.exists(RECORD):
        rec = json.load(open(RECORD))
        gates = rec.get('failed_gates') or []
        print('trial_record: terminal_passed=%s passed=%s status=%s'
              % (rec.get('terminal_passed'), rec.get('passed'),
                 rec.get('evidence_status')))
        print('failed_gates (%d): %s' % (len(gates), ', '.join(gates)))
        if len(gates) >= 9:
            print('  -> every gate failed at once: the BUNDLE is invalid, not the run')
    print()
    print('zero-length intervals found: %d' % zero)
    if zero == 0:
        raise SystemExit('NOTE: no zero-length interval in this bundle; defect not present here')
    print('=> recorder.contact_intervals() closes an interval at its own first step,')
    print('   so a contact lasting exactly one physics step is emitted as [t, t].')
    print('   schema.py correctly rejects it; the whole bundle then becomes invalid')
    print('   and all nine gates report not-evaluable. On a clean trial this would')
    print('   be recorded as a robot failure. That is the defect.')
    return 0


if __name__ == '__main__':
    sys.exit(main())