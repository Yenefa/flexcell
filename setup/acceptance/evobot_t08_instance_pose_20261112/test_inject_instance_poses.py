#!/usr/bin/env python3
"""Tests for inject_instance_poses.py. Every test builds its own world text, no Gazebo."""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, 'inject_instance_poses.py')

WORLD = '''<?xml version="1.0"?>
<sdf version="1.10">
  <world name="empty">
    <model name="target_box_a">
      <pose>0.220000 0.000000 0.0175 0 0 0</pose>
      <link name="link"/>
    </model>
    <model name="target_box_b">
      <pose>0.200000 -0.180000 0.0175 0 0 0</pose>
      <link name="link"/>
    </model>
    <model name="zone_1">
      <pose>0.120000 -0.150000 0.001 0 0 0</pose>
    </model>
  </world>
</sdf>
'''


def run(world_text, spec):
    tmp = tempfile.mkdtemp()
    world = os.path.join(tmp, 'world.sdf')
    task = os.path.join(tmp, 'task.json')
    open(world, 'w').write(world_text)
    open(task, 'w').write(json.dumps(spec))
    proc = subprocess.run([sys.executable, TOOL, world, task],
                          capture_output=True, text=True)
    return proc, open(world).read()


def test_moves_an_object_to_its_declared_pose():
    spec = {'task_id': 'X', 'objects': [
        {'name': 'target_box_a', 'initial_pose': [0.21, 0.03, 0.0175, 0.0]}]}
    proc, after = run(WORLD, spec)
    assert proc.returncode == 0, proc.stderr
    assert '<pose>0.210000 0.030000 0.017500 0 0 0</pose>' in after
    # the OTHER object must not be touched
    assert '<pose>0.200000 -0.180000 0.0175 0 0 0</pose>' in after


def test_moves_both_objects():
    spec = {'task_id': 'X', 'objects': [
        {'name': 'target_box_a', 'initial_pose': [0.23, -0.07, 0.0175, 0.0]},
        {'name': 'target_box_b', 'initial_pose': [0.20, -0.19, 0.0175, 0.0]}]}
    proc, after = run(WORLD, spec)
    assert proc.returncode == 0, proc.stderr
    assert '<pose>0.230000 -0.070000 0.017500 0 0 0</pose>' in after
    assert '<pose>0.200000 -0.190000 0.017500 0 0 0</pose>' in after


def test_a_model_outside_the_spec_is_left_where_it_was():
    """Objects not named in the spec must not move.

    NOTE on scope: this used to assert the same about zone_1, and it was right at the time.
    Zone markers are now moved ON PURPOSE (see the zone tests below) because a marker that
    says 'push it into the marked zone' while sitting somewhere else is a wrong statement
    about the task. So this test is narrowed to OBJECT models, which is the property it was
    really about -- an unrelated object drifting would be worse than not rewriting at all.
    The zone behaviour is covered by its own three tests rather than dropped.
    """
    spec = {'task_id': 'X', 'objects': [
        {'name': 'target_box_a', 'initial_pose': [0.19, 0.02, 0.0175, 0.0]}]}
    proc, after = run(WORLD, spec)
    assert proc.returncode == 0, proc.stderr
    # target_box_b is not in the spec, so it must keep the pose the world gave it
    assert '<pose>0.200000 -0.180000 0.0175 0 0 0</pose>' in after


def test_refuses_when_a_spec_object_has_no_model():
    spec = {'task_id': 'X', 'objects': [
        {'name': 'not_a_model', 'initial_pose': [0.0, 0.0, 0.0175, 0.0]}]}
    proc, after = run(WORLD, spec)
    assert proc.returncode != 0, 'must refuse rather than silently skip'
    assert 'REFUSED' in (proc.stderr + proc.stdout)
    # and must not have written a half-applied world
    assert after == WORLD


def test_refuses_on_non_finite_pose():
    tmp = tempfile.mkdtemp()
    world = os.path.join(tmp, 'world.sdf')
    task = os.path.join(tmp, 'task.json')
    open(world, 'w').write(WORLD)
    open(task, 'w').write(json.dumps({'task_id': 'X', 'objects': [
        {'name': 'target_box_a', 'initial_pose': ['nan', 0.0, 0.0175]}]}))
    proc = subprocess.run([sys.executable, TOOL, world, task],
                          capture_output=True, text=True)
    assert proc.returncode != 0
    assert open(world).read() == WORLD


def test_refuses_when_spec_has_no_objects():
    proc, after = run(WORLD, {'task_id': 'X'})
    assert proc.returncode != 0
    assert 'REFUSED' in (proc.stderr + proc.stdout)


def test_dev_spec_is_a_semantic_no_op():
    spec = {'task_id': 'T08-push-seed2000', 'objects': [
        {'name': 'target_box_a', 'initial_pose': [0.22, 0.0, 0.0175, 0.0]},
        {'name': 'target_box_b', 'initial_pose': [0.2, -0.18, 0.0175, 0.0]}]}
    proc, after = run(WORLD, spec)
    assert proc.returncode == 0
    assert '0.220000 0.000000 0.017500' in after
    assert '0.200000 -0.180000 0.017500' in after


ZONE_WORLD = '''<?xml version="1.0"?>
<sdf version="1.10">
  <world name="empty">
    <model name="target_box_a">
      <pose>0.220000 0.000000 0.0175 0 0 0</pose>
      <link name="link"/>
    </model>
    <model name="target_box_b">
      <pose>0.200000 -0.180000 0.0175 0 0 0</pose>
      <link name="link"/>
    </model>
    <model name="zone_1">
      <pose>0.120000 -0.150000 0.001 0 0 0</pose>
    </model>
    <model name="zone_2">
      <pose>0.250000 0.050000 0.001 0 0 0</pose>
    </model>
  </world>
</sdf>
'''


def test_zone_marker_moves_to_the_spec_zone_at_table_height():
    spec = {'task_id': 'X',
            'objects': [{'name': 'target_box_a', 'initial_pose': [0.22, 0.0, 0.0175, 0.0]}],
            'zones': [{'name': 'zone_push', 'pose': [0.11, 0.03, 0.0175], 'radius': 0.06}]}
    proc, after = run(ZONE_WORLD, spec)
    assert proc.returncode == 0, proc.stderr
    # x,y from the spec, z at table level not at the block's height
    assert '<pose>0.110000 0.030000 0.001000 0 0 0</pose>' in after


def test_unused_zone_marker_is_parked_not_left_on_the_table():
    spec = {'task_id': 'X',
            'objects': [{'name': 'target_box_a', 'initial_pose': [0.22, 0.0, 0.0175, 0.0]}],
            'zones': [{'name': 'zone_push', 'pose': [0.11, 0.03, 0.0175], 'radius': 0.06}]}
    proc, after = run(ZONE_WORLD, spec)
    assert proc.returncode == 0
    # zone_2 has no counterpart in the spec, so it must not stay where it was
    assert '<pose>0.250000 0.050000 0.001 0 0 0</pose>' not in after
    assert '<pose>0.000000 0.000000 -1.000000 0 0 0</pose>' in after


def test_two_spec_zones_map_onto_both_markers():
    spec = {'task_id': 'X',
            'objects': [{'name': 'target_box_a', 'initial_pose': [0.22, 0.0, 0.0175, 0.0]}],
            'zones': [{'name': 'zone_1', 'pose': [0.12, -0.15, 0.0175], 'radius': 0.06},
                      {'name': 'zone_2', 'pose': [0.25, 0.05, 0.0175], 'radius': 0.06}]}
    proc, after = run(ZONE_WORLD, spec)
    assert proc.returncode == 0, proc.stderr
    assert '<pose>0.120000 -0.150000 0.001000 0 0 0</pose>' in after
    assert '<pose>0.250000 0.050000 0.001000 0 0 0</pose>' in after
    # nothing parked when the spec accounts for every marker
    assert '-1.000000' not in after


def test_a_spec_without_zones_leaves_markers_parked_but_does_not_fail():
    spec = {'task_id': 'X',
            'objects': [{'name': 'target_box_a', 'initial_pose': [0.22, 0.0, 0.0175, 0.0]}]}
    proc, after = run(ZONE_WORLD, spec)
    assert proc.returncode == 0, proc.stderr
    assert '-1.000000' in after


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t()
            print('  PASS %s' % t.__name__)
        except AssertionError as exc:
            failed += 1
            print('  FAIL %s: %s' % (t.__name__, exc))
    print('%d passed, %d failed' % (len(tests) - failed, failed))
    sys.exit(1 if failed else 0)