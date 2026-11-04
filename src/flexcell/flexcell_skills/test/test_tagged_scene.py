import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
from sim_profile import THREE_OBJECTS, profile


def test_tags_are_visual_only_and_calibration_has_no_box_world_positions(tmp_path):
    _, normal = profile(tmp_path / 'normal', scene='three_boxes', camera=True)
    _, tagged = profile(tmp_path / 'tags', scene='tagged_three_boxes', camera=True)
    a, b = ET.parse(normal).getroot(), ET.parse(tagged).getroot()
    calibration = json.loads((tagged.parent / 'vision.json').read_text())
    assert set(calibration) == {'camera_frame', 'camera_sdf_pose', 'tag_size_m', 'tags'}
    assert [tag['object'] for tag in calibration['tags']] == list(THREE_OBJECTS)
    assert calibration['tag_size_m'] == .025
    for tag, name in zip(calibration['tags'], THREE_OBJECTS):
        path = "world/model[@name='%s']" % name
        for suffix in ('pose', 'link/inertial', 'link/collision'):
            assert ET.tostring(a.find(path + '/' + suffix)) == ET.tostring(b.find(path + '/' + suffix))
        visual = b.find(path + "/link/visual[@name='apriltag_%d']" % tag['id'])
        assert visual.find('geometry/plane/size').text == '0.03125 0.03125'
        assert tag['tag_to_center'][2] == -.0177
        assert 'world_center_m' not in tag
    image = b.find("world/model[@name='dataset_camera']/link/sensor/camera/image")
    assert (image.find('width').text, image.find('height').text) == ('1280', '960')


def test_tagged_scene_requires_an_actual_camera(tmp_path):
    with pytest.raises(ValueError, match='requires camera'):
        profile(tmp_path / 'bad', scene='tagged_three_boxes')


def test_perception_world_has_no_robot_or_carry_plugins(tmp_path):
    _, path = profile(tmp_path / 'read-only', backend='detachable_joint',
                      scene='tagged_three_boxes', camera=True, perception_only=True)
    world = ET.parse(path).getroot().find('world')
    names = [p.get('name') for p in world.findall('plugin')]
    assert 'flexcell::PhysicsTrace' not in names
    assert 'flexcell::DetachableCarryGuard' not in names
    assert 'gz::sim::systems::Sensors' in names
    assert world.find("model[@name='open_manipulator_x']") is None
    assert json.loads((path.parent / 'vision.json').read_text())['perception_only']
