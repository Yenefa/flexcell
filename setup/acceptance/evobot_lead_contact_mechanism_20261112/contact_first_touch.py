#!/usr/bin/env python3
"""Discriminate the flick mechanism from the FIRST contact, not from the average.

WHY A SECOND ANALYSIS
    The first pass (contact_mechanism.py) averaged contact height over the whole run and found
    no separation between forward and backward trials (2.3 mm, below resolution). That refutes
    the round-1 'top edge' hypothesis but does not explain the flick. Averaging is the wrong
    statistic: a flick is decided at the FIRST contact, and a long dragging contact afterwards
    dominates the mean.

COMPETING MECHANISMS AT FIRST CONTACT
    M1  RIDE-OVER   the finger descends onto the block's TOP and the block is squeezed out
                    between finger and table -> first contact is high (near block top) and
                    the contact point sits well INSIDE the block's footprint
    M2  FACE HIT    the finger meets the block's far (+x) FACE -> first contact is mid-height
                    and the contact x sits at the block's +x face, i.e. offset ~ +half-width
    M3  NEAR-SIDE   the finger comes down on the near (-x) side of the top and drags it
                    -> contact x offset negative

    These predict different (contact_x - centre_x, contact_z) at the FIRST contact, so one
    table separates them. Uses only the contact log and the block pose already in it.
"""
import glob
import gzip
import json
import os
import sys

BLOCK = 'target_box_a'
HALF = 0.0175


def find_repo_root(start):
    cur = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(cur, 'benchmark', 'tasks')):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            raise SystemExit('REFUSED: repo root not found above %s' % start)
        cur = parent


REPO = find_repo_root(os.path.dirname(os.path.abspath(__file__)))
EVID = os.path.join(REPO, 'setup', 'acceptance', 'evobot_t08_evidence_loop_20261112', 'evidence')


def first_contacts(log_path):
    """Yield steps that contain a gripper-vs-block contact."""
    opener = gzip.open if log_path.endswith('.gz') else open
    with opener(log_path, 'rt') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            target = (record.get('targets') or {}).get(BLOCK) or {}
            block_pose = target.get('pose') or []
            for c in ((target.get('contacts') or {}).get('contact') or []):
                n1 = ((c.get('collision1') or {}).get('name') or '')
                n2 = ((c.get('collision2') or {}).get('name') or '')
                if 'gripper' not in n1 and 'gripper' not in n2:
                    continue
                for i, pos in enumerate(c.get('position') or []):
                    yield (int(record.get('sim_ns', 0)), float(pos.get('x', 0.0)),
                           float(pos.get('z', 0.0)), block_pose, i)


def analyse(trial_dir):
    log = os.path.join(trial_dir, 'logs', 'contact_steps.jsonl.gz')
    rec_path = os.path.join(trial_dir, 'trial_record.json')
    if not (os.path.exists(log) and os.path.exists(rec_path)):
        return None
    rec = json.load(open(rec_path))
    it = first_contacts(log)
    try:
        first = next(it)
    except StopIteration:
        return {'arm': os.path.basename(os.path.dirname(trial_dir)),
                'trial': os.path.basename(trial_dir), 'first': None,
                'cos': rec.get('direction_cos')}
    sim_ns, cx, cz, block_pose, _idx = first
    bx = float(block_pose[0]) if len(block_pose) > 0 else float('nan')
    return {
        'arm': os.path.basename(os.path.dirname(trial_dir)),
        'trial': os.path.basename(trial_dir),
        'first_sim_s': sim_ns / 1e9,
        'contact_x_offset': cx - bx,
        'contact_z': cz,
        'block_x_at_first': bx,
        'cos': rec.get('direction_cos'),
        'displacement_mm': rec.get('displacement_mm'),
        'passed': rec.get('passed'),
    }


def main():
    rows = []
    for arm in ('R', 'S'):
        for trial_dir in sorted(glob.glob(os.path.join(EVID, arm, '*'))):
            if os.path.isdir(trial_dir):
                r = analyse(trial_dir)
                if r:
                    rows.append(r)
    have = [r for r in rows if r.get('first_sim_s') is not None]
    if not have:
        raise SystemExit('REFUSED: no first-contact data in any trial')
    print('%-3s %-4s %8s %12s %10s %8s %9s' %
          ('arm', 'tr', 't_s', 'x_offset_m', 'contact_z', 'cos', 'disp_mm'))
    print('-' * 66)
    for r in have:
        print('%-3s %-4s %8.3f %12.4f %10.4f %8.4f %9.2f' % (
            r['arm'], r['trial'], r['first_sim_s'], r['contact_x_offset'],
            r['contact_z'], r['cos'] if r['cos'] is not None else float('nan'),
            r['displacement_mm'] or float('nan')))
    fwd = [r for r in have if (r['cos'] or 0) > 0]
    bwd = [r for r in have if (r['cos'] or 0) < 0]
    print()
    for label, group in (('forward', fwd), ('backward', bwd)):
        if not group:
            print('  %-9s n=0 (no comparison possible)' % label)
            continue
        mx = sum(r['contact_x_offset'] for r in group) / len(group)
        mz = sum(r['contact_z'] for r in group) / len(group)
        mt = sum(r['first_sim_s'] for r in group) / len(group)
        print('  %-9s n=%d  mean x_offset %+.4f m  mean contact_z %.4f m  mean t_first %.2f s'
              % (label, len(group), mx, mz, mt))
    if fwd and bwd:
        dx = (sum(r['contact_x_offset'] for r in bwd) / len(bwd)
              - sum(r['contact_x_offset'] for r in fwd) / len(fwd))
        dz = (sum(r['contact_z'] for r in bwd) / len(bwd)
              - sum(r['contact_z'] for r in fwd) / len(fwd))
        print()
        print('  backward - forward:  dx_offset = %+.4f m   dz = %+.4f m' % (dx, dz))
        print()
        print('  Reading (half-width = %.4f m):' % HALF)
        print('    M1 ride-over   -> |x_offset| small (inside footprint), z high')
        print('    M2 far-face    -> x_offset near +%.4f, z mid' % HALF)
        print('    M3 near-side   -> x_offset negative')
        verdict = []
        if abs(dx) > 0.008:
            verdict.append('the two classes differ in WHERE the first contact lands (%.1f mm)' % (dx * 1000))
        else:
            verdict.append('first-contact x does NOT differ by more than 8 mm between classes')
        if abs(dz) > 0.008:
            verdict.append('they differ in contact HEIGHT (%.1f mm)' % (dz * 1000))
        else:
            verdict.append('they do NOT differ in contact height')
        for v in verdict:
            print('  -> ' + v)
        print()
        print('  If neither differs, the flick is NOT determined by the first contact geometry,')
        print('  and the honest state is UNKNOWN with contact geometry excluded as the cause.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
