#!/usr/bin/env python3
"""Gate one Phase-3 segment before the next one is allowed to start.

This is the pre-declared rule, not an after-the-fact reading: a segment passes
only if it produced its prescribed trial count, no harness error, and complete
carry telemetry - at least one start and one final summary for a session whose
object matches, with every summary carrying the fields #50 introduced.

usage: gate.py <segment-label> <probe.jsonl> <carry.jsonl> <first-new-carry-line> <expected-trials>
exit:  0 PASS  1 FAIL
"""
import collections
import json
import sys

REQUIRED_SUMMARY_FIELDS = (
    'schema_version', 'object', 'session', 'backend', 'started_mono_ns',
    'sample_mono_ns', 'period_s', 'ee_lookup_count', 'ee_missing_count',
    'ee_missing_streak', 'ee_missing_streak_max', 'ee_lookup_ns_total',
    'ee_lookup_ns_max', 'pin_requests', 'pin_confirmed', 'pin_failed',
    'pin_skipped_no_offset', 'final')


def load(path, first_line=1):
    rows = []
    with open(path, 'rb') as fh:
        for i, line in enumerate(fh, 1):
            if i < first_line or not line.strip():
                continue
            try:
                rows.append(json.loads(line.replace(b'\x00', b'')))
            except ValueError:
                rows.append({'__unparsable_line__': i})
    return rows


def main():
    if len(sys.argv) != 6:
        print(__doc__)
        return 2
    label, probe_path, carry_path, first_line, expected = sys.argv[1:6]
    expected, first_line = int(expected), int(first_line)

    problems = []
    rows = load(probe_path)
    if len(rows) != expected:
        problems.append('trial count %d != %d' % (len(rows), expected))
    for row in rows:
        if row.get('harness_error'):
            problems.append('trial %s harness_error=%r'
                            % (row.get('trial'), row['harness_error']))
        if 'pick_ok' not in row:
            problems.append('trial %s has no pick_ok' % row.get('trial'))
        if row.get('__unparsable_line__'):
            problems.append('unparsable probe line %d' % row['__unparsable_line__'])

    carry = load(carry_path, first_line)
    events = collections.Counter(c.get('event') for c in carry)
    summaries = [c for c in carry if c.get('event') == 'teleport_loop_summary']
    starts = [c for c in carry if c.get('event') == 'start']

    if not starts:
        problems.append('no carry start recorded for this segment')
    if not summaries:
        problems.append('no teleport_loop_summary recorded for this segment')
    if not any(s.get('final') for s in summaries):
        problems.append('no final summary for this segment')
    for s in summaries:
        missing = [f for f in REQUIRED_SUMMARY_FIELDS if f not in s]
        if missing:
            problems.append('summary missing fields %s' % missing)
            break
        if s.get('backend') != 'teleport':
            problems.append('summary backend=%r not teleport' % s.get('backend'))
            break

    objects = {r.get('object_name') for r in rows if r.get('object_name')}
    sessions = {s.get('session') for s in summaries}
    sessions.discard(None)
    sessions.discard('')
    if len(objects) != 1:
        problems.append('segment spans %d objects: %s' % (len(objects), sorted(objects)))
    if len(sessions) != 1:
        problems.append('segment shows %d carry sessions: %s'
                        % (len(sessions), sorted(s[:8] for s in sessions)))
    for st in starts:
        if st.get('session') not in sessions:
            problems.append('start session %r has no summary' % (st.get('session'),))
    unmatched = [s for s in summaries if s.get('object') not in objects]
    if unmatched:
        problems.append('summary object does not match the segment object')

    print('== gate %s ==' % label)
    print('  trials %d/%d   carry events %s' % (len(rows), expected, dict(events)))
    print('  sessions %s   objects %s   summaries %d (final %d)'
          % (sorted(s[:8] for s in sessions), sorted(objects), len(summaries),
             sum(1 for s in summaries if s.get('final'))))
    if problems:
        for p in problems:
            print('  BLOCKER %s' % p)
        print('GATE: FAIL (%s) - the window stops here' % label)
        return 1
    print('GATE: PASS (%s)' % label)
    return 0


if __name__ == '__main__':
    sys.exit(main())
