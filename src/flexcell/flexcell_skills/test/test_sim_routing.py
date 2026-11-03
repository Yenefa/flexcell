"""Routing summaries must report what the arms did, not what the winner was called."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
from sim_smoke import completion_expectation, summarize_routing


def row(action='PICK', policy='llm', trace=None, **extra):
    value = dict(action=action, policy=policy, policy_trace=trace)
    value.update(extra)
    return value


def leaf(**fields):
    return dict(fields)


def test_fsm_and_resume_rows_are_not_model_calls():
    rows = [row('OBSERVE', 'fsm', None), row('PICK', 'fsm', None),
            row('PLACE', 'fsm', None),
            row('VERIFY', 'fsm+resume', leaf(source='completion_check', fallback=False))]
    summary = summarize_routing(rows)
    assert summary['model_calls'] == 0
    assert summary['fast_calls'] == 0
    assert summary['slow_calls'] == 0
    assert summary['models'] == []


def test_a_fast_call_that_escalated_reports_both_arms():
    rows = [row('PICK', 'hybrid', dict(
        threshold=.7,
        source='llm',
        proposals=[dict(policy='jev', action='PICK', confidence=.9,
                        policy_trace=leaf(source='jev', backend='clef',
                                          model='clef-flash-q8_0')),
                   dict(policy='llm', action='PICK', confidence=.95,
                        policy_trace=leaf(source='llm', backend='deepseek-official',
                                          response_model='deepseek-flash'))]))]
    summary = summarize_routing(rows)
    assert (summary['fast_calls'], summary['slow_calls']) == (1, 1)
    assert summary['model_calls'] == 2
    assert summary['models'] == ['clef-flash-q8_0', 'deepseek-flash']
    assert summary['backends'] == ['clef', 'deepseek-official']


def test_a_hybrid_run_that_stayed_fast_reports_only_fast_calls():
    proposals = [dict(policy='jev', action=name, confidence=.93,
                      policy_trace=leaf(source='jev', model='clef-flash-q8_0'))
                 for name in ('PICK', 'PLACE', 'VERIFY')]
    rows = [row('PICK', 'hybrid', dict(threshold=.7, source='jev', proposals=proposals))]
    summary = summarize_routing(rows)
    assert summary['fast_calls'] == 3
    assert summary['slow_calls'] == 0
    assert summary['models'] == ['clef-flash-q8_0']


def test_a_slow_call_without_an_identity_is_still_a_call():
    rows = [row('PICK', 'llm', leaf(source='llm', fallback=False, tokens=11))]
    summary = summarize_routing(rows)
    assert summary['slow_calls'] == 1
    assert summary['models'] == []
    assert summary['calls_without_identity'] == 1


def test_a_fast_identity_comes_from_the_fast_schema():
    rows = [row('VERIFY', 'jev', leaf(source='jev', fallback=False, backend='clef',
                                      model='clef-flash-q8_0', model_sha256='a' * 64))]
    summary = summarize_routing(rows)
    assert summary['fast_calls'] == 1
    assert summary['models'] == ['clef-flash-q8_0']
    assert summary['backends'] == ['clef']
    assert summary['calls_without_identity'] == 0


def test_a_fallback_row_counts_no_model_call():
    rows = [row('OBSERVE', 'llm', leaf(source='fsm', fallback=True))]
    summary = summarize_routing(rows)
    assert summary['model_calls'] == 0
    assert summary['fallbacks'] == 1


@pytest.mark.parametrize('policy', ['fsm', 'llm', 'jev', 'hybrid'])
def test_resume_short_circuits_every_policy_to_one_verification(policy):
    assert completion_expectation(policy, True) == {'pick': 0, 'place': 0, 'verify': 1}


def test_only_the_fsm_must_carry_when_the_object_is_already_placed():
    assert completion_expectation('fsm', False) == {'pick': 1, 'place': 1, 'verify': 1}
    for policy in ('llm', 'jev', 'hybrid'):
        assert completion_expectation(policy, False) is None
