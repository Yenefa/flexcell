import copy
import math

import pytest

from flexcell_skills.vision_geometry import compose, observations, optical_pose, validate_calibration


@pytest.mark.parametrize('axis,expected', [
    ([1., 0., 0.], [0., -1., 0.]),
    ([0., 1., 0.], [0., 0., -1.]),
    ([0., 0., 1.], [1., 0., 0.]),
])
def test_gazebo_camera_axes_are_converted_to_optical_axes(axis, expected):
    pose = optical_pose([0.] * 6)
    assert compose(pose, axis + [0., 0., 0., 1.])[:3] == pytest.approx(expected)


def test_camera_world_translation_and_yaw_are_applied_in_metres():
    pose = optical_pose([1., 2., 3., 0., 0., math.pi / 2])
    assert compose(pose, [0., 0., 1., 0., 0., 0., 1.])[:3] == pytest.approx([1., 3., 3.])


def frame():
    calibration = dict(camera_frame='optical', camera_sdf_pose=[0.] * 6, tag_size_m=.025,
        tags=[dict(id=0, object='box', frame='tag',
                   tag_to_center=[0., 0., -.0177, 0., 0., 0., 1.])])
    image = dict(stamp_ns=1_000_000_000, frame_id='optical', width=1280, height=960)
    info = dict(image, p=[800., 0., 640., 0., 0., 800., 480., 0., 0., 0., 1., 0.], d=[])
    detected = dict(stamp_ns=image['stamp_ns'], frame_id='optical',
                    tags=[dict(id=0, hamming=0, margin=100.)])
    transforms = {'tag': dict(stamp_ns=image['stamp_ns'], frame_id='optical',
                            pose=[0., 0., 1., 0., 0., 0., 1.])}
    return calibration, image, info, detected, transforms


def test_center_offset_is_transformed_not_replaced_by_a_fixed_world_height():
    values = frame()
    before = copy.deepcopy(values)
    report = observations(*values)
    assert report['source'] == 'VISION_APRILTAG'
    assert report['objects']['box']['available']
    assert report['objects']['box']['world_center_m'] == pytest.approx([.9823, 0., 0.])
    assert values == before


@pytest.mark.parametrize('failure,reason', [
    ('info_stamp', 'camera_info_unmatched'), ('tf_stamp', 'tag_transform_unmatched'),
    ('missing', 'tag_missing'), ('duplicate', 'tag_ambiguous'),
    ('uncalibrated', 'camera_uncalibrated'), ('distorted', 'image_requires_rectification'),
    ('bad_rotation', 'tag_transform_invalid'), ('stale_image', 'stale_image'),
])
def test_unusable_frames_do_not_reuse_a_pose(failure, reason):
    values = frame()
    _, image, info, detected, transforms = values
    if failure == 'info_stamp': info['stamp_ns'] -= 1
    elif failure == 'tf_stamp': transforms['tag']['stamp_ns'] -= 1
    elif failure == 'missing': detected['tags'] = []
    elif failure == 'duplicate': detected['tags'] *= 2
    elif failure == 'uncalibrated': info['p'][0] = 0.
    elif failure == 'distorted': info['d'] = [.1]
    elif failure == 'bad_rotation': transforms['tag']['pose'][3:] = [0.] * 4
    elif failure == 'stale_image': image['error'] = 'stale_image'
    result = observations(*values)['objects']['box']
    assert not result['available']
    assert result['reason'].startswith(reason)
    assert 'world_center_m' not in result


@pytest.mark.parametrize('failure', ['empty', 'duplicate_object', 'invalid_offset'])
def test_invalid_calibration_cannot_produce_vacuous_success(failure):
    calibration = frame()[0]
    if failure == 'empty':
        calibration['tags'] = []
    elif failure == 'duplicate_object':
        tag = copy.deepcopy(calibration['tags'][0])
        tag.update(id=1, frame='another_tag')
        calibration['tags'].append(tag)
    else:
        calibration['tags'][0]['tag_to_center'][3:] = [0.] * 4
    with pytest.raises(ValueError):
        validate_calibration(calibration)
