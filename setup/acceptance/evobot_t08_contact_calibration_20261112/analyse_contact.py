#!/usr/bin/env python3
"""Inverse contact-height calibration: FIRST-CONTACT z as a function of contact_height_m.

WHY THIS MEASURES CONTACT Z AND NOT DISPLACEMENT
    Round 1 swept commanded height and recorded displacement. That is the wrong output:
    displacement is a consequence, and it is noisy because an edge-on-edge contact is a
    near-degenerate force balance. What the sweep has to establish is WHERE the finger
    touches the block, because that decides whether the push is an edge drag (contact at
    the block top, z = 0.0350) or a face push (contact at block mid-height, z = 0.0175).

    Block geometry, from the task spec and the generated world: 35 mm cube resting on the
    table, so it spans z = 0.0000 .. 0.0350 with its centre at 0.0175.

THE MODEL BEING TESTED
    push.py commands the end effector to travel at constant z = contact_height_m, but
    end_effector_link carries no collision geometry. If the bodies that do collide (the
    finger links) sit at a RIGID offset above that frame, then

        first_contact_z  =  contact_height_m  +  offset      (slope 1.0)

    and the command that puts contact at the block centre is 0.0175 - offset. With
    offset = 0.0149 (measured at command 0.0200) that is 0.0026.
    The competing model is that contact z is CLAMPED at the block top regardless of the
    command, which gives a flat curve and means no number can reach the face.

    The two models are distinguishable by the slope, so the sweep reports the slope.

CONTACT FRAME, VERIFIED NOT ASSUMED
    The Lead's analysis stated as an unproven assumption that the contact point is read in
    the world frame. It is checkable from the data itself: the block's pose z is also in
    each record. If the contact point were in the block's LOCAL frame, a contact on the top
    face would read z = +0.0175 (half-height); in the world frame it reads 0.0350 (block
    top). This script prints both, so the frame claim is settled by the numbers rather than
    inherited.

FIRST CONTACT IS REUSED, NOT RE-DERIVED
    The extraction follows setup/acceptance/evobot_lead_contact_mechanism_20261112/
    contact_first_touch.py: first step containing a gripper-vs-block contact, taking that
    record's contact point and the block pose in the same record.
"""
import glob
import gzip
import json
import os
import sys

BLOCK = 'target_box_a'
HALF = 0.0175          # half of the 35 mm cube
CENTRE_Z = 0.0175      # resting on the table
TOP_Z = 0.0350


def first_contacts(log_path):
    """Yield every gripper-vs-block contact point, in time order."""
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
                for pos in (c.get('position') or []):
                    yield (int(record.get('sim_ns', 0)),
                           float(pos.get('x', 0.0)),
                           float(pos.get('y', 0.0)),
                           float(pos.get('z', 0.0)),
                           block_pose)


def contact_log(trial_dir):
    for name in ('contact_steps.jsonl.gz', 'contact_steps.jsonl'):
        path = os.path.join(trial_dir, 'logs', name)
        if os.path.exists(path):
            return path
    return None


def analyse(trial_dir, commanded):
    log = contact_log(trial_dir)
    rec_path = os.path.join(trial_dir, 'trial_record.json')
    row = {'trial_dir': trial_dir, 'commanded_height_m': commanded,
           'contact_established': False, 'first_contact_z': None,
           'first_contact_x_offset': None, 'first_contact_sim_s': None,
           'block_z_at_first': None, 'n_contact_points': 0,
           'contact_z_min': None, 'contact_z_max': None,
           'displacement_mm': None, 'displacement_signed_mm': None,
           'cos': None, 'terminal_passed': None, 'passed': None,
           'block_moved_mm': None, 'invalid': None}
    if os.path.exists(rec_path):
        rec = json.load(open(rec_path))
        row['displacement_mm'] = rec.get('displacement_mm')
        row['displacement_signed_mm'] = rec.get('displacement_signed_mm')
        row['cos'] = rec.get('direction_cos')
        row['terminal_passed'] = rec.get('terminal_passed')
        row['passed'] = rec.get('passed')
        row['commanded_height_m'] = rec.get('contact_height_m', commanded)
    invalid_path = os.path.join(trial_dir, 'invalid_infra.txt')
    if os.path.exists(invalid_path):
        row['invalid'] = open(invalid_path).read().strip()
    if log is None:
        return row

    zs = []
    first = None
    for sim_ns, cx, cy, cz, block_pose in first_contacts(log):
        if first is None:
            first = (sim_ns, cx, cy, cz, block_pose)
        zs.append(cz)
    row['n_contact_points'] = len(zs)
    if first is None:
        return row

    sim_ns, cx, cy, cz, block_pose = first
    bx = float(block_pose[0]) if len(block_pose) > 0 else float('nan')
    bz = float(block_pose[2]) if len(block_pose) > 2 else float('nan')
    row.update({
        'contact_established': True,
        'first_contact_z': cz,
        'first_contact_x_offset': cx - bx,
        'first_contact_sim_s': sim_ns / 1e9,
        'block_z_at_first': bz,
        'contact_z_min': min(zs),
        'contact_z_max': max(zs),
    })
    return row


def find_trials(root):
    """Find every trial directory, at any depth.

    The sweep's own layout is <root>/<arm>/t1, but the round-2 evidence layout is
    <root>/<arm>/<seed>/t1. Walking to the trial_record.json is depth-independent, so the
    same analyser can be pointed at either without a special case.
    """
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        if 'trial_record.json' in filenames or os.path.isdir(os.path.join(dirpath, 'logs')):
            if os.path.basename(dirpath).startswith('t'):
                found.append(dirpath)
    return sorted(found)


def commanded_height_for(trial_dir):
    """Read the commanded height from the nearest manifest.txt above the trial."""
    cur = trial_dir
    for _ in range(4):
        cur = os.path.dirname(cur)
        manifest = os.path.join(cur, 'manifest.txt')
        if os.path.exists(manifest):
            for line in open(manifest):
                if line.startswith('contact_height_m '):
                    return float(line.split()[1])
        if os.path.dirname(cur) in (cur, ''):
            break
    return None


def main(argv):
    root = argv[1] if len(argv) > 1 else os.path.dirname(os.path.abspath(__file__)) + '/runs'
    rows = []
    for trial_dir in find_trials(root):
        commanded = commanded_height_for(trial_dir)
        row = analyse(trial_dir, commanded)
        # label: everything between the sweep root and the trial, so nested seeds stay distinct
        rel = os.path.relpath(trial_dir, root)
        row['arm'] = rel[:-len('/t1')] if rel.endswith('/t1') else rel
        rows.append(row)

    rows.sort(key=lambda r: (r['commanded_height_m'] is None, -(r['commanded_height_m'] or 0)))

    print('%-12s %10s %12s %12s %9s %10s %8s %7s' % (
        'arm', 'cmd_h_m', 'first_z_m', 'x_offset_m', 'contact?', 'disp_mm', 'cos', 'passed'))
    print('-' * 88)
    for r in rows:
        print('%-12s %10.4f %12s %12s %9s %10s %8s %7s' % (
            r['arm'],
            r['commanded_height_m'] if r['commanded_height_m'] is not None else float('nan'),
            ('%.4f' % r['first_contact_z']) if r['first_contact_z'] is not None else '-',
            ('%+.4f' % r['first_contact_x_offset']) if r['first_contact_x_offset'] is not None else '-',
            'yes' if r['contact_established'] else 'NO',
            ('%.2f' % r['displacement_mm']) if r['displacement_mm'] is not None else '-',
            ('%.4f' % r['cos']) if r['cos'] is not None else '-',
            r['passed']))

    have = [r for r in rows if r['contact_established'] and r['commanded_height_m'] is not None]
    print()
    if len(have) >= 2:
        # slope of first_contact_z against commanded height, the model discriminator
        n = len(have)
        sx = sum(r['commanded_height_m'] for r in have)
        sy = sum(r['first_contact_z'] for r in have)
        sxx = sum(r['commanded_height_m'] ** 2 for r in have)
        sxy = sum(r['commanded_height_m'] * r['first_contact_z'] for r in have)
        denom = n * sxx - sx * sx
        slope = (n * sxy - sx * sy) / denom if denom else float('nan')
        intercept = (sy - slope * sx) / n
        print('linear fit over %d contacting points: first_z = %.4f * cmd_h + %.4f' % (n, slope, intercept))
        print('  slope 1.0  -> rigid offset; the command reaches the face at cmd_h = %.4f' % (CENTRE_Z - intercept))
        print('  slope 0.0  -> contact clamped at the block top; no command reaches the face')
        offsets = [r['first_contact_z'] - r['commanded_height_m'] for r in have]
        print('  per-point offset (first_z - cmd_h): %s' % ', '.join('%.4f' % o for o in offsets))
        print('  offset spread: %.4f m' % (max(offsets) - min(offsets)))
    no_contact = [r for r in rows if not r['contact_established']]
    print()
    print('points with NO gripper-vs-block contact: %d' % len(no_contact))
    for r in no_contact:
        print('  %-12s cmd_h=%.4f  (a real data point, not discarded)' % (
            r['arm'], r['commanded_height_m'] or float('nan')))
    print()
    print('block centre z = %.4f   block top z = %.4f   face-contact tolerance +/-0.0050' % (
        CENTRE_Z, TOP_Z))
    for r in have:
        d = r['first_contact_z'] - CENTRE_Z
        print('  cmd_h=%.4f -> first_z=%.4f  delta_from_centre=%+.4f  %s' % (
            r['commanded_height_m'], r['first_contact_z'], d,
            'WITHIN 5 mm OF CENTRE' if abs(d) <= 0.005 else 'not face contact'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
