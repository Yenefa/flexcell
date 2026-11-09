"""Every configured box must be visible to MoveIt before the approach is planned."""
import pytest

from flexcell_skills import known_objects
from flexcell_skills import pick_server as module
from flexcell_skills.pick_server import PickServer


class RecordingScene:
    def __init__(self):
        self.added = []

    def add_box(self, name, position, size, frame='world', *, orientation=(0., 0., 0., 1.)):
        self.added.append((name, list(position), list(size), list(orientation), frame))
        return True, ''


@pytest.fixture(autouse=True)
def restore_defaults():
    yield
    known_objects.configure(known_objects.DEFAULT_OBJECTS)


def server(scene):
    value = PickServer.__new__(PickServer)
    value._size = [.035, .035, .035]
    value._scene = scene
    value.has_parameter = lambda _name: False
    return value


def test_the_target_and_every_configured_box_enter_at_the_measured_pose(monkeypatch):
    known_objects.configure(['target_box_a', 'target_box_b', 'target_box_c'])
    measured = {
        'target_box_b': ([.20, -.18, .0175], [0., 0., .1, .9949874371]),
        'target_box_c': ([.15, -.05, .0175], [0., 0., -.05, .9987492178]),
    }
    monkeypatch.setattr(module, 'sample_gz_pose',
                        lambda name, **_kwargs: (measured[name], None))
    scene = RecordingScene()

    synced, skipped = server(scene)._sync_scene_objects('target_box_a')

    assert synced == ['target_box_b', 'target_box_c']
    assert skipped == []
    added = {item[0]: item for item in scene.added}
    assert 'target_box_a' not in added
    assert added['target_box_c'][1] == pytest.approx([.15, -.05, .0175])
    assert added['target_box_c'][3] == pytest.approx([0., 0., -.05, .9987492178])
    assert added['target_box_b'][2] == pytest.approx([.035, .035, .035])


def test_a_configured_box_that_cannot_be_measured_is_reported(monkeypatch):
    known_objects.configure(['target_box_a', 'target_box_b', 'target_box_c'])
    monkeypatch.setattr(
        module, 'sample_gz_pose',
        lambda name, **_kwargs: (([.20, -.18, .0175], [0., 0., 0., 1.]), None)
        if name == 'target_box_b' else (None, 'model not seen in pose stream'))
    scene = RecordingScene()

    synced, skipped = server(scene)._sync_scene_objects('target_box_a')

    assert synced == ['target_box_b']
    assert skipped == [['target_box_c', 'model not seen in pose stream']]


def test_an_unconfigured_box_is_never_queried(monkeypatch):
    known_objects.configure(['target_box_a', 'target_box_b'])
    monkeypatch.setattr(
        module, 'sample_gz_pose',
        lambda name, **_kwargs: (([.20, -.18, .0175], [0., 0., 0., 1.]), None)
        if name == 'target_box_b' else pytest.fail('unconfigured object was sampled'))
    scene = RecordingScene()

    synced, skipped = server(scene)._sync_scene_objects('target_box_a')

    assert synced == ['target_box_b'] and skipped == []
