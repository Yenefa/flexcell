"""Slow adapter contract checks; live behavior evidence is stored separately."""
import json
from unittest.mock import Mock, patch
import pytest

from flexcell_skills.decision_policy import Constraints, HistoryRecord, TaskGoal
from flexcell_skills.llm_policy import LLMPolicy


@pytest.fixture(autouse=True)
def default_backend_environment(monkeypatch):
    for name in ('RESPONSE_FORMAT', 'THINKING', 'BACKEND', 'TIMEOUT_S', 'MAX_TOKENS', 'API_KEY_FILE', 'BUDGET_FILE'):
        monkeypatch.delenv('FLEXCELL_LLM_' + name, raising=False)


def inputs():
    return ({'world_state': {'objects': [], 'carry': {'engaged': False}}},
            TaskGoal('g', 's', (('a', 'z'),)),
            Constraints(frozenset(('OBSERVE', 'PICK', 'PLACE', 'VERIFY', 'ABORT')),
                        1, 0.06, 'demo_slow', 0),
            (HistoryRecord('OBSERVE', 'a', 0, 0, 1, 1, 'ev'),))


def test_slow_model_supplies_target_reason_and_own_telemetry():
    transport = Mock(return_value={'choices': [{'message': {'content': json.dumps({
        'action': 'PICK', 'target': 'a', 'confidence': .8,
        'reason_code': 'PLAN_NEXT', 'explanation': 'observed object'})}}],
        'usage': {'total_tokens': 42, 'prompt_tokens': 20, 'completion_tokens': 22}})
    policy = LLMPolicy(transport=transport)
    policy._endpoint = 'http://localhost/v1/chat/completions'
    decision = policy.decide(*inputs())
    assert (decision.action, decision.target, decision.reason_code) == ('PICK', 'a', 'PLAN_NEXT')
    assert decision.policy_trace['source'] == 'llm'
    assert decision.policy_trace['tokens'] == 42
    payload = transport.call_args.args[1]
    assert payload['response_format']['type'] == 'json_schema'
    assert payload['response_format']['json_schema']['schema']['properties']['target']['enum'] == ['', 'a']


def test_parse_failure_has_typed_fsm_provenance():
    policy = LLMPolicy(transport=Mock(return_value={'choices': []}))
    decision = policy.decide(*inputs())
    assert decision.action == 'PICK'
    assert decision.policy_trace['source'] == 'fsm'
    assert decision.policy_trace['failure'] == 'parse_error'


def test_backend_failure_with_model_history_outside_fsm_grammar_aborts():
    policy = LLMPolicy(transport=Mock(side_effect=TimeoutError))
    world, goal, constraints, history = inputs()
    history += (HistoryRecord('OBSERVE', 'a', 0, 0, 1, 2, 'ev2'),)
    decision = policy.decide(world, goal, constraints, history)
    assert decision.action == 'ABORT'
    assert decision.reason_code == 'POLICY_FAILURE'
    assert decision.policy_trace['fallback'] is True


def test_gateway_json_mode_and_response_provenance(monkeypatch):
    monkeypatch.setenv('FLEXCELL_LLM_RESPONSE_FORMAT', 'json_object')
    monkeypatch.setenv('FLEXCELL_LLM_THINKING', 'disabled')
    monkeypatch.setenv('FLEXCELL_LLM_BACKEND', 'opencode-zen')
    monkeypatch.setenv('FLEXCELL_LLM_TIMEOUT_S', '30')
    monkeypatch.setenv('FLEXCELL_LLM_MAX_TOKENS', '512')
    reply = {'model': 'deepseek-v4.1-flash', 'choices': [{'finish_reason': 'stop', 'message': {
        'content': json.dumps(dict(action='PICK', target='a', confidence=.9,
                                   reason_code='PLAN_NEXT', explanation='observed'))}}]}
    transport = Mock(return_value=reply)
    policy = LLMPolicy(transport=transport)
    policy._endpoint = 'https://opencode.ai/zen/v1/chat/completions'
    decision = policy.decide(*inputs())
    _, payload, timeout = transport.call_args.args
    assert timeout == 30 and payload['max_tokens'] == 512
    assert payload['response_format'] == {'type': 'json_object'}
    assert payload['thinking'] == {'type': 'disabled'}
    assert decision.policy_trace['response_model'] == 'deepseek-v4.1-flash'
    assert decision.policy_trace['backend'] == 'opencode-zen'
    reply['choices'][0]['message']['content'] = json.dumps(dict(
        action='PICK', target='unknown', confidence=.9, reason_code='PLAN_NEXT'))
    assert policy.decide(*inputs()).policy_trace['failure'] == 'parse_error'


def test_gateway_credential_only_in_request_header(tmp_path, monkeypatch):
    key = tmp_path / 'key'
    key.write_text('test-credential')
    monkeypatch.setenv('FLEXCELL_LLM_API_KEY_FILE', str(key))
    with patch('urllib.request.urlopen') as urlopen:
        urlopen.return_value.__enter__.return_value.read.return_value = b'{"choices":[]}'
        assert LLMPolicy._http('https://opencode.ai/zen/v1/chat/completions', {'model': 'test'}, 3) == {'choices': []}
        request = urlopen.call_args.args[0]
        assert request.get_header('Authorization') == 'Bearer test-credential'
        assert b'test-credential' not in request.data
