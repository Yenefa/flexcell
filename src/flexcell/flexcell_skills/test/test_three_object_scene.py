"""The three-box scene is opt-in; the shipped world and profiles stay A/B."""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
from sim_profile import THREE_OBJECTS, profile


def read_params(path):
    return yaml.safe_load(Path(path).read_text())


def world_models(path):
    return [model.get('name') for model in
            ET.parse(path).getroot().find('world').findall('model')]


def plugin(path, name):
    return ET.parse(path).getroot().find("world/plugin[@name='%s']" % name)


def test_the_shipped_profile_still_has_exactly_two_boxes(tmp_path):
    params_path, world_path = profile(tmp_path / 'default')
    params = read_params(params_path)
    assert params['observe_server']['ros__parameters']['tracked_objects'] == [
        'target_box_a', 'target_box_b']
    assert 'target_box_c' not in world_models(world_path)
    assert plugin(world_path, 'flexcell::PhysicsTrace').find('object') is None
    assert plugin(world_path, 'flexcell::DetachableCarryGuard') is None


def test_the_three_box_scene_is_declared_everywhere_it_is_needed(tmp_path):
    params_path, world_path = profile(
        tmp_path / 'three', backend='detachable_joint', scene='three_boxes')
    params = read_params(params_path)
    assert params['observe_server']['ros__parameters']['tracked_objects'] == list(THREE_OBJECTS)
    assert params['observe_server']['ros__parameters']['object_target_box_c_size'] == [
        pytest.approx(.035)] * 3
    for node in ('pick_server', 'place_server', 'carry_server'):
        assert params[node]['ros__parameters']['tracked_objects'] == list(THREE_OBJECTS)

    models = world_models(world_path)
    assert models.count('target_box_c') == 1
    model = ET.parse(world_path).getroot().find("world/model[@name='target_box_c']")
    pose = [float(value) for value in model.find('pose').text.split()]
    assert pose[:3] == pytest.approx([.15, -.05, .0175])

    trace = plugin(world_path, 'flexcell::PhysicsTrace')
    assert [item.text for item in trace.findall('object')] == list(THREE_OBJECTS)
    guard = plugin(world_path, 'flexcell::DetachableCarryGuard')
    assert [item.text for item in guard.findall('allowed_model')] == list(THREE_OBJECTS)


def test_a_detachable_guard_without_a_three_box_scene_keeps_the_default_names(tmp_path):
    _, world_path = profile(tmp_path / 'joint', backend='detachable_joint')
    guard = plugin(world_path, 'flexcell::DetachableCarryGuard')
    assert guard.findall('allowed_model') == []


def test_the_three_box_velocity_carry_allows_every_tracked_object(tmp_path):
    params_path, world_path = profile(tmp_path / 'servo-three', scene='three_boxes')
    tracked = read_params(params_path)['observe_server']['ros__parameters']['tracked_objects']
    carry = plugin(world_path, 'flexcell::CarryDynamics')
    assert [item.text for item in carry.findall('allowed_model')] == tracked


def test_an_unknown_scene_is_refused(tmp_path):
    with pytest.raises(ValueError, match='unknown scene'):
        profile(tmp_path / 'bad', scene='four_boxes')
