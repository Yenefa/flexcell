"""Visual-only task selection and endpoint plans; all scenes here are synthetic."""
from copy import deepcopy
import hashlib
import itertools
import json
import math
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

from flexcell_skills.visual_region_plan import BOX_RADIUS_M, plan_region
from flexcell_skills.contracts.safety_gate import destination_clear

ROOT = Path(__file__).resolve().parents[4]
REGION = [.19, .28, -.21, .04]
STAGING = [[.12, .05], [.12, -.15]]
NAMES = ['target_box_a', 'target_box_b', 'target_box_c']
ANCHORS = [[.22, 0., .0175], [.20, -.18, .0175], [.14, -.05, .0175]]


def scene(names=NAMES, positions=ANCHORS):
    calibration = dict(camera_frame='camera', camera_sdf_pose=[0.] * 6, tag_size_m=.025,
        tags=[dict(id=i, object=name, frame='tag%d' % i,
                   tag_to_center=[0., 0., -.0177, 0., 0., 0., 1.]) for i, name in enumerate(names)])
    frames = [dict(source='VISION_APRILTAG', image_stamp_ns=1_000_000_000 + i * 500_000_000,
                   camera_frame='camera', image='frame-%03d.png' % i, image_age_at_receive_s=.1,
                   objects={n: dict(available=True, reason='', world_center_m=list(p))
                            for n, p in zip(names, positions)}) for i in range(2)]
    capture = dict(source='VISION_APRILTAG', mode='READ_ONLY', status='OBSERVATIONS_AVAILABLE',
                   capture_started=True, requested_frames=2, captured_frames=2, frames=frames)
    return capture, calibration


@pytest.mark.parametrize('names', list(itertools.permutations(NAMES)))
def test_selection_follows_visual_positions_for_every_identity_permutation(names):
    capture, calibration = scene(names)
    before = deepcopy((capture, calibration))
    plan = plan_region(capture, calibration, REGION, STAGING)
    assert set(plan['selected_objects']) == set(names[:2])
    assert plan['untouched_objects'] == [names[2]]
    assert [m['phase'] for m in plan['moves']] == ['clear', 'clear', 'restore', 'restore']
    assert {m['object_name'] for m in plan['moves']} == set(names[:2])
    restore = [m for m in plan['moves'] if m['phase'] == 'restore']
    expected = dict(zip(names, ANCHORS))
    assert all(m['target_world_m'] == expected[m['object_name']] for m in restore)
    assert plan['image_stamp_ns'] == capture['frames'][0]['image_stamp_ns']
    assert plan['execution_ready'] is False and plan['requires_live_observe'] is True
    assert (capture, calibration) == before
    # Cross-check nominal endpoints with the actual existing pre-PICK gate,
    # independently of the planner's circle-envelope calculations.
    world = {'world_state': {'objects': [dict(
        name=name, klass='box', available=True, size=[.035] * 3,
        pose=dict(position=dict(zip('xyz', p)), orientation=dict(x=0., y=0., z=0., w=1.)))
        for name, p in zip(names, ANCHORS)]}}
    for move in plan['moves']:
        assert destination_clear(world, move['object_name'], move['target_world_m']) == (True, None)
        obj = next(o for o in world['world_state']['objects'] if o['name'] == move['object_name'])
        obj['pose']['position'] = dict(zip('xyz', move['target_world_m']))


def test_center_outside_but_box_edge_inside_is_selected():
    capture, calibration = scene(positions=[[.185, .03, .0175], [.35, -.18, .0175], [.10, -.15, .0175]])
    plan = plan_region(capture, calibration, REGION, [[.08, .12]])
    assert plan['selected_objects'] == ['target_box_a']


def test_documented_region_and_staging_work_with_the_shared_profile(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'scripts'))
    from sim_profile import profile
    out = tmp_path / 'profile'
    _, world = profile(out, backend='detachable_joint', skill_backend='mtc', camera=True,
                       scene='tagged_three_boxes', level_release_tolerance_deg=5.)
    calibration = json.loads((out / 'vision.json').read_text())
    models = {m.get('name'): m for m in ET.parse(world).getroot().find('world').findall('model')}
    # SDF is used only to make this synthetic input fixture. The planner itself
    # sees the same observations schema as the read-only camera capture.
    points = [[float(v) for v in models[n].find('pose').text.split()[:3]] for n in NAMES]
    capture, _ = scene(positions=points)
    for frame in capture['frames']:
        frame['camera_frame'] = calibration['camera_frame']
    plan = plan_region(capture, calibration, [.20, .28, -.21, .04], STAGING)
    assert plan['selected_objects'] == NAMES[:2] and len(plan['moves']) == 4


def test_corner_uses_distance_to_rectangle_not_a_square_expansion():
    capture, calibration = scene(positions=[[.16, .07, .0175], [.35, -.18, .0175], [.10, -.15, .0175]])
    plan = plan_region(capture, calibration, REGION, [])
    assert plan['moves'] == [] and plan['selected_objects'] == []
    assert plan['untouched_objects'] == NAMES


def test_ambiguous_boundary_stops_instead_of_guessing():
    capture, calibration = scene(positions=[[.16, .03, .0175], *ANCHORS[1:]])
    with pytest.raises(ValueError, match='membership is ambiguous'):
        plan_region(capture, calibration, REGION, STAGING)


@pytest.mark.parametrize('xy', [[.17, .03], [.185, .06]])
def test_outer_envelope_overlap_alone_cannot_justify_moving_an_outside_box(xy):
    capture, calibration = scene(positions=[xy + [.0175], [.35, -.18, .0175], [.10, -.15, .0175]])
    with pytest.raises(ValueError, match='membership is ambiguous'):
        plan_region(capture, calibration, REGION, STAGING)


def test_search_backtracks_when_the_first_staging_point_blocks_both_others():
    capture, calibration = scene(positions=[[.22, 0., .0175], [.22, -.18, .0175], [.04, .20, .0175]])
    plan = plan_region(capture, calibration, REGION, [[.10, 0.], [.10, .07], [.10, -.07]])
    clears = plan['moves'][:2]
    assert all(m['target_world_m'][:2] != [.10, 0.] for m in clears)
    assert math.dist(*[m['target_world_m'] for m in clears]) > 2 * (BOX_RADIUS_M + .01)


@pytest.mark.parametrize('points', [[], [[.12, .05]], [[.12, .05], [.12, .05]],
                                   [[.14, -.05], [.22, 0.]], [[.17, .04], [.17, -.15]]])
def test_missing_occupied_or_not_fully_outside_staging_cannot_produce_a_plan(points):
    with pytest.raises(ValueError, match='no clear-and-restore'):
        plan_region(*scene(), REGION, points)


def test_all_three_objects_can_be_cleared_within_six_moves():
    capture, calibration = scene(positions=[[.22, 0., .0175], [.20, -.18, .0175], [.27, -.09, .0175]])
    plan = plan_region(capture, calibration, REGION, [[.10, .10], [.10, -.02], [.10, -.15]])
    assert len(plan['moves']) == 6 and plan['clear_complete_after'] == 3
    state = {n: list(p) for n, p in zip(NAMES, [[.22, 0., .0175], [.20, -.18, .0175], [.27, -.09, .0175]])}
    for i, move in enumerate(plan['moves']):
        target = move['target_world_m']
        assert all(math.dist(target[:2], p[:2]) > 2 * (BOX_RADIUS_M + .01)
                   for n, p in state.items() if n != move['object_name'])
        state[move['object_name']] = target
        if i == 2:
            assert all(p[0] + BOX_RADIUS_M + .01 < REGION[0] for p in state.values())
    assert state == dict(zip(NAMES, [[.22, 0., .0175], [.20, -.18, .0175], [.27, -.09, .0175]]))


def test_restore_uses_known_table_height_and_keeps_the_measured_visual_xy():
    positions = deepcopy(ANCHORS)
    positions[0] = [.222, .001, .019]
    plan = plan_region(*scene(positions=positions), REGION, STAGING)
    restore = next(m for m in plan['moves'] if m['phase'] == 'restore' and m['object_name'] == NAMES[0])
    assert restore['target_world_m'] == [.222, .001, .0175]


def test_truth_fields_never_affect_selection_or_targets():
    capture, calibration = scene()
    expected = plan_region(capture, calibration, REGION, STAGING)
    capture['world_state'] = {'objects': [{'name': 'target_box_c', 'truth': ANCHORS[0]}]}
    for frame in capture['frames']:
        for obj in frame['objects'].values():
            obj['truth_world_center_m'] = [999., 999., 999.]
    assert plan_region(capture, calibration, REGION, STAGING) == expected


@pytest.mark.parametrize('defect', ['status', 'no_frame', 'none_frame', 'missing_object',
    'extra_object', 'unavailable', 'reason', 'nan', 'bool', 'height', 'stale', 'future',
    'duplicate_stamp', 'camera', 'source', 'movement', 'bad_calibration'])
def test_bad_or_moving_capture_is_not_replaced_with_a_good_subset(defect):
    capture, calibration = scene()
    first = capture['frames'][0]
    obj = first['objects'][NAMES[0]]
    if defect == 'status': capture['status'] = 'UNAVAILABLE'
    elif defect == 'no_frame': capture['frames'].pop(0)
    elif defect == 'none_frame': capture['frames'][0] = None
    elif defect == 'missing_object': first['objects'].pop(NAMES[0])
    elif defect == 'extra_object': first['objects']['unmapped'] = deepcopy(obj)
    elif defect == 'unavailable': obj['available'] = False
    elif defect == 'reason': obj['reason'] = 'tag_ambiguous'
    elif defect == 'nan': obj['world_center_m'][0] = float('nan')
    elif defect == 'bool': obj['world_center_m'][0] = True
    elif defect == 'height': obj['world_center_m'][2] = .2
    elif defect == 'stale': first['image_age_at_receive_s'] = 1.1
    elif defect == 'future': first['image_age_at_receive_s'] = -.1
    elif defect == 'duplicate_stamp': capture['frames'][1]['image_stamp_ns'] = first['image_stamp_ns']
    elif defect == 'camera': first['camera_frame'] = 'other'
    elif defect == 'source': first['source'] = 'SIMULATION_GROUND_TRUTH'
    elif defect == 'movement': capture['frames'][1]['objects'][NAMES[0]]['world_center_m'][0] += .03
    elif defect == 'bad_calibration': calibration['tags'][1]['object'] = NAMES[0]
    with pytest.raises(ValueError):
        plan_region(capture, calibration, REGION, STAGING)


@pytest.mark.parametrize('region,margin,staging', [
    ([.28, .19, -.21, .04], .01, STAGING), ([.19, .28, .04, -.21], .01, STAGING),
    ([float('inf'), .28, -.21, .04], .01, STAGING), (REGION, -.01, STAGING),
    (REGION, BOX_RADIUS_M, STAGING), (REGION, True, STAGING),
    (REGION, .01, [[float('nan'), .1]]), (REGION, .01, [[.1, .1]] * 17),
])
def test_invalid_geometry_is_rejected(region, margin, staging):
    with pytest.raises(ValueError):
        plan_region(*scene(), region, staging, margin)


def cli(tmp_path, capture=None):
    report, calibration = scene()
    (tmp_path / 'capture.json').write_text(json.dumps(report if capture is None else capture))
    (tmp_path / 'vision.json').write_text(json.dumps(calibration))
    return [sys.executable, str(ROOT / 'scripts/plan_region.py'),
            '--observations', str(tmp_path / 'capture.json'), '--calibration', str(tmp_path / 'vision.json'),
            '--region', '.19', '.28', '-.21', '.04', '--staging', '.12', '.05',
            '--staging', '.12', '-.15', '--out', str(tmp_path / 'plan.json')]


def test_cli_writes_a_read_only_plan_and_refuses_to_overwrite(tmp_path):
    args = cli(tmp_path)
    result = subprocess.run(args, capture_output=True, text=True, check=True)
    report = json.loads(result.stdout)
    assert report['status'] == 'PLANNED' and len(report['moves']) == 4
    assert report['motion_dispatched'] is False and report['execution_ready'] is False
    assert report['input_sha256']['observations'] == hashlib.sha256((tmp_path / 'capture.json').read_bytes()).hexdigest()
    original = (tmp_path / 'plan.json').read_bytes()
    retry = subprocess.run(args, capture_output=True, text=True)
    assert retry.returncode == 2 and (tmp_path / 'plan.json').read_bytes() == original


@pytest.mark.parametrize('capture', [[], {'status': 'UNAVAILABLE'}])
def test_cli_invalid_input_returns_unavailable_with_no_partial_moves(tmp_path, capture):
    result = subprocess.run(cli(tmp_path, capture), capture_output=True, text=True)
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report['status'] == 'UNAVAILABLE' and 'moves' not in report
    assert report['motion_dispatched'] is False
