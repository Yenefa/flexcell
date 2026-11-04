"""Destination occupancy uses all observed objects, independently of transport."""
import copy
import math

import pytest

from flexcell_skills.contracts.safety_gate import (
    destination_clear, rejection_canonical_code)
from flexcell_skills.contracts.error_codes import ERR_SAFETY_REJECTED


def world():
    def box(name, position):
        return dict(name=name, klass='box', available=True, size=[.035]*3,
                    pose=dict(position=dict(zip('xyz', position)),
                              orientation=dict(x=0., y=0., z=0., w=1.)))
    return {'world_state': {'objects': [
        box('a', [.22, 0., .0175]), box('b', [.20, -.18, .0175])]}}


def test_occupied_destination_names_passive_object_and_is_typed():
    ok, reason = destination_clear(world(), 'b', [.22, 0., .0175])
    assert not ok and reason == 'destination_occupied:a'
    assert rejection_canonical_code(reason) == ERR_SAFETY_REJECTED


@pytest.mark.parametrize('target,goal', [
    ('a', [.12, -.15, .0175]), ('b', [.25, .05, .0175]),
    ('a', [.22, 0., .0175])])
def test_free_destinations_and_own_start_remain_usable(target, goal):
    value = world()
    before = copy.deepcopy(value)
    assert destination_clear(value, target, goal) == (True, None)
    assert value == before


def test_passive_box_orientation_changes_occupancy():
    value = world()
    a = value['world_state']['objects'][0]
    a['size'] = [.14, .02, .02]
    destination = [.22, .075, .0175]
    assert destination_clear(value, 'b', destination) == (True, None)
    a['pose']['orientation'] = dict(x=0., y=0., z=math.sqrt(.5), w=math.sqrt(.5))
    assert destination_clear(value, 'b', destination) == (False, 'destination_occupied:a')


@pytest.mark.parametrize('bad', ['unavailable', 'size', 'position', 'orientation', 'missing'])
def test_unknown_passive_geometry_cannot_establish_a_free_destination(bad):
    value = world()
    a = value['world_state']['objects'][0]
    if bad == 'unavailable':
        a['available'] = False
    elif bad == 'size':
        a['size'][0] = 0.
    elif bad == 'position':
        a['pose']['position']['x'] = float('nan')
    elif bad == 'orientation':
        a['pose']['orientation']['w'] = 0.
    else:
        del a['pose']
    ok, reason = destination_clear(value, 'b', [.25, .05, .0175])
    assert not ok and reason == 'destination_geometry_unavailable'
    assert rejection_canonical_code(reason) == ERR_SAFETY_REJECTED
