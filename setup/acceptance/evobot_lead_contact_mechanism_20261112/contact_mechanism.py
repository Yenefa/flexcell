#!/usr/bin/env python3
"""Where does the end effector actually touch the block, and does that predict the flick?

WHY
    The dominant T08 failure is not 'did not push' but 'pushed BACKWARDS': in 4 of 9 valid
    dev trials the direction cosine came out about -1. The stated hypothesis in round 1 was
    'the end effector does not maintain a stable contact face', but that was a description,
    not a measurement, and two competing mechanisms were never separated:

      H_A  the finger contacts the block's TOP EDGE (high z), rides over it and flicks the
           block backwards  ->  contact z should be high, near the block top, and the
           measured contact normal should point downward-ish

      H_B  the finger contacts the FACE at mid height and drives it forward  ->  contact z
           near the block centre, normal horizontal

    These make DIFFERENT predictions about contact z and about the force sign, so one
    measurement separates them. That is what this script does, using the per-step contact
    log already captured by the run -- no simulator, no new run.

SOURCE
    evidence/<arm>/<trial>/logs/contact_steps.jsonl.gz, one record per 5 ms physics step,
    each carrying for every watched model the contact list with position/normal/wrench.
"""
import glob
import gzip
import json
import math
import os
import sys

BLOCK = 'target_box_a'
BLOCK_TOP_Z = 0.035      # 35 mm block resting on the table from z=0
REST_Z = 0.0175


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
ARMS = ['R', 'S']


def gripper_contacts(record):
    """Yield (sim_ns, z, normal_z, force_x_block) for gripper-vs-block contacts in one step."""
    target = (record.get('targets') or {}).get(BLOCK) or {}
    contacts = (target.get('contacts') or {}).get('contact') or []
    out = []
    for c in contacts:
        n1 = ((c.get('collision1') or {}).get('name') or '')
        n2 = ((c.get('collision2') or {}).get('name') or '')
        if 'gripper' not in n1 and 'gripper' not in n2:
            continue
        block_is_1 = n1.startswith(BLOCK)
        positions = c.get('position') or []
        normals = c.get('normal') or []
        wrenches = c.get('wrench') or []
        for i, pos in enumerate(positions):
            z = float(pos.get('z', float('nan')))
            nz = float((normals[i] or {}).get('z', 0.0)) if i < len(normals) else 0.0
            fx = 0.0
            if i < len(wrenches):
                w = wrenches[i] or {}
                body = w.get('body_1_wrench') if block_is_1 else w.get('body_2_wrench')
                fx = float(((body or {}).get('force') or {}).get('x', 0.0))
            out.append((int(record.get('sim_ns', 0)), z, nz, fx))
    return out


def analyse_trial(trial_dir):
    log = os.path.join(trial_dir, 'logs', 'contact_steps.jsonl.gz')
    rec_path = os.path.join(trial_dir, 'trial_record.json')
    if not (os.path.exists(log) and os.path.exists(rec_path)):
        return None
    rec = json.load(open(rec_path))
    samples = []
    opener = gzip.open if log.endswith('.gz') else open
    with opener(log, 'rt') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            samples.extend(gripper_contacts(record))
    if not samples:
        return {'trial': os.path.basename(trial_dir), 'arm': os.path.basename(os.path.dirname(trial_dir)),
                'gripper_contacts': 0, 'cos': rec.get('direction_cos'),
                'displacement_mm': rec.get('displacement_mm'), 'passed': rec.get('passed')}
    zs = [s[1] for s in samples]
    nzs = [s[2] for s in samples]
    fxs = [s[3] for s in samples]
    impulse_x = sum(fxs)
    return {
        'arm': os.path.basename(os.path.dirname(trial_dir)),
        'trial': os.path.basename(trial_dir),
        'gripper_contacts': len(samples),
        'contact_z_min': min(zs),
        'contact_z_max': max(zs),
        'contact_z_mean': sum(zs) / len(zs),
        'normal_z_mean': sum(nzs) / len(nzs),
        'force_x_sum': impulse_x,
        'cos': rec.get('direction_cos'),
        'displacement_mm': rec.get('displacement_mm'),
        'terminal_passed': rec.get('terminal_passed'),
        'passed': rec.get('passed'),
    }


def main():
    rows = []
    for arm in ARMS:
        for trial_dir in sorted(glob.glob(os.path.join(EVID, arm, '*'))):
            if not os.path.isdir(trial_dir):
                continue
            r = analyse_trial(trial_dir)
            if r:
                rows.append(r)
    if not rows:
        raise SystemExit('REFUSED: no trials found under %s' % EVID)
    have = [r for r in rows if r.get('gripper_contacts')]
    if not have:
        raise SystemExit('REFUSED: no gripper-vs-block contacts found in any trial; '
                         'the analysis cannot conclude anything')

    print('%-3s %-4s %-7s %9s %9s %9s %9s %10s %9s' %
          ('arm', 'tr', 'contacts', 'z_min', 'z_max', 'z_mean', 'nz_mean', 'force_x', 'cos'))
    print('-' * 84)
    for r in have:
        print('%-3s %-4s %7d %9.4f %9.4f %9.4f %9.3f %10.4f %9.4f' % (
            r['arm'], r['trial'], r['gripper_contacts'], r['contact_z_min'],
            r['contact_z_max'], r['contact_z_mean'], r['normal_z_mean'],
            r['force_x_sum'], r['cos'] if r['cos'] is not None else float('nan')))

    fwd = [r for r in have if (r['cos'] or 0) > 0]
    bwd = [r for r in have if (r['cos'] or 0) < 0]
    print()
    print('FORWARD (cos > 0): n=%d' % len(fwd))
    print('BACKWARD (cos < 0): n=%d' % len(bwd))
    print()
    for label, group in (('forward', fwd), ('backward', bwd)):
        if not group:
            continue
        zm = sum(r['contact_z_mean'] for r in group) / len(group)
        zx = sum(r['contact_z_max'] for r in group) / len(group)
        nzm = sum(r['normal_z_mean'] for r in group) / len(group)
        print('  %-9s mean contact z %.4f   mean max z %.4f   mean normal_z %+.3f'
              % (label, zm, zx, nzm))
    print()
    print('H_A (top-edge contact) predicts: backward trials have HIGHER contact z and a')
    print('     more negative/downward normal than forward trials.')
    print('H_B (face contact) predicts: contact z similar in both, normal near horizontal.')
    if fwd and bwd:
        dz = (sum(r['contact_z_mean'] for r in bwd) / len(bwd)
              - sum(r['contact_z_mean'] for r in fwd) / len(fwd))
        print()
        print('  measured difference in mean contact z (backward - forward) = %+.4f m' % dz)
        if dz > 0.005:
            print('  -> consistent with H_A: the backwards flicks touch HIGHER up the block')
        elif abs(dz) <= 0.005:
            print('  -> does not separate H_A from H_B at 5 mm resolution; contact height is')
            print('     not the discriminator, so the flick must come from something else')
        else:
            print('  -> OPPOSITE to H_A: backwards trials touch LOWER, which the hypothesis')
            print('     did not predict. Report as a refutation, not a confirmation.')
    else:
        print()
        print('  NOT ENOUGH OF BOTH CLASSES to compare -- no conclusion is drawn.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
