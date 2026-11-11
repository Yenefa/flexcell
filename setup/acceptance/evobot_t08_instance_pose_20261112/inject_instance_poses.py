#!/usr/bin/env python3
"""Place a task instance's objects at the poses its spec DECLARES, in a generated world COPY.

WHY THIS EXISTS
    sim_profile.profile() hard-codes target_box_a at (0.22, 0.00) and target_box_b at
    (0.20, -0.18) and takes no object-pose argument. So a task spec whose declared poses
    differ from those values -- every t08_unseen spec, and t08_dev seed2001/seed2002 -- was
    never actually instantiated: the run happened in the dev world and was then graded
    against unseen geometry. Measured offsets up to 70.7 mm on a task whose entire
    tolerance band is 30-150 mm.

WHY IT EDITS THE COPY AND NOT sim_profile.py
    sim_profile.py's output is hashed into frozen declarations. The established pattern in
    this project (see inject_contact_evidence.py) is to leave it byte-identical and edit a
    COPY of the generated world. This does the same.

WHAT IT REFUSES
    - a spec object that has no matching <model> in the world (silently skipping it would
      reproduce the very defect this fixes)
    - a model whose <pose> cannot be parsed
    - a non-finite coordinate
    It then RE-READS the file and asserts the poses it wrote are the poses that are there.
"""
import json
import math
import re
import sys


def _finite_triple(values):
    if len(values) < 3:
        return None
    try:
        triple = tuple(float(v) for v in values[:3])
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(v) for v in triple):
        return None
    return triple


def set_model_pose(text, model, xyz):
    """Rewrite the first <pose> inside <model name=model>. Returns (text, changed)."""
    open_tag = re.compile(r'<model\s+name="%s"\s*>' % re.escape(model))
    match = open_tag.search(text)
    if match is None:
        return text, False
    # find the first <pose> at or after the model tag, before the next <model
    tail = text[match.end():]
    next_model = tail.find('<model ')
    window = tail if next_model < 0 else tail[:next_model]
    pose = re.search(r'<pose>([^<]*)</pose>', window)
    if pose is None:
        return text, False
    new_pose = '<pose>%f %f %f 0 0 0</pose>' % xyz
    abs_start = match.end() + pose.start()
    abs_end = match.end() + pose.end()
    return text[:abs_start] + new_pose + text[abs_end:], True


def read_model_pose(text, model):
    open_tag = re.compile(r'<model\s+name="%s"\s*>' % re.escape(model))
    match = open_tag.search(text)
    if match is None:
        return None
    tail = text[match.end():]
    next_model = tail.find('<model ')
    window = tail if next_model < 0 else tail[:next_model]
    pose = re.search(r'<pose>\s*([-0-9.eE+]+)\s+([-0-9.eE+]+)\s+([-0-9.eE+]+)', window)
    if pose is None:
        return None
    return tuple(float(pose.group(i)) for i in (1, 2, 3))


def main(argv):
    if len(argv) < 2:
        print('usage: inject_instance_poses.py <world.sdf> <task.json>', file=sys.stderr)
        return 2
    world_path, task_path = argv[0], argv[1]
    spec = json.load(open(task_path, encoding='utf-8'))
    if 'objects' not in spec:
        raise SystemExit('REFUSED: task spec has no objects[]')
    text = open(world_path, encoding='utf-8').read()

    applied = []
    for obj in spec['objects']:
        name = obj.get('name')
        pose = obj.get('initial_pose')
        if not name or pose is None:
            raise SystemExit('REFUSED: object entry missing name or initial_pose: %r' % (obj,))
        xyz = _finite_triple(pose)
        if xyz is None:
            raise SystemExit('REFUSED: %s initial_pose is not three finite numbers: %r'
                             % (name, pose))
        text, changed = set_model_pose(text, name, xyz)
        if not changed:
            raise SystemExit('REFUSED: no <model name="%s"> with a <pose> in %s -- '
                             'skipping it would leave the instance uninstantiated, which is '
                             'the defect this tool exists to fix' % (name, world_path))
        applied.append((name, xyz))

    open(world_path, 'w', encoding='utf-8').write(text)

    # RE-READ what is actually on disk. A write that is believed rather than verified is
    # the failure mode this whole round is about.
    verify_text = open(world_path, encoding='utf-8').read()
    for name, xyz in applied:
        got = read_model_pose(verify_text, name)
        if got is None:
            raise SystemExit('FAILED: %s has no readable pose after writing' % name)
        if any(abs(got[i] - xyz[i]) > 1e-9 for i in range(3)):
            raise SystemExit('FAILED: %s wrote %r but read back %r' % (name, xyz, got))
        print('  %-16s pose = (%.6f, %.6f, %.6f)' % (name, got[0], got[1], got[2]))
    print('INSTANCE_POSES_SET %d object(s) from %s'
          % (len(applied), task_path.rsplit('/', 1)[-1]))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
