"""Signed target-force direction, not just a magnitude.

The contact gate has always compared ``|sum of body_1 forces|`` against m*g. A
magnitude cannot tell a support force from a suction force, or a vertical load
from a lateral one, so "the target body's signed force is calibrated" stayed
false. This gate uses the declared, known direction (gravity) and refuses the
window unless every settled sample pushes the target up, in the declared partner
direction, with no lateral component and no contact point acting the other way.

Declared scope: one known direction (resting weight). A known lateral or oblique
load is still not calibrated, and collisions without a contact sensor stay
UNKNOWN.
"""
import json
import math
from pathlib import Path

from contact_gate import observation, require

#: Frozen fixture, matched against `signed_force` in the declaration.
FROZEN = dict(target='target_box_a', partner='ground_plane', direction=[0., 0., 1.],
              magnitude_min_n=.392, magnitude_max_n=.588, max_lateral_n=1e-6,
              min_signed_samples=476, max_cosine_error=1e-3)


def rows(path):
    with Path(path).open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def verify_file(path, declaration):
    declared = declaration.get('signed_force')
    require(isinstance(declared, dict) and declared == {key: FROZEN[key] for key in
                                                       ('target', 'partner', 'direction',
                                                        'magnitude_min_n', 'magnitude_max_n',
                                                        'max_lateral_n', 'min_signed_samples')},
            'signed force fixture changed or undeclared')
    target = FROZEN['target']
    partner_prefix = FROZEN['partner'] + '::'
    samples = 0
    z_values, lateral_max, cosine_min = [], 0., 1.
    for row in rows(path):
        if not declaration['settle_from_ns'] <= row['sim_ns'] <= declaration['settle_to_ns']:
            continue
        watched = row['targets'][target]
        result = observation(watched)
        require(result['state'] == 'CONTACTS_WITH_FORCE',
                'the settled target has no complete contact force')
        for entry in watched['contacts']['contact']:
            other = (entry.get('collision2') or {}).get('name', '')
            require(str(other).startswith(partner_prefix),
                    'contact partner is not the declared one: %r' % (other,))
        points = result['body_1_point_forces_n']
        require(points, 'no contact force points in a settled sample')
        require(all(point[2] > 0 for point in points),
                'a contact point pushes the target in the gravity direction')
        total = result['raw_body_1_force_sum_n']
        samples += 1
        z_values.append(total[2])
        lateral_max = max(lateral_max, math.hypot(total[0], total[1]))
        norm = math.hypot(*total)
        require(norm > 0, 'signed force has no magnitude')
        cosine = sum(a * b for a, b in zip(total, FROZEN['direction'])) / norm
        cosine_min = min(cosine_min, cosine)
        require(cosine >= 1. - FROZEN['max_cosine_error'],
                'the force is not along the declared direction (cosine %.6f)' % cosine)
    require(samples >= FROZEN['min_signed_samples'],
            'signed force coverage below declaration')
    require(all(FROZEN['magnitude_min_n'] <= z <= FROZEN['magnitude_max_n'] for z in z_values),
            'a settled sample differs from the declared weight')
    require(lateral_max <= FROZEN['max_lateral_n'],
            'a lateral force component appeared on a vertical support')
    return dict(status='SIGNED_FORCE_PASS', target=target, partner=FROZEN['partner'],
                samples=samples, direction=FROZEN['direction'],
                min_z_n=min(z_values), max_z_n=max(z_values), min_direction_cosine=cosine_min,
                max_lateral_n=lateral_max, lateral_limit_n=FROZEN['max_lateral_n'],
                known_direction_only=True,
                interpretation='One known support direction (gravity) is signed and calibrated; '
                               'lateral/oblique known loads and torque remain uncalibrated')
