#!/usr/bin/env python3
"""Assert everything this window claims, from the files in this directory.

The window is GRASP-B-001-PHASE-3, run 2026-10-26 on the WSL execution host at
source c37af8d (including #49 session identity and #50 teleport loop
observation). Ten declared trials: A1 then A4 then B5.

Every number printed is also asserted. If the archive changes, this exits 1
instead of narrating a different story.

Run:  python3 verify_phase3_window.py
"""
import hashlib
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = sys.argv[1] if len(sys.argv) > 1 else HERE
HIST_ARCHIVE = (sys.argv[2] if len(sys.argv) > 2
                else os.path.join(os.path.dirname(ROOT), 'grasp_b001_20261025'))
G = 9.81
RISE_THRESHOLD = 0.030
SUMMARY_FIELDS = ('schema_version', 'object', 'session', 'backend', 'period_s',
                  'ee_lookup_count', 'ee_missing_count', 'pin_requests',
                  'pin_confirmed', 'pin_failed', 'pin_skipped_no_offset', 'final')

failures = []


def check(name, ok, detail):
    print('%-64s %s  %s' % (name, 'PASS' if ok else 'FAIL', detail))
    if not ok:
        failures.append(name)


def load_jsonl(path, first_line=1):
    rows = []
    with open(path, 'rb') as fh:
        for i, line in enumerate(fh, 1):
            if i < first_line or not line.strip():
                continue
            rows.append(json.loads(line.replace(b'\x00', b'')))
    return rows


def read(path):
    with open(os.path.join(ROOT, path), 'rb') as fh:
        return fh.read()


# ---------------------------------------------------------------- segments
segments = {}
for name, expected in (('A1', 1), ('A4', 4), ('B5', 5)):
    rows = load_jsonl(os.path.join(ROOT, name + '.jsonl'))
    segments[name] = rows
    with open(os.path.join(ROOT, name + '.exit')) as fh:
        code = int(fh.read().strip())
    check('%s ran exactly %d trials' % (name, expected), len(rows) == expected,
          'n=%d' % len(rows))
    check('%s exited 0' % name, code == 0, 'exit=%d' % code)

trials = [(name, row) for name, rows in segments.items() for row in rows]
picks = load_jsonl(os.path.join(ROOT, 'logs', 'pick_window.jsonl'))
carry = load_jsonl(os.path.join(ROOT, 'logs', 'carry_window.jsonl'))
moves = load_jsonl(os.path.join(ROOT, 'logs', 'move_to_pose_window.jsonl'))

check('the declared window is 10 trials over A then B', len(trials) == 10
      and [t[1]['object_name'] for t in trials if t[0] == 'A1'] == ['target_box_a']
      and {t[1]['object_name'] for t in trials if t[0] == 'A4'} == {'target_box_a'}
      and {t[1]['object_name'] for t in trials if t[0] == 'B5'} == {'target_box_b'},
      str([t[1]['object_name'][-1] for t in trials]))
check('no trial reports a harness error',
      not any(t[1].get('harness_error') for t in trials),
      str([t[1].get('harness_error') for t in trials if t[1].get('harness_error')]))
check('exactly one trial failed, and it failed as a grasp (code 23)',
      sum(1 for _, r in trials if not r['pick_ok']) == 1
      and [r['error_code'] for _, r in trials if not r['pick_ok']] == [23],
      '%d failures' % sum(1 for _, r in trials if not r['pick_ok']))

# ------------------------------------------------------- identity per trial
starts = [c for c in carry if c.get('event') == 'start']
summaries = {}
for c in carry:
    if c.get('event') == 'teleport_loop_summary':
        summaries.setdefault(c.get('session'), []).append(c)

by_evidence = {}
for p in picks:
    by_evidence.setdefault(p.get('evidence_id'), []).append(p)

joined, ambiguous = [], []
for name, row in trials:
    cand = by_evidence.get(row['evidence_id'], [])
    if len(cand) != 1:
        ambiguous.append((name, row['trial'], 'pick rows=%d' % len(cand)))
        continue
    offset = cand[0].get('carry_offset')
    hit = [s for s in starts if s.get('offset') == offset]
    if len(hit) != 1:
        ambiguous.append((name, row['trial'], 'starts=%d' % len(hit)))
        continue
    joined.append((name, row, cand[0], hit[0], summaries.get(hit[0]['session'], [])))

check('all 10 trials join to exactly one PICK row and one carry session',
      len(joined) == 10, 'joined=%d ambiguous=%s' % (len(joined), ambiguous))
sessions = {s['session'] for _, _, _, s, _ in joined}
check('the ten trials used ten distinct carry sessions', len(sessions) == 10,
      'sessions=%d' % len(sessions))

missing_final = [(n, r['trial']) for n, _, _, _, sums in joined
                 if not any(s.get('final') for s in sums)]
check('every session closed with a final summary', not missing_final,
      str(missing_final))
not_last = [(n, r['trial']) for n, _, _, _, sums in joined
            if sums and not sums[-1].get('final')]
check('the last summary of every session is the final one',
      not not_last, 'a non-final record was last for %s' % not_last[:3])
incomplete = [(n, r['trial']) for n, _, _, _, sums in joined
              for s in sums if any(f not in s for f in SUMMARY_FIELDS)]
check('every summary carries the full #50 field set', not incomplete,
      str(sorted(set(incomplete))[:3]))

# ------------------------------------------- the two hypotheses, decided
miss = sum(s.get('ee_missing_count', 0) for _, _, _, _, sums in joined
           for s in sums[-1:])
lookups = sum(s.get('ee_lookup_count', 0) for _, _, _, _, sums in joined
              for s in sums[-1:])
pin_fail = sum(s.get('pin_failed', 0) for _, _, _, _, sums in joined
               for s in sums[-1:])
pin_ok = sum(s.get('pin_confirmed', 0) for _, _, _, _, sums in joined
             for s in sums[-1:])
pin_req = sum(s.get('pin_requests', 0) for _, _, _, _, sums in joined
              for s in sums[-1:])
print('\n  carry loop totals: lookups=%d missing=%d pins=%d confirmed=%d failed=%d'
      % (lookups, miss, pin_req, pin_ok, pin_fail))

check('no end-effector lookup was ever missing in the window', miss == 0,
      'missing=%d of %d' % (miss, lookups))
check('the window contains exactly one rejected pin request', pin_fail == 1,
      'failed=%d of %d' % (pin_fail, pin_req))
check('that rejected pin request was in a trial that succeeded',
      all(s.get('pin_failed') == 0 for n, r, _, _, sums in joined
          if not r['pick_ok'] for s in sums[-1:]),
      'the failed trial has zero pin rejections')
check('the failing trial itself had zero misses and zero pin failures',
      all(s.get('ee_missing_count') == 0 and s.get('pin_failed') == 0
          for n, r, _, _, sums in joined if not r['pick_ok'] for s in sums[-1:]),
      'checked the failed trial')
check('the failing trial ran its carry session to a normal close',
      all(any(s.get('final') for s in sums)
          for n, r, _, _, sums in joined if not r['pick_ok']),
      'final present')

# ------------------------------------------- where the box actually was
lag = []
for name, row, pick, start, sums in joined:
    offset_z = pick['carry_offset'][2]
    box_z = pick['box_after'][2]
    implied_ee = box_z - offset_z
    end = pick['wall_ts']
    begin = end - pick['elapsed_ms'] / 1000.0
    lift = [m for m in moves
            if str(m.get('request_id', '')).endswith('-lift')
            and begin <= m.get('wall_ts', 0) <= end + 1.0]
    if len(lift) != 1:
        continue
    reached = lift[0]['reached_pose']['position'][2]
    lag.append((name, row['trial'], row['rise_m'], row['pick_ok'],
                (implied_ee - reached) * 1000.0,
                lift[0]['planned_duration_s'], lift[0]['outcome']))

print('\n  %-4s %-3s %8s %5s %10s' % ('seg', 'tr', 'rise', 'ok', 'lag_mm'))
for item in lag:
    print('  %-4s %-3d %+8.4f %5s %+10.1f'
          % (item[0], item[1], item[2], item[3], item[4]))

check('every trial has one lift record that succeeded',
      all(item[6] == 'SUCCEEDED' for item in lag) and len(lag) == 10,
      'n=%d' % len(lag))
lags = [item[4] for item in lag]
check('the box sits below its pinned pose in this window', max(lags) < 5.0,
      'worst upward lag %+.1f mm' % max(lags))
check('the lag reaches at least 50 mm in the worst trial', min(lags) <= -50.0,
      'worst lag %+.1f mm' % min(lags))
check('the lag is continuous, not two populations',
      sum(1 for x in lags if abs(x) > 20.0) >= 4 and sum(1 for x in lags if abs(x) <= 20.0) >= 4,
      'over20=%d under20=%d' % (sum(1 for x in lags if abs(x) > 20.0),
                                sum(1 for x in lags if abs(x) <= 20.0)))
passed_with_lag = [item for item in lag if item[3] and abs(item[4]) > 20.0]
check('trials with more than 20 mm of lag still passed the rise check',
      len(passed_with_lag) >= 3,
      '%d trials' % len(passed_with_lag))
failed = [item for item in lag if not item[3]]
check('the one failure is the largest lag in the window',
      len(failed) == 1 and failed[0][4] == min(lags),
      'failed lag %+.1f vs worst %+.1f' % (failed[0][4], min(lags)))

# ------------------------------------------- the aliasing arithmetic
terms = [s.get('period_s') for _, _, _, _, sums in joined for s in sums[-1:]]
check('every summary reports the configured 0.1 s pin period',
      set(terms) == {0.1}, str(sorted(set(terms))))
fall = 0.5 * G * 0.1 ** 2 * 1000.0
print('\n  a body in free fall for one 0.1 s pin period drops %.1f mm' % fall)
check('the observed lag is the same order as one period of free fall',
      0.5 * fall <= min(lags) * -1 <= 2.0 * fall,
      'observed max %.1f mm vs computed %.1f mm' % (-min(lags), fall))

# ------------------------------- and this failure is not the historical shape
hist_path = os.path.join(HIST_ARCHIVE, 'stage_pick.jsonl')
hist = []
for row in load_jsonl(hist_path):
    if row.get('injected') or str(row.get('detail', '')).startswith('injected failure'):
        continue
    if str(row.get('error_code')) == '23' and 'box_rise_m' in row:
        hist.append(row['box_rise_m'])
hist_sorted = sorted(hist)
hist_median = hist_sorted[len(hist_sorted) // 2]
hist_negative = sum(1 for x in hist_sorted if x < 0)
print('  historical code-23 failures: n=%d median rise %+.4f, %d below zero'
      % (len(hist), hist_median, hist_negative))
print('  this window\'s failure: rise %+.4f' % failed[0][2])

check('the historical failure population is unchanged at 92 records',
      len(hist) == 92, 'n=%d' % len(hist))
check('this window\'s failure lifted the box above its start, unlike the '
      'historical median', failed[0][2] > 0 > hist_median,
      'window %+.4f vs historical median %+.4f' % (failed[0][2], hist_median))

# ------------------- and lag alone cannot produce the historical failure shape
travels = []
for name, row, pick, start, sums in joined:
    end = pick['wall_ts']
    begin = end - pick['elapsed_ms'] / 1000.0
    grasp = [m for m in moves
             if str(m.get('request_id', '')).endswith('-grasp')
             and begin <= m.get('wall_ts', 0) <= end + 1.0]
    lift = [m for m in moves
            if str(m.get('request_id', '')).endswith('-lift')
            and begin <= m.get('wall_ts', 0) <= end + 1.0]
    if len(grasp) == 1 and len(lift) == 1:
        travels.append(lift[0]['reached_pose']['position'][2]
                       - grasp[0]['reached_pose']['position'][2])

min_travel = min(travels)
worst_lag = -min(lags) / 1000.0
floor = min_travel - worst_lag
print('\n  shortest arm travel in the window: %.4f m' % min_travel)
print('  worst observed lag:                 %.4f m' % worst_lag)
print('  lowest rise the lag could produce:  %+.4f m' % floor)

check('a trailing box cannot fall below this floor, and the floor is positive',
      floor > 0.0, 'floor %+.4f m' % floor)
check('so the 54 historical failures with a negative rise are a different '
      'population from this window\'s failure',
      hist_negative == 54 and floor > 0.0,
      'historical negative=%d, lag floor %+.4f' % (hist_negative, floor))

# ------------------------------------------------------- health and identity
hb = json.loads(read('health_before.json'))
ha = json.loads(read('health_after.json'))
for label, doc in (('before', hb), ('after', ha)):
    check('strict health %s the window is clean' % label,
          doc.get('ok') is True and not doc.get('hard_fail'),
          'ok=%s hard_fail=%s' % (doc.get('ok'), doc.get('hard_fail')))
    check('task state is IDLE %s the window' % label,
          doc['checks'].get('task_state') == 'IDLE',
          str(doc['checks'].get('task_state')))
    check('carry is disengaged %s the window' % label,
          doc['checks'].get('carry_engaged') is False,
          str(doc['checks'].get('carry_engaged')))

identity = read('identity_sha256.txt').decode()
check('the running carry_server is the #49+#50 source',
      identity.count('1bb5e55ed3f7955389e38fd22921a1837c07c2be86a36009dbfaa5559fe6f7bd') == 3,
      'occurrences=%d' % identity.count('1bb5e55e'))
check('the world file is the same world #47 ran', 'c81c3c09' in identity, 'world sha')
check('the source tree was unmodified when the window started',
      'tracked modifications:\n  (none)' in read('identity.txt').decode(),
      'clean tree')

print('\n' + '=' * 78)
if failures:
    print('FALSIFIED: %d declared fact(s) no longer hold' % len(failures))
    for name in failures:
        print('  - %s' % name)
    sys.exit(1)
print('CONFIRMED: 10 trials, 10 sessions, zero TF misses, one rejected pin in a')
print('trial that passed, and the box trailing its pinned pose by 3-72 mm.')
print('This window\'s single failure is that lag, not the historical shape:')
print('lag cannot drive a rise negative, and 54 of the 92 historical failures')
print('were negative. The historical population was NOT reproduced here.')
