import json
import multiprocessing

import pytest

from flexcell_skills.inference_budget import BudgetExceeded, InferenceBudget


URL = 'https://api.deepseek.com/chat/completions'


def request():
    return dict(model='deepseek-flash', thinking={'type': 'disabled'}, max_tokens=512,
                messages=[dict(role='user', content='x' * 20_000)])


def exhaust(path):
    budget = InferenceBudget(path)
    while True:
        try:
            budget.reserve(URL, request())
        except BudgetExceeded:
            return


def test_parallel_processes_cannot_oversubscribe_or_reset_budget(tmp_path):
    path = tmp_path / 'budget.json'
    workers = [multiprocessing.Process(target=exhaust, args=(path,)) for _ in range(3)]
    for process in workers:
        process.start()
    for process in workers:
        process.join(10)
        assert process.exitcode == 0
    state = json.loads(path.read_text())
    assert 0 < state['committed_upper_bound_microyuan'] <= 5_000_000
    with pytest.raises(BudgetExceeded):
        InferenceBudget(path).reserve(URL, request())


def test_usage_releases_only_unused_reservation_and_unknown_usage_stays_reserved(tmp_path):
    path = tmp_path / 'budget.json'
    budget = InferenceBudget(path)
    first = budget.reserve(URL, request())
    second = budget.reserve(URL, request())
    budget.settle(first, dict(usage=dict(prompt_tokens=100, completion_tokens=50)))
    budget.settle(second, {})
    state = json.loads(path.read_text())
    assert state['committed_upper_bound_microyuan'] == 600 + state['calls'][1]['reserved_microyuan']
    with pytest.raises(ValueError):
        budget.reserve(URL, dict(request(), model='deepseek-v4-pro'))


def test_full_reasoning_reserves_and_settles_against_same_five_yuan_cap(tmp_path):
    path = tmp_path / 'budget.json'
    budget = InferenceBudget(path)
    payload = dict(request(), thinking={'type': 'enabled'}, reasoning_effort='max', max_tokens=32768)
    call_id = budget.reserve(URL, payload)
    state = json.loads(path.read_text())
    assert state['calls'][0]['reserved_microyuan'] >= 32768 * 8
    assert state['limit_microyuan'] == 5_000_000
    budget.settle(call_id, dict(usage=dict(prompt_tokens=2000, completion_tokens=16000)))
    assert json.loads(path.read_text())['committed_upper_bound_microyuan'] == 132000
    for bad in (dict(payload, max_tokens=65537), dict(payload, max_tokens=True),
                dict(payload, thinking={'type': 'disabled'})):
        with pytest.raises(ValueError):
            budget.reserve(URL, bad)
