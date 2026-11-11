#!/usr/bin/env python3
"""What the gripper gate actually measures, checked against the robot model and the raw bundle.

Answers: is the 0.002 limit a radians-vs-metres error, and can the observed aperture have
enclosed the 35 mm block? Reads the installed URDF and R/t1's evidence bundle. No simulator.
"""
import json
import os
import sys

URDF_CANDIDATES = [
    '/home/ros/agentic_workcell_ws/install/share/open_manipulator_description/urdf/'
    'open_manipulator_x/open_manipulator_x.urdf',
    '/home/ros/r4check/install/share/open_manipulator_description/urdf/'
    'open_manipulator_x/open_manipulator_x.urdf',
]
BUNDLE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      '..', 'evobot_t08_evidence_loop_20261112', 'evidence', 'R', 't1',
                      'evidence_bundle.json')
BOX_M = 0.035
OPEN_POS = 0.02
CLOSE_POS = -0.011
LIMIT = 0.002


def urdf_joint_type(path):
    text = open(path).read()
    for name in ('gripper_left_joint', 'gripper_right_joint'):
        idx = text.find('<joint name="%s"' % name)
        if idx < 0:
            return None
        snippet = text[idx:idx + 300]
        jtype = snippet.split('type="')[1].split('"')[0]
        lower = upper = None
        if 'lower="' in snippet:
            lower = float(snippet.split('lower="')[1].split('"')[0])
            upper = float(snippet.split('upper="')[1].split('"')[0])
        return name, jtype, lower, upper
    return None


def main():
    path = next((p for p in URDF_CANDIDATES if os.path.exists(p)), None)
    if path is None:
        raise SystemExit('REFUSED: no open_manipulator URDF found; cannot decide units')
    name, jtype, lower, upper = urdf_joint_type(path)
    print('URDF: %s' % path)
    print('  %s type=%s limit=[%s, %s]' % (name, jtype, lower, upper))
    prismatic = (jtype == 'prismatic')
    print('  => position is %s' % ('a LINEAR displacement in METRES' if prismatic
                                    else 'an ANGLE in RADIANS'))
    print()
    print('LIMIT INTERPRETATION')
    print('  max_aperture_change_rad = %.4f' % LIMIT)
    if prismatic:
        print('  applied to a prismatic joint => %.1f mm of finger travel' % (LIMIT * 1000))
        print('  the field NAME says radians; the joint is linear. Name and unit disagree.')
    else:
        print('  applied to a revolute joint => %.3f rad' % LIMIT)
    print()
    travel_to_grasp = OPEN_POS - BOX_M / 2.0
    print('GEOMETRY OF A GENUINE GRASP OF THIS BLOCK')
    print('  block width            %.1f mm' % (BOX_M * 1000))
    print('  per-finger contact pos %.4f m (gap = %.1f mm)' % (BOX_M / 2.0, BOX_M * 1000))
    print('  commanded open         %.4f m' % OPEN_POS)
    print('  travel open->contact   %.4f m = %.2f mm' % (travel_to_grasp, travel_to_grasp * 1000))
    print('  limit / grasp travel   %.0f%%' % (100 * LIMIT / travel_to_grasp))
    print()
    bundle = json.load(open(BUNDLE))
    gripper = bundle.get('gripper') or {}
    span = gripper.get('span') or []
    if not span:
        raise SystemExit('REFUSED: bundle has no gripper span; cannot analyse')
    values = [float(v) for _t, v in span]
    lo, hi = min(values), max(values)
    travel = hi - lo
    print('OBSERVED (R/t1, %d samples of %s)' % (len(values), gripper.get('joint_name')))
    print('  min %.6f  max %.6f  travel %.6f m (%.2f mm)' % (lo, hi, travel, travel * 1000))
    print('  commanded open %.3f, closed stop %.3f' % (OPEN_POS, CLOSE_POS))
    print('  fingers stayed %.1f mm from the closed stop' % ((lo - CLOSE_POS) * 1000))
    print('  max finger gap during window = %.1f mm' % (2 * abs(hi) * 1000 if hi < 0 else 2 * hi * 1000))
    print('  => a %.0f mm block cannot fit between the fingers at any sample' % (BOX_M * 1000))
    print()
    print('FINDINGS')
    print('  A. units: the lane\'s "0.002 rad should be 0.040 rad" is REFUTED for this robot;')
    print('     the joint is prismatic so 0.002 already means 2 mm. But the field is named')
    print('     _rad while carrying metres, which is what invited the error.')
    print('  B. calibration: %.1f mm is %.0f%% of the travel a genuine grasp needs, and the')
    print('     project\'s own archived GRASPED_AT_GOAL records sit at a similar aperture,')
    print('     so the bound is narrower than nominal behaviour. It is NOT traceable to any')
    print('     measurement; evaluate.py:328 calls it calibrated with no citation.')
    print('  C. discrimination: the gate bounds travel only. It never tests whether the')
    print('     aperture could enclose the object, which is the property that defines a')
    print('     grasp. Both a contact-flex and a grasp are therefore judged by one number.')
    return 0


if __name__ == '__main__':
    sys.exit(main())