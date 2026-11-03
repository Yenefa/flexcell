"""The runner must be able to declare a real policy, and only what it declares."""
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
from sim_profile import DECISION_POLICIES, profile


def params(path):
    return yaml.safe_load(Path(path).read_text())['task_fsm_server']['ros__parameters']


def test_the_default_profile_still_declares_the_fsm(tmp_path):
    params_path, _world = profile(tmp_path / 'default')
    assert params(params_path)['decision_policy'] == 'fsm'


@pytest.mark.parametrize('policy', DECISION_POLICIES)
def test_every_declared_policy_reaches_the_task_node(tmp_path, policy):
    extra = {'hybrid_threshold': .7} if policy == 'hybrid' else {}
    params_path, _world = profile(tmp_path / policy, decision_policy=policy, **extra)
    declared = params(params_path)
    assert declared['decision_policy'] == policy
    if policy == 'hybrid':
        assert declared['hybrid_threshold'] == pytest.approx(.7)
    else:
        # The shipped YAML carries a default threshold; a non-hybrid run must not
        # overwrite it, and it is inert because the policy never routes through it.
        assert declared.get('hybrid_threshold') == pytest.approx(.7)


def test_an_unknown_policy_is_refused(tmp_path):
    with pytest.raises(ValueError, match='unknown decision policy'):
        profile(tmp_path / 'x', decision_policy='magic')


def test_hybrid_without_a_threshold_is_refused(tmp_path):
    with pytest.raises(ValueError, match='requires a declared threshold'):
        profile(tmp_path / 'y', decision_policy='hybrid')


def test_a_threshold_without_hybrid_is_refused(tmp_path):
    with pytest.raises(ValueError, match='belongs to the hybrid policy'):
        profile(tmp_path / 'z', decision_policy='llm', hybrid_threshold=.7)


def test_an_out_of_range_threshold_is_refused(tmp_path):
    for bad in (0., 1.5, -0.1):
        with pytest.raises(ValueError, match='threshold in'):
            profile(tmp_path / ('t%s' % str(bad).replace('.', '_')),
                    decision_policy='hybrid', hybrid_threshold=bad)
