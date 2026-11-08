"""Platform levers used by the real-Gazebo tasks (scripts/sim_profile.py)."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _load_sim_profile():
    path = ROOT / "scripts" / "sim_profile.py"
    spec = importlib.util.spec_from_file_location("sim_profile_lever", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_zone_2_pose_overrides_the_second_destination(tmp_path):
    profile = _load_sim_profile()
    params_path, _world = profile.profile(tmp_path, zone_2_pose=(0.45, 0.05, 0.0175))
    params = json.loads(Path(params_path).read_text()) if params_path.suffix == ".json" else None
    if params is None:
        import yaml
        params = yaml.safe_load(Path(params_path).read_text())
    node = params["task_fsm_server"]["ros__parameters"]
    assert node["zone_2_x"] == 0.45 and node["zone_2_y"] == 0.05


def test_zone_2_pose_rejects_malformed_input(tmp_path):
    profile = _load_sim_profile()
    with pytest.raises(ValueError):
        profile.profile(tmp_path, zone_2_pose=(0.45, 0.05))
