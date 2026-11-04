"""A third same-spec box must be a configuration change, not a code change."""
import pytest

from flexcell_skills import known_objects
from flexcell_skills.contracts.injection import parse_false_attach
from flexcell_skills.joint_follow import JointFollowMonitor, PrepositionLatch


@pytest.fixture(autouse=True)
def restore_defaults():
    yield
    known_objects.configure(known_objects.DEFAULT_OBJECTS)


def test_the_shipped_set_is_still_a_and_b():
    known_objects.configure(known_objects.DEFAULT_OBJECTS)
    assert known_objects.known() == ['target_box_a', 'target_box_b']
    with pytest.raises(ValueError):
        known_objects.require('target_box_c')


def test_configuring_a_third_box_makes_every_validator_accept_it():
    known_objects.configure(['target_box_a', 'target_box_b', 'target_box_c'])
    assert known_objects.require('target_box_c') == 'target_box_c'

    follow = JointFollowMonitor()
    follow.arm('target_box_c', 'a' * 32)          # the monitor accepts the new name
    assert follow.summary()['object'] == 'target_box_c'

    spec = parse_false_attach('target_box_c:0.03', 'detachable_joint')
    assert spec['object'] == 'target_box_c'

    assert set(PrepositionLatch().buffer) == {'target_box_a', 'target_box_b', 'target_box_c'}


def test_an_unknown_box_is_still_refused():
    known_objects.configure(['target_box_a', 'target_box_b', 'target_box_c'])
    with pytest.raises(ValueError):
        JointFollowMonitor().arm('target_box_d', 'a' * 32)
    with pytest.raises(ValueError):
        parse_false_attach('target_box_d:0.03', 'detachable_joint')


def test_an_empty_object_list_is_refused():
    with pytest.raises(ValueError):
        known_objects.configure([])
