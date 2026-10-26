#!/usr/bin/env python3
"""Gate one Phase-3 segment before the next one is allowed to start. (v2)

v1 is kept as `gate_v1_one_session_per_segment.py`. It required exactly one
carry session per *segment*, which failed A4 although A4's telemetry was
complete: four trials produced four starts, four sessions and four final
summaries. The task book (#50 docs, step 4) asks for "an unambiguous matching
teleport session" per trial, not per segment. The rule below is that reading,
written before B5 ran.

Identity is established by exact equality between the PICK's `carry_offset`
and the carry `start` event's `offset`, not by a time window: the two values are
the same computed vector, so a match is unique and does not depend on clocks.

usage: gate.py <label> <probe.jsonl> <carry.jsonl> <pick.jsonl>
               <first-carry-line> <first-pick-line> <expected-trials>
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
    if len(sys.argv) != 8:
        print(__doc__)
        return 2
    label = sys.argv[1]
    probe = load(sys.argv[2])
    carry = load(sys.argv[3], int(sys.argv[5]))
    picks = load(sys.argv[4], int(sys.argv[6]))
    expected = int(sys.argv[7])

    problems = []
    if len(probe) != expected:
        problems.append('trial count %d != %d' % (len(probe), expected))
    for row in probe:
        if row.get('harness_error'):
            problems.append('trial %s harness_error=%r'
                            % (row.get('trial'), row['harness_error']))
        if 'pick_ok' not in row:
            problems.append('trial %s has no pick_ok' % row.get('trial'))

    summaries = collections.defaultdict(list)
    starts = []
    for c in carry:
        if c.get('event') == 'start':
            starts.append(c)
        elif c.get('event') == 'teleport_loop_summary':
            summaries[c.get('session')].append(c)

    if len(starts) != expected:
        problems.append('%d carry starts for %d trials' % (len(starts), expected))

    by_evidence = {}
    for p in picks:
        if p.get('evidence_id'):
            by_evidence.setdefault(p['evidence_id'], []).append(p)

    joined, sessions = [], set()
    for row in probe:
        ev = row.get('evidence_id')
        cand = by_evidence.get(ev, [])
        if len(cand) != 1:
            problems.append('trial %s: %d pick rows for evidence_id %r'
                            % (row.get('trial'), len(cand), ev))
            continue
        offset = cand[0].get('carry_offset')
        if offset is None:
            problems.append('trial %s: pick row has no carry_offset' % row.get('trial'))
            continue
        hit = [s for s in starts if s.get('offset') == offset]
        if len(hit) != 1:
            problems.append('trial %s: %d carry starts for its offset'
                            % (row.get('trial'), len(hit)))
            continue
        session = hit[0].get('session')
        if session in sessions:
            problems.append('session %r claimed by two trials' % (session,))
        sessions.add(session)
        joined.append((row, hit[0], summaries.get(session, [])))

    for row, start, sums in joined:
        if not sums:
            problems.append('trial %s: session %r has no summary'
                            % (row.get('trial'), start.get('session')))
            continue
        if not any(s.get('final') for s in sums):
            problems.append('trial %s: session %r has no final summary'
                            % (row.get('trial'), start.get('session')))
        for s in sums:
            missing = [f for f in REQUIRED_SUMMARY_FIELDS if f not in s]
            if missing:
                problems.append('trial %s: summary missing %s'
                                % (row.get('trial'), missing))
                break
            if s.get('backend') != 'teleport':
                problems.append('trial %s: summary backend=%r'
                                % (row.get('trial'), s.get('backend')))
                break
        if sums[-1].get('object') != row.get('object_name'):
            problems.append('trial %s: summary object %r != %r'
                            % (row.get('trial'), sums[-1].get('object'),
                               row.get('object_name')))

    print('== gate v2 %s ==' % label)
    print('  trials %d/%d   starts %d   sessions %d   summaries %d'
          % (len(probe), expected, len(starts), len(sessions),
             sum(len(v) for v in summaries.values())))
    for row, start, sums in joined:
        last = sums[-1] if sums else {}
        print('    trial %s  %-13s rise=%+.4f  session=%s  lookups=%s miss=%s '
              'pins=%s/%s/%s final=%s'
              % (row.get('trial'), row.get('object_name'), row.get('rise_m') or 0.0,
                 str(start.get('session'))[:8], last.get('ee_lookup_count'),
                 last.get('ee_missing_count'), last.get('pin_confirmed'),
                 last.get('pin_failed'), last.get('pin_requests'),
                 last.get('final')))
    if problems:
        for p in problems:
            print('  BLOCKER %s' % p)
        print('GATE: FAIL (%s)' % label)
        return 1
    print('GATE: PASS (%s)' % label)
    return 0


if __name__ == '__main__':
    sys.exit(main())
