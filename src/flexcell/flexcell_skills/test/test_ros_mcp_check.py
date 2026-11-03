"""Transport success must never conceal a failed or empty Observe result."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))
from ros_mcp_check import action_fields, observed_world, tool_value


def observation():
    return dict(success=True, status=4, result=dict(outcome=0, error_code=0,
                world_state=dict(objects=[dict(name='target_box_a', available=True)])))


def test_transport_success_requires_typed_robot_success():
    value = observation()
    assert observed_world(value)['objects'][0]['name'] == 'target_box_a'
    for key, bad in [('outcome', 1), ('error_code', 2), ('outcome', False)]:
        failed = deepcopy(value)
        failed['result'][key] = bad
        with pytest.raises(RuntimeError, match='did not succeed'):
            observed_world(failed)
    value['status'] = 6
    with pytest.raises(RuntimeError, match='did not succeed'):
        observed_world(value)


@pytest.mark.parametrize('objects', [[], [dict(name='target_box_a', available=False)]])
def test_missing_or_unavailable_measurements_cannot_be_ready(objects):
    value = observation()
    value['result']['world_state']['objects'] = objects
    with pytest.raises(RuntimeError):
        observed_world(value)


def test_tool_payload_errors_cannot_be_ready():
    reply = SimpleNamespace(isError=False, structuredContent={'error': 'not connected'}, content=[])
    with pytest.raises(RuntimeError, match='not connected'):
        tool_value(reply)


def test_verify_fields_survive_structured_content_and_json_text():
    fields = dict(outcome=0, error_code=0, verified=True, has_measured_pose=True,
                  position_error_m=.002229)
    for result in [fields, json.dumps(fields)]:
        payload = dict(success=True, status=4, result=result)
        for reply in [SimpleNamespace(isError=False, structuredContent=payload, content=[]),
                      SimpleNamespace(isError=False, structuredContent=None,
                                      content=[SimpleNamespace(type='text', text=json.dumps(payload))])]:
            assert action_fields(tool_value(reply)) == fields


def test_missing_verify_measurement_is_not_fabricated():
    assert 'verified' not in action_fields(dict(result=dict(outcome=0)))
    for result in [None, [], 'null']:
        with pytest.raises(RuntimeError, match='missing or not an object'):
            action_fields(dict(result=result))
