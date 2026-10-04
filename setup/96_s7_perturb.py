#!/usr/bin/env python3
"""S7 perturbation builder (issue #9 / §4.2): off-canonical initial placement.

Generates a SEEDED off-canonical placement for the demo boxes (the adaptation
probe: the deterministic baseline must pick from wherever the world actually
is - it is object-name-driven, not position-driven), applies it via the gz
set_pose service, and prints the schedule as JSON (the runner attaches it to
the batch row).

Placement constraint set (geometry priors, HANDOFF §三):
  - on the ground plane (z = 0.0175) - the grasp descend is box_z + 0.16
  - inside the reachable annulus where the canonical boxes already live:
    x in [0.16, 0.28], |y| <= 0.24
  - boxes at least 0.12 m apart (arm/gripper clearance)
  - never exactly on a zone centre (the probe must PICK first, not start placed)

Usage:  python3 setup/96_s7_perturb.py --seed 7 [--amp 0.06]
"""
import argparse
import json
import math
import random
import sys

CANONICAL = {
    'target_box_a': (0.22, 0.0, 0.0175),
    'target_box_b': (0.20, -0.18, 0.0175),
}
ZONES = {(0.12, -0.15), (0.25, 0.05)}
MIN_SEP = 0.12
X_RANGE = (0.16, 0.28)
Y_RANGE = (-0.24, 0.20)


def gz_set_pose(name, xyz, world='empty'):
    from gz.msgs10 import boolean_pb2, pose_pb2
    import gz.transport13 as gz_transport
    node = gz_transport.Node()
    req = pose_pb2.Pose()
    req.name = name
    req.position.x, req.position.y, req.position.z = xyz
    req.orientation.w = 1.0
    rep = node.request('/world/%s/set_pose' % world, req, pose_pb2.Pose,
                       boolean_pb2.Boolean, 300)
    if rep is None:
        return False
    if isinstance(rep, tuple):
        rep = rep[-1]
    return bool(getattr(rep, 'data', rep))


def sample_placements(rng, amp):
    """Perturb each canonical box within the reachable band; retry until the
    separation + zone-clearance constraints hold (seeded => deterministic)."""
    while True:
        cand = {}
        for name, (cx, cy, cz) in CANONICAL.items():
            x = min(max(cx + rng.uniform(-amp, amp), X_RANGE[0]), X_RANGE[1])
            y = min(max(cy + rng.uniform(-amp, amp), Y_RANGE[0]), Y_RANGE[1])
            cand[name] = (round(x, 4), round(y, 4), cz)
        seps = [dist(cand[a][:2], cand[b][:2])
                for a in cand for b in cand if a < b]
        zone_dists = [min(dist(pos[:2], z) for z in ZONES)
                      for pos in cand.values()]
        if min(seps) >= MIN_SEP and min(zone_dists) >= 0.05:
            return cand


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--amp', type=float, default=0.06)
    ap.add_argument('--apply', action='store_true',
                    help='actually set the poses (default: print only)')
    args = ap.parse_args()

    rng = random.Random(args.seed)
    placements = sample_placements(rng, args.amp)
    schedule = {'tool': 's7_perturb', 'seed': args.seed, 'amp': args.amp,
                'placements': {k: list(v) for k, v in placements.items()}}
    print(json.dumps(schedule))
    if args.apply:
        for name, xyz in placements.items():
            ok = gz_set_pose(name, xyz)
            if not ok:
                print('set_pose failed for %s' % name, file=sys.stderr)
                return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
