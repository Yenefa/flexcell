"""Normal sessions and smoke runs must declare the same release contract."""
import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
from sim_profile import profile


@pytest.mark.parametrize('scene,camera', [(None, False), ('three_boxes', False),
                                        ('tagged_three_boxes', True)])
@pytest.mark.parametrize('limit', [0., .001, 5., 45.])
def test_each_scene_declares_one_solver_and_gate_limit(tmp_path, scene, camera, limit):
    p, _ = profile(tmp_path / 'run', backend='detachable_joint', skill_backend='mtc',
                   camera=camera, scene=scene, level_release_tolerance_deg=limit)
    config = yaml.safe_load(p.read_text())
    assert config['mtc_planner']['ros__parameters']['level_release_pitch_tolerance_deg'] == limit
    assert config['place_server']['ros__parameters']['max_release_tilt_deg'] == limit
    assert config['place_server']['ros__parameters']['place_tolerance_m'] == .06
    assert config['move_to_pose_server']['ros__parameters']['enable_mtc_handoff'] is True


@pytest.mark.parametrize('backend,skill', [('teleport', 'legacy'), ('velocity_servo', 'legacy'),
                                          ('detachable_joint', 'legacy'), ('teleport', 'mtc'),
                                          ('velocity_servo', 'mtc')])
def test_unsupported_backends_are_rejected_before_writing(tmp_path, backend, skill):
    out = tmp_path / 'invalid'
    with pytest.raises(ValueError, match='mtc.*detachable_joint'):
        profile(out, backend=backend, skill_backend=skill, level_release_tolerance_deg=5.)
    assert not out.exists()


@pytest.mark.parametrize('limit', [-.001, 45.001, float('nan'), float('inf'),
                                  -float('inf'), True, '5'])
def test_invalid_limits_are_rejected_before_writing(tmp_path, limit):
    out = tmp_path / 'invalid'
    with pytest.raises(ValueError, match='finite number'):
        profile(out, backend='detachable_joint', skill_backend='mtc', level_release_tolerance_deg=limit)
    assert not out.exists()


def test_level_release_changes_no_world_geometry_or_unrelated_parameters(tmp_path):
    old, old_world = profile(tmp_path / 'old', backend='detachable_joint', skill_backend='mtc')
    new, new_world = profile(tmp_path / 'new', backend='detachable_joint', skill_backend='mtc',
                             level_release_tolerance_deg=5.)
    assert old_world.read_bytes() == new_world.read_bytes()
    before, after = yaml.safe_load(old.read_text()), yaml.safe_load(new.read_text())
    assert 'mtc_planner' not in before
    after.pop('mtc_planner')
    after['place_server']['ros__parameters'].pop('max_release_tilt_deg')
    for config in (before, after):
        for node in config.values():
            for key in ('log_dir', 'episode_dir'):
                if key in node.get('ros__parameters', {}):
                    node['ros__parameters'][key] = '$RUN/' + key
    assert before == after


def test_cli_generates_a_camera_profile_and_preserves_existing_files(tmp_path):
    command = [sys.executable, str(ROOT / 'scripts/sim_profile.py'), '--out', str(tmp_path / 'scene'),
               '--backend', 'detachable_joint', '--skill-backend', 'mtc', '--camera',
               '--scene', 'tagged_three_boxes', '--level-release-tolerance-deg', '5']
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    paths = json.loads(result.stdout)
    assert set(paths) == {'params', 'world', 'vision'}
    original = {k: Path(p).read_bytes() for k, p in paths.items()}
    retry = subprocess.run(command, capture_output=True, text=True)
    assert retry.returncode == 2
    assert {k: Path(p).read_bytes() for k, p in paths.items()} == original
    config = yaml.safe_load(original['params'])
    assert config['observe_server']['ros__parameters']['tracked_objects'] == [
        'target_box_a', 'target_box_b', 'target_box_c']
    assert config['mtc_planner']['ros__parameters']['level_release_pitch_tolerance_deg'] == 5.
    assert config['place_server']['ros__parameters']['max_release_tilt_deg'] == 5.


def test_cli_rejects_level_release_with_the_default_backend(tmp_path):
    out = tmp_path / 'bad'
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/sim_profile.py'), '--out', str(out),
                             '--level-release-tolerance-deg', '5'], capture_output=True, text=True)
    assert result.returncode == 2 and 'mtc' in result.stderr
    assert not out.exists()


def test_smoke_flag_uses_shared_profile_validation_before_startup(tmp_path, monkeypatch):
    import sim_smoke
    monkeypatch.setattr(sys, 'argv', ['sim_smoke', '--out', str(tmp_path),
                                     '--level-release-tolerance-deg', '5'])
    monkeypatch.setattr(sim_smoke.subprocess, 'Popen', lambda *a, **k: pytest.fail('stack started'))
    with pytest.raises(ValueError, match='mtc.*detachable_joint'):
        sim_smoke.main()
    assert not list(tmp_path.rglob('params.yaml'))
