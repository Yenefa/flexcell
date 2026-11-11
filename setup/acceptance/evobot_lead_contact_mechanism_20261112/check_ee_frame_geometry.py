#!/usr/bin/env python3
"""Why contact_height_m cannot control the contact height: the URDF, not an inference.

WHY
    Section 8 of README.md traced the +15 mm command-to-contact offset to push.py holding
    the end effector at constant z = contact_height_m while the control target
    end_effector_link has no collision geometry. That was read from the code. This checks
    the robot description, which is the primary source.

WHAT IT FOUND (2026-11-12)
    end_effector_link  visual: box 0.01^3        collision: NONE
    gripper_left_link  collision: gripper_left_palm.stl   origin (0.0817, 0.021, 0)
    gripper_right_link collision: gripper_right_palm.stl  origin (0.0817, -0.021, 0)
    end_effector_joint origin: (0.126, 0, 0) from link5

    The frame the push skill positions is 44.3 mm forward of the palm origins along
    link5 x, and carries no collision geometry at all. The palms - whose meshes are named
    *palm*, not finger - are the bodies that actually touch. contact_height_m therefore
    positions a bookkeeping frame, and the mapping from it to a contact height is a fixed
    geometric offset the skill never models.

    This is the mechanism behind the measurement, not a restatement of it.
"""
import glob
import re
import sys

CANDIDATES = [
    '/home/ros/agentic_workcell_ws/install/share/open_manipulator_description/urdf/open_manipulator_x/open_manipulator_x.urdf',
    '/home/ros/agentic_workcell_ws/src/open_manipulator/open_manipulator_description/urdf/open_manipulator_x/open_manipulator_x.urdf',
]


def find_urdf():
    for path in CANDIDATES:
        try:
            open(path).close()
            return path
        except OSError:
            continue
    hits = glob.glob('/home/ros/**/open_manipulator_x.urdf', recursive=True)
    if hits:
        return hits[0]
    raise SystemExit('REFUSED: open_manipulator_x.urdf not found; this check cannot run')


def main():
    path = find_urdf()
    text = open(path, encoding='utf-8').read()
    print('urdf: %s' % path)
    print()

    ee_collision = None
    for match in re.finditer(r'<link name="([^"]+)">(.*?)</link>', text, re.S):
        name, body = match.group(1), match.group(2)
        if name not in ('end_effector_link', 'gripper_left_link', 'gripper_right_link'):
            continue
        has_visual = '<visual>' in body
        has_collision = '<collision>' in body
        mesh = re.search(r'<collision>.*?filename="([^"]+)"', body, re.S)
        print('  %-20s visual=%-5s collision=%-5s %s'
              % (name, has_visual, has_collision,
                 (mesh.group(1).rsplit('/', 1)[-1] if mesh else '')))
        if name == 'end_effector_link':
            ee_collision = has_collision

    print()
    for match in re.finditer(r'<joint name="([^"]+)" type="([^"]+)">(.*?)</joint>', text, re.S):
        name, jtype, body = match.group(1), match.group(2), match.group(3)
        if not any(k in name for k in ('gripper', 'end_effector')):
            continue
        origin = re.search(r'<origin[^>]*xyz="([^"]+)"', body)
        print('  %-22s %-9s origin=%s'
              % (name, jtype, origin.group(1) if origin else '-'))

    print()
    if ee_collision is None:
        raise SystemExit('REFUSED: end_effector_link not found in the URDF')
    if ee_collision:
        print('UNEXPECTED: end_effector_link HAS collision geometry.');
        print('The mechanism in README section 8 would then need re-deriving.');
        return 1
    print('CONFIRMED: end_effector_link has NO collision geometry.')
    print('The push skill positions that frame, so contact_height_m cannot be a statement')
    print('about where the robot touches the block. The palms are the contacting bodies.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
