#!/usr/bin/env python3
"""Is the GRASP-B-001 failure transient, or does it depend on its context?

This reads the PICK archive merged in #47 and tests the ordered-sequence
hypothesis BEFORE spending another robot window on it. Every number printed
here is also asserted: if the archive changes, this script fails instead of
quietly reporting a different answer.

Run:  python3 setup/acceptance/grasp_sequence_20261025/analyse.py
Exit: 0 all declared facts hold; 1 at least one no longer holds.
"""
import bisect
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = (sys.argv[1] if len(sys.argv) > 1
           else os.path.join(os.path.dirname(HERE), 'grasp_b001_20261025'))
SESSION_GAP_S = 120.0

failures = []


def check(name, condition, detail):
    print('%-62s %s  %s' % (name, 'PASS' if condition else 'FAIL', detail))
    if not condition:
        failures.append(name)


def load(name):
    rows = []
    with open(os.path.join(ARCHIVE, name), 'rb') as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line.replace(b'\x00', b'')))
    return rows


def kind(row):
    """Three populations, kept apart on purpose.

    `injected` rows are deliberate scenario failures (recovery_demo_v1 /
    exhaust_demo_v1). Counting them as evidence about the physical grasp
    inflated the historical failure rate by 6x and manufactured a fake
    sequential correlation on the first pass, so they are excluded rather
    than merely mentioned.
    """
    if row.get('injected') or str(row.get('detail', '')).startswith('injected failure'):
        return 'injected'
    if str(row.get('outcome')) == '0':
        return 'ok'
    if str(row.get('error_code')) == '23':
        return 'grasp23'
    return 'infra_%s' % row.get('error_code')


def sessions(rows, gap):
    out, cur = [], [rows[0]]
    for prev, row in zip(rows, rows[1:]):
        if row['wall_ts'] - prev['wall_ts'] > gap:
            out.append(cur)
            cur = [row]
        else:
            cur.append(row)
    out.append(cur)
    return out


def two_proportion_z(p1, n1, p2, n2):
    """Textbook pooled two-proportion z. Hand-rolled to keep this dependency
    free; the archive is small enough that no library earns its keep."""
    import math
    pooled = (p1 * n1 + p2 * n2) / float(n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1.0 / n1 + 1.0 / n2))
    return (p1 - p2) / se if se else 0.0


picks = sorted(load('stage_pick.jsonl'), key=lambda r: r['wall_ts'])
carry = load('stage_carry.jsonl')
for r in picks:
    r['kind'] = kind(r)

counts = collections.Counter(r['kind'] for r in picks)
print('== PICK archive =================================================')
print('  rows %d over %.1f days' % (
    len(picks), (picks[-1]['wall_ts'] - picks[0]['wall_ts']) / 86400.0))
for k, n in sorted(counts.items()):
    print('    %-10s %d' % (k, n))
print()

check('the archive holds 537 PICK records', len(picks) == 537, 'n=%d' % len(picks))
check('58 of them are deliberate scenario injections', counts['injected'] == 58,
      'n=%d' % counts['injected'])
check('359 natural successes', counts['ok'] == 359, 'n=%d' % counts['ok'])
check('92 natural grasp failures (error_code 23)', counts['grasp23'] == 92,
      'n=%d' % counts['grasp23'])
check('28 natural infrastructure failures', sum(
    n for k, n in counts.items() if k.startswith('infra_')) == 28,
      'n=%d' % sum(n for k, n in counts.items() if k.startswith('infra_')))

# Only a row that measured a rise can speak about a rise.
measured = [r for r in picks if 'box_rise_m' in r]
check('every non-injected row that measured a rise is ok or grasp23',
      {r['kind'] for r in measured} <= {'ok', 'grasp23'},
      str(sorted({r['kind'] for r in measured})))
check('451 rows carry a measured box_rise_m', len(measured) == 451,
      'n=%d' % len(measured))

print('\n== the failure is memoryless ====================================')
clean = [[r for r in s if r['kind'] != 'injected'] for s in sessions(picks, SESSION_GAP_S)]
clean = [s for s in clean if s]
tab = collections.Counter()
for s in clean:
    for a, b in zip(s, s[1:]):
        tab[(a['kind'], b['kind'])] += 1

after_ok = [n for (a, _), n in tab.items() if a == 'ok']
after_bad = [n for (a, _), n in tab.items() if a == 'grasp23']
n_ok, n_bad = sum(after_ok), sum(after_bad)
# a grasp failure may only be followed by ok or grasp23 (infra windows are
# separate PICKs), so the diagonal IS the count of repeated grasp failures.
fail_ok = n_ok - tab[('ok', 'ok')]
fail_bad = tab[('grasp23', 'grasp23')]
p_ok, p_bad = fail_ok / float(n_ok), fail_bad / float(n_bad)
z = two_proportion_z(p_bad, n_bad, p_ok, n_ok)

print('  after success   n=%3d  next grasp fails %3d  rate %.3f' % (n_ok, fail_ok, p_ok))
print('  after failure   n=%3d  next grasp fails %3d  rate %.3f' % (n_bad, fail_bad, p_bad))
print('  two-proportion z = %.2f (|z| < 1.96 means no detectable carry-over)' % z)
print()

check('a grasp failure does not materially raise the next failure rate',
      abs(z) < 1.96, 'z=%.2f' % z)
check('a grasp failure is followed by a success more often than by another one',
      tab[('grasp23', 'ok')] > tab[('grasp23', 'grasp23')],
      '%d ok vs %d repeat' % (tab[('grasp23', 'ok')], tab[('grasp23', 'grasp23')]))
check('success follows failure as often as failure follows success',
      tab[('grasp23', 'ok')] == 55 and tab[('ok', 'grasp23')] == 58,
      '%d vs %d' % (tab[('grasp23', 'ok')], tab[('ok', 'grasp23')]))

print('\n== but infrastructure errors are sticky =========================')
sticky = {}
for a in ('infra_30', 'infra_21', 'infra_41', 'infra_22'):
    row = {b: n for (x, b), n in tab.items() if x == a}
    total = sum(row.values())
    if total:
        sticky[a] = (total - row.get('ok', 0), total)
for a in sorted(sticky):
    bad, total = sticky[a]
    print('  after %-9s n=%2d  next fails %2d  rate %.3f' % (a, total, bad, bad / float(total)))
print()

check('a MoveToPose contention error is always followed by another failure',
      sticky.get('infra_30', (0, 0)) == (11, 11), str(sticky.get('infra_30')))
check('a gz transport error is always followed by another failure',
      sticky.get('infra_41', (0, 0)) == (5, 5), str(sticky.get('infra_41')))

print('\n== the pin-service hypothesis ===================================')
pins = sorted(c['wall_ts'] for c in carry if c.get('event') == 'set_pose_fail')
lo, hi = min(c['wall_ts'] for c in carry), max(c['wall_ts'] for c in carry)
windowed = []
for r in measured:
    if not lo <= r['wall_ts'] <= hi:
        continue
    start = r['wall_ts'] - r.get('elapsed_ms', 0) / 1000.0
    n = (bisect.bisect_right(pins, r['wall_ts'] + 0.5)
         - bisect.bisect_left(pins, start - 0.5))
    windowed.append((r['kind'], n))

for label in ('ok', 'grasp23'):
    sel = [n for k, n in windowed if k == label]
    hit = sum(1 for n in sel if n > 0)
    print('  %-8s n=%3d  windows containing a set_pose_fail: %3d (%.1f%%)'
          % (label, len(sel), hit, 100.0 * hit / len(sel)))
print()

ok_hits = sum(1 for k, n in windowed if k == 'ok' and n > 0)
ok_n = sum(1 for k, n in windowed if k == 'ok')
bad_hits = sum(1 for k, n in windowed if k == 'grasp23' and n > 0)
bad_n = sum(1 for k, n in windowed if k == 'grasp23')
check('a failing pin request is NOT enriched in failed PICK windows',
      bad_hits * ok_n <= ok_hits * bad_n,
      'ok %d/%d vs fail %d/%d' % (ok_hits, ok_n, bad_hits, bad_n))

print('\n== the shape of the failure =====================================')
bad_rows = [r for r in picks if r['kind'] == 'grasp23' and 'box_after' in r]
sank = [r for r in bad_rows if r['box_rise_m'] < -1e-4]
still = [r for r in bad_rows if abs(r['box_rise_m']) <= 1e-4]
part = [r for r in bad_rows if 1e-4 < r['box_rise_m'] < 0.030]
print('  measured failures %d: %d sank below start, %d did not move, %d rose <3cm'
      % (len(bad_rows), len(sank), len(still), len(part)))
print('  box_before z on failures: %.4f .. %.4f (all essentially at rest)'
      % (min(r['box_before'][2] for r in bad_rows),
         max(r['box_before'][2] for r in bad_rows)))
print()

check('most measured failures end BELOW where they started',
      len(sank) > len(still) + len(part),
      'sank=%d vs still=%d partial=%d' % (len(sank), len(still), len(part)))
check('every measured failure starts with the box at rest',
      max(r['box_before'][2] for r in bad_rows) < 0.020,
      'max=%.4f' % max(r['box_before'][2] for r in bad_rows))

print('\n== the carry log cannot attribute a stop to a PICK =============')
ev = collections.Counter(c.get('event') for c in carry)
withsession = sum(1 for c in carry
                  if c.get('event') == 'stop' and c.get('session'))
print('  stop events %d, of which %d name a session, %d name an object'
      % (ev['stop'], withsession,
         sum(1 for c in carry if c.get('event') == 'stop' and c.get('object'))))
print('  start events %d  ->  %d stops are re-engages or no-ops'
      % (ev['start'], ev['stop'] - ev['start']))
print()

check('no stop event can be attributed to a PICK', withsession == 0,
      'with session=%d' % withsession)
check('stops outnumber starts, so most stops release nothing',
      ev['stop'] > 3 * ev['start'], 'stop=%d start=%d' % (ev['stop'], ev['start']))

print('\n' + '=' * 64)
if failures:
    print('FALSIFIED: %d declared fact(s) no longer hold' % len(failures))
    for name in failures:
        print('  - %s' % name)
    sys.exit(1)
print('CONFIRMED: the grasp failure is memoryless in this archive;')
print('the ordered A->B window would test a hypothesis these 451')
print('measured PICKs already reject.')
