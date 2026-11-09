"""A first-attempt qualification must not silently borrow production recovery."""
import hashlib
import json
from pathlib import Path
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
from sim_profile import profile


def semantic(path):
    result = yaml.safe_load(path.read_text())
    for node in result.values():
        for key in ('log_dir', 'episode_dir'):
            if key in node.get('ros__parameters', {}): node['ros__parameters'][key] = '$RUN/' + key
    return result


def test_historical_profile_retains_its_declared_hash_and_recovery(tmp_path):
    p, w = profile(tmp_path/'old', 'detachable_joint', False, 'mtc', 11., .002,
                   contact_trace=True, release_clearance_m=.05)
    declaration = json.loads((ROOT/'infra/joint-contact-ci-smoke.json').read_text())
    assert hashlib.sha256(w.read_bytes()).hexdigest() == declaration['world_sha256']
    assert hashlib.sha256(json.dumps(semantic(p), sort_keys=True).encode()).hexdigest() == declaration['semantic_config_sha256']
    assert semantic(p)['task_fsm_server']['ros__parameters']['recovery_budget'] == 1


def test_new_qualification_has_zero_recovery_and_unchanged_world(tmp_path):
    p, w = profile(tmp_path/'new', 'detachable_joint', False, 'mtc', 11., .002,
                   contact_trace=True, release_clearance_m=.05, qualification_no_recovery=True)
    declaration = json.loads((ROOT/'infra/joint-contact-position-goal.json').read_text())
    assert semantic(p)['task_fsm_server']['ros__parameters']['recovery_budget'] == 0
    assert hashlib.sha256(w.read_bytes()).hexdigest() == declaration['world_sha256']
    assert hashlib.sha256(json.dumps(semantic(p), sort_keys=True).encode()).hexdigest() == declaration['semantic_config_sha256']


def test_unrelated_runtime_cannot_enable_the_qualification_override(tmp_path):
    with pytest.raises(ValueError, match='no-recovery qualification'):
        profile(tmp_path/'bad', qualification_no_recovery=True)
