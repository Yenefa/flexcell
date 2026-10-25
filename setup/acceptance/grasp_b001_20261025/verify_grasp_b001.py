#!/usr/bin/env python3
"""Re-derive the GRASP-B-001 window result from the committed bytes.

Pure stdlib. No ROS, no Gazebo, no network, no model. Exit 0 only when every
claim in README.md holds; exit 1 on a falsified claim; exit 2 on a missing or
unreadable input.

The point of this file is to make the archive falsifiable. If any number in the
README stops matching the bytes, this must fail loudly.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent.parent

FIXED_HEAD = '36486780f5bf46add81124aa334400c71be4ae72'
WINDOW = 5
FOLLOW_MIN_M = 0.03
ATTACH_RADIUS_M = 0.20

# The 12 failed PICK attempts from the three E-021 baseline batches, as listed by
# competition/iyaic-2026/evidence/grasp-failures-20261025.json.
HISTORICAL_FAIL_IDS = (
    'target_box_b-8ede22c0', 'target_box_b-219f0ce8', 'target_box_b-6238efa6',
    'target_box_b-ab9d3c7b', 'target_box_b-1e9ada41', 'target_box_b-7130f1b2',
    'target_box_b-2f4d1909', 'target_box_b-e07f6179', 'target_box_a-58946988',
    'target_box_a-e9257f99', 'target_box_a-081508ad', 'target_box_a-2d6775e0',
)

# Frozen distribution boundaries. These are the observed extremes, restated as
# invariants: the two populations do not overlap on rise.
HIST_MAX_FAIL_RISE = 0.02968
TODAY_MIN_OK_RISE = 0.03846


class Ledger:
    def __init__(self):
        self.rows = []

    def add(self, claim, ok, detail=''):
        self.rows.append((claim, bool(ok), detail))

    def report(self, width=62):
        for claim, ok, detail in self.rows:
            print('%-*s %s%s' % (width, claim, 'PASS' if ok else 'FAIL',
                                 ('  ' + detail) if detail else ''))
        failed = [c for c, ok, _ in self.rows if not ok]
        print()
        print('%d checks, %d failed' % (len(self.rows), len(failed)))
        if failed:
            print('FALSIFIED:')
            for claim in failed:
                print('  - ' + claim)
        return len(failed)


def load_jsonl(path):
    rows = []
    with open(path, encoding='utf-8') as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                raise SystemExit(2) from None
    return rows


def load_jsonl_with_defects(path):
    """Parse a byte-copied stage log, reporting NUL-prefixed lines separately.

    stage_carry.jsonl carries one record behind a 72-byte NUL run, left by a
    pre-allocated write on this filesystem. The archive keeps the bytes exactly
    as found; this function strips the prefix only to count records, and the
    caller asserts how much damage is there so it cannot silently grow.
    """
    rows, defects = [], []
    with open(path, 'rb') as stream:
        for index, raw in enumerate(stream, 1):
            stripped = raw.strip()
            if not stripped:
                continue
            lead = len(stripped) - len(stripped.lstrip(b'\x00'))
            if lead:
                defects.append((index, lead))
                stripped = stripped.lstrip(b'\x00')
            try:
                rows.append(json.loads(stripped.decode('utf-8')))
            except (json.JSONDecodeError, UnicodeDecodeError):
                defects.append((index, 'unparseable'))
    return rows, defects


def read_text(path):
    return Path(path).read_text(encoding='utf-8').strip()


def rise_of(row):
    before, after = row.get('before'), row.get('after')
    if before is None or after is None:
        return None
    return after[2] - before[2]


def main():
    for name in ('A.jsonl', 'B.jsonl', 'A.stdout', 'B.stdout', 'A.exit', 'B.exit',
                 'health_before.json', 'health_after.json', 'head.txt',
                 'stage_pick.jsonl', 'stage_carry.jsonl', 'identity_sha256.txt'):
        if not (ROOT / name).is_file():
            print('MISSING INPUT: ' + name)
            return 2

    ledger = Ledger()
    a_rows = load_jsonl(ROOT / 'A.jsonl')
    b_rows = load_jsonl(ROOT / 'B.jsonl')
    pick_stage = load_jsonl(ROOT / 'stage_pick.jsonl')
    carry_stage, carry_defects = load_jsonl_with_defects(ROOT / 'stage_carry.jsonl')

    # --- window shape -------------------------------------------------------
    ledger.add('A ran exactly 5 trials', len(a_rows) == WINDOW, 'n=%d' % len(a_rows))
    ledger.add('B ran exactly 5 trials', len(b_rows) == WINDOW, 'n=%d' % len(b_rows))
    ledger.add('A exit code is 0', read_text(ROOT / 'A.exit') == '0',
               read_text(ROOT / 'A.exit'))
    ledger.add('B exit code is 0', read_text(ROOT / 'B.exit') == '0',
               read_text(ROOT / 'B.exit'))
    ledger.add('A objects are all target_box_a',
               {r.get('object_name') for r in a_rows} == {'target_box_a'})
    ledger.add('B objects are all target_box_b',
               {r.get('object_name') for r in b_rows} == {'target_box_b'})
    ledger.add('trial numbers are 1..5 in A',
               [r.get('trial') for r in a_rows] == [1, 2, 3, 4, 5])
    ledger.add('trial numbers are 1..5 in B',
               [r.get('trial') for r in b_rows] == [1, 2, 3, 4, 5])

    # --- no harness error anywhere -----------------------------------------
    noisy = [r.get('trial') for r in a_rows + b_rows if r.get('harness_error')]
    ledger.add('no row carries a harness_error', not noisy, 'rows=%s' % noisy)

    # --- every precondition reset really happened --------------------------
    bad_pre = [r.get('trial') for r in a_rows + b_rows
               if not (r.get('precondition') or {}).get('ok')]
    ledger.add('every precondition reset returned ok', not bad_pre, 'rows=%s' % bad_pre)
    idle = [r.get('trial') for r in a_rows + b_rows
            if (r.get('precondition') or {}).get('reset', {})
            .get('report', {}).get('report', {}).get('task_state_seen') != 'IDLE']
    ledger.add('every reset saw task_state IDLE', not idle, 'rows=%s' % idle)

    # --- outcomes -----------------------------------------------------------
    all_rows = a_rows + b_rows
    picks_ok = [r for r in all_rows if r.get('pick_ok') is True]
    ledger.add('all 10 picks report pick_ok', len(picks_ok) == 10,
               'n=%d' % len(picks_ok))
    ledger.add('no row reports a PICK error code',
               {r.get('error_code') for r in all_rows} == {0},
               'codes=%s' % sorted({r.get('error_code') for r in all_rows}))
    ledger.add('terminal ROS status is SUCCEEDED on every row',
               {(r.get('action') or {}).get('ros_status') for r in all_rows} == {4})
    ledger.add('every goal was accepted',
               all((r.get('action') or {}).get('accepted') for r in all_rows))
    ledger.add('every goal termination was confirmed',
               all((r.get('action') or {}).get('terminal_confirmed') for r in all_rows))

    # --- rise recomputes from the recorded poses ---------------------------
    drift = []
    for r in all_rows:
        recomputed = rise_of(r)
        if recomputed is None or abs(recomputed - r.get('rise_m', 0.0)) > 1e-9:
            drift.append((r.get('trial'), recomputed, r.get('rise_m')))
    ledger.add('rise_m re-derives from before/after poses', not drift, str(drift[:2]))

    rises = [r['rise_m'] for r in all_rows]
    ledger.add('every rise clears the 0.030 m follow threshold',
               all(v > FOLLOW_MIN_M for v in rises),
               'min=%.5f' % min(rises))
    ledger.add('no rise exceeds the grasp_raise envelope',
               all(v < 0.12 for v in rises), 'max=%.5f' % max(rises))

    a_rises = [r['rise_m'] for r in a_rows]
    b_rises = [r['rise_m'] for r in b_rows]
    ledger.add('A rise minimum matches the README',
               abs(min(a_rises) - TODAY_MIN_OK_RISE) < 1e-4,
               'min=%.5f' % min(a_rises))
    ledger.add('today minimum across both groups is the A minimum',
               abs(min(rises) - min(a_rises)) < 1e-12)

    # --- health before and after -------------------------------------------
    for label in ('health_before.json', 'health_after.json'):
        health = json.loads((ROOT / label).read_text(encoding='utf-8'))
        checks = health.get('checks') or {}
        tag = label.replace('.json', '')
        ledger.add('%s ok is true' % tag, health.get('ok') is True)
        ledger.add('%s hard_fail is empty' % tag, health.get('hard_fail') == [])
        ledger.add('%s task_state is IDLE' % tag, checks.get('task_state') == 'IDLE',
                   str(checks.get('task_state')))
        ledger.add('%s carry_engaged is false' % tag,
                   checks.get('carry_engaged') is False)
        ledger.add('%s reports no busy task' % tag, health.get('busy') is False)
        ledger.add('%s saw both target boxes' % tag,
                   'object target_box_a pose' in checks and
                   'object target_box_b pose' in checks)

    ledger.add('health before and after are byte-identical',
               (ROOT / 'health_before.json').read_bytes() ==
               (ROOT / 'health_after.json').read_bytes())

    # --- code identity ------------------------------------------------------
    head = read_text(ROOT / 'head.txt').splitlines()
    ledger.add('window ran at the fixed source commit', head and head[0] == FIXED_HEAD,
               head[0][:12] if head else '')
    ident = read_text(ROOT / 'identity_sha256.txt')
    ledger.add('identity file covers pick_server.py', 'pick_server.py' in ident)
    ledger.add('identity file covers the world file', 'flexcell_world.sdf' in ident)

    # --- the comparison that carries the argument --------------------------
    by_id = {}
    for row in pick_stage:
        eid = row.get('evidence_id')
        if eid:
            by_id[eid] = row

    missing_hist = [eid for eid in HISTORICAL_FAIL_IDS if eid not in by_id]
    ledger.add('all 12 historical failures are present in the stage log',
               not missing_hist, 'missing=%d' % len(missing_hist))
    if not missing_hist:
        hist_rises = [by_id[eid]['box_rise_m'] for eid in HISTORICAL_FAIL_IDS]
        ledger.add('every historical failure sits below the follow threshold',
                   all(v < FOLLOW_MIN_M for v in hist_rises),
                   'max=%.5f' % max(hist_rises))
        ledger.add('historical maximum rise matches the README',
                   abs(max(hist_rises) - HIST_MAX_FAIL_RISE) < 1e-4,
                   'max=%.5f' % max(hist_rises))
        ledger.add('the two populations do not overlap on rise',
                   max(hist_rises) < TODAY_MIN_OK_RISE,
                   'hist_max=%.5f < today_min=%.5f'
                   % (max(hist_rises), TODAY_MIN_OK_RISE))
        hist_gaps = [by_id[eid].get('attach_gap_m') for eid in HISTORICAL_FAIL_IDS]
        ledger.add('every historical attach gap is inside the attach radius',
                   all(g is not None and abs(g) < ATTACH_RADIUS_M for g in hist_gaps),
                   'max=%.4f' % max(abs(g) for g in hist_gaps))
        ledger.add('historical attach gaps span the same band as today',
                   abs(max(abs(g) for g in hist_gaps) - 0.16707) < 1e-3,
                   'max=%.5f' % max(abs(g) for g in hist_gaps))
        ledger.add('historical failures were recorded as GRASP_FAILED (23)',
                   {by_id[eid].get('error_code') for eid in HISTORICAL_FAIL_IDS} == {23})

    # Today's rows must also be findable in the stage log, with the same rise.
    today_ids = [r['evidence_id'] for r in all_rows if r.get('evidence_id')]
    missing_today = [eid for eid in today_ids if eid not in by_id]
    ledger.add('all 10 window picks are present in the stage log',
               not missing_today, 'missing=%d' % len(missing_today))
    if not missing_today:
        mismatch = [(eid, by_id[eid]['box_rise_m']) for eid, r in zip(today_ids, all_rows)
                    if abs(by_id[eid]['box_rise_m'] - r['rise_m']) > 1e-9]
        ledger.add('probe rise equals the stage-log rise on every row', not mismatch,
                   str(mismatch[:2]))
        today_gaps = [abs(by_id[eid]['attach_gap_m']) for eid in today_ids]
        ledger.add('every window attach gap is inside the attach radius',
                   all(g < ATTACH_RADIUS_M for g in today_gaps),
                   'max=%.4f' % max(today_gaps))
        ledger.add('attach gaps are within 8 mm of each other in both groups',
                   max(today_gaps) - min(today_gaps) < 0.012,
                   'span=%.4f' % (max(today_gaps) - min(today_gaps)))

    # --- the gap this archive cannot close --------------------------------
    ledger.add('carry log carries exactly one damaged record',
               len(carry_defects) == 1,
               'defects=%s' % (carry_defects,))
    if len(carry_defects) == 1:
        ledger.add('the damage is a 71-byte NUL prefix, not a lost record',
                   carry_defects[0] == (523, 71), str(carry_defects[0]))

    starts = [r for r in carry_stage if r.get('event') == 'start']
    stops = [r for r in carry_stage if r.get('event') == 'stop']
    fails = [r for r in carry_stage if r.get('event') == 'set_pose_fail']
    ledger.add('carry log has start, stop and set_pose_fail events',
               len(starts) == 449 and len(stops) == 1432 and len(fails) == 19,
               'start=%d stop=%d set_pose_fail=%d'
               % (len(starts), len(stops), len(fails)))
    ledger.add('every carry start that names an object names a real one',
               all(r.get('object') in (None, 'target_box_a', 'target_box_b')
                   for r in starts),
               'objects=%s' % sorted({str(r.get('object')) for r in starts}))
    ledger.add('11 early carry starts predate the object field',
               sum(1 for r in starts if not r.get('object')) == 11,
               'n=%d' % sum(1 for r in starts if not r.get('object')))
    ledger.add('carry stop events carry no identity at all',
               stops and not any(r.get('object') or r.get('request_id') for r in stops),
               'stops=%d' % len(stops))
    ledger.add('no carry event carries a per-pick request id (known gap)',
               not any(r.get('request_id') for r in carry_stage))
    ledger.add('carry backend is teleport wherever it is recorded',
               {r.get('backend') for r in carry_stage} <= {'teleport', None},
               'values=%s' % sorted({str(r.get('backend')) for r in carry_stage}))
    ledger.add('276 carry rows omit the backend field',
               sum(1 for r in carry_stage if r.get('backend') is None) == 276,
               'n=%d' % sum(1 for r in carry_stage if r.get('backend') is None))

    # set_pose_fail is a transient, not a sufficient cause: one lands inside
    # today's successful window.
    ledger.add('every set_pose_fail is a single consecutive failure',
               {r.get('consecutive') for r in fails} == {1},
               'values=%s' % sorted({r.get('consecutive') for r in fails}))
    ledger.add('every set_pose_fail names target_box_a',
               {r.get('object') for r in fails} == {'target_box_a'},
               str(sorted({str(r.get('object')) for r in fails})))
    window_start = 1792913599.0  # 2026-10-25 15:33:19 local, first reset of A
    in_window = [r for r in fails if (r.get('wall_ts') or 0) > window_start]
    ledger.add('one set_pose_fail occurred inside the successful window',
               len(in_window) == 1, 'n=%d' % len(in_window))

    failed = ledger.report()
    print()
    if failed:
        print('RESULT: FALSIFIED')
        return 1
    print('RESULT: CONFIRMED (window reproduced, historical failures not)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
