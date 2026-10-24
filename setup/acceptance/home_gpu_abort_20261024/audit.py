#!/usr/bin/env python3
"""Recompute the fixed five-case functional receipt without robot/model calls."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


def audit(root):
    load = lambda name: json.loads((root / name).read_text().lstrip('\ufeff'))
    rows = [json.loads(line) for line in (root / 'batch.jsonl').read_text().splitlines()]
    assert Counter(row['scenario'] for row in rows) == {'S4': 2, 'S5': 2, 'S1': 1}
    deployment = load('deployment.json')
    identity = load('identity.json')
    owner = load('owner.json')
    shutdown = load('shutdown.json')
    fingerprint = deployment['runtime_fingerprint']
    expected_model = deployment['active_backends']['fast']
    assert identity['weights']['sha256'] == expected_model['model_sha256']
    calibration_sha = hashlib.sha256((root / 'calibration.json').read_bytes()).hexdigest()
    assert calibration_sha == expected_model['calibration_sha256']
    mapping = load('episode_map.json')
    by_original = {entry['original_path']: entry for entry in mapping}
    model_calls = []
    results = []
    for row in rows:
        assert row['policy'] == 'jev' and row['stage'] == 'smoke'
        assert not row['harness_error'] and row['scenario_exercised']
        assert row['outcome'] == row['expected']
        assert row['runtime_fingerprint'] == fingerprint
        entry = by_original[row['episode']]
        raw = (root / entry['archived_path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == entry['sha256']
        episode = json.loads(raw)
        assert episode['runtime_fingerprint'] == fingerprint
        calls = []
        for index, step in enumerate(episode['steps']):
            output = step['policy_output']
            trace = output['policy_trace']
            if index == 0:
                assert output['action'] == 'OBSERVE'
                assert step['policy_input']['world_state_canonical'] is None
                assert trace['source'] == 'fsm' and trace['fallback'] is True
                assert trace['failure'] == 'no world state'
                continue
            assert trace['source'] == 'jev' and trace['fallback'] is False
            assert trace['backend'] == 'clef'
            assert trace['model'] == expected_model['model']
            assert trace['model_sha256'] == expected_model['model_sha256']
            assert trace['calibration_sha256'] == calibration_sha
            assert type(trace['tokens']) is int and trace['tokens'] > 0
            raw_input = re.search(r'"input_tokens":\s*(\d+)', output['explanation'])
            assert raw_input and int(raw_input.group(1)) == trace['tokens']
            calls.append({'seq': step['seq'], 'action': output['action'],
                          'tokens': trace['tokens'], 'source': trace['source']})
        assert len(calls) == row['model_decisions']
        model_calls.extend(calls)
        final = episode['final_state']
        if row['scenario'] == 'S4':
            assert final['error_code'] == 50
            last = episode['steps'][-1]['policy_input']['history'][-1]
            assert last['action'] == 'PLACE' and last['outcome'] != 0
            cause = {10: 'ERR_IK_UNREACHABLE', 30: 'ERR_MOTION_FAILED'}[last['error_code']]
            assert ('previous_skill=PLACE cause=%s legacy_error_code=%d' %
                    (cause, last['error_code'])) in final['detail']
        elif row['scenario'] == 'S5':
            assert final['error_code'] == 51
            assert 'previous_skill=PICK cause=ERR_GRASP_FAILED legacy_error_code=23' in final['detail']
            assert sum(s['policy_output']['action'] == 'PICK' for s in episode['steps']) == 2
            assert all(s['policy_input']['constraints']['recovery_budget'] == 1
                       for s in episode['steps'])
        else:
            assert final['error_code'] == 0 and final['outcome'] == '0'
            assert final['object_a_at_zone'] and final['object_b_at_zone']
            assert not any('RECOVERY:' in item for item in final['fsm_trace'])
            assert sum(s['policy_output']['action'] == 'PICK' for s in episode['steps']) == 2
        results.append({'scenario': row['scenario'], 'run': row['run'],
                        'outcome': row['outcome'], 'task_error_code': final['error_code'],
                        'model_decisions': calls})
    assert shutdown['pid'] == owner['pid']
    assert shutdown['exited'] and shutdown['watchdog_exited']
    assert shutdown['port_11435_listening'] is False
    assert shutdown['remaining_inference_processes'] == []
    assert 'offloaded 33/33 layers to GPU' in (root / 'server_stderr.log').read_text()
    actual_context = owner['arguments'][owner['arguments'].index('-c') + 1]
    return {'status': 'FUNCTIONAL_REGRESSION_PASS', 'episodes': len(rows),
            'runtime_head': load('run_status.json')['head'],
            'runtime_fingerprint': fingerprint, 'results': results,
            'model_decisions': len(model_calls),
            'recorded_tokens': sum(call['tokens'] for call in model_calls),
            'model_weight_sha256': identity['weights']['sha256'],
            'gpu': identity['gpu'], 'shutdown': shutdown,
            'context_metadata': {'legacy_manifest_value': deployment['server_context_tokens'],
                                 'observed_server_argument': int(actual_context),
                                 'discrepancy_retained': deployment['server_context_tokens'] != int(actual_context)},
            'full_raw_model_responses_archived': False,
            'model_replay': 'NOT_RUN',
            'scope': 'Five functional cases only; no baseline qualification or historical replay'}


if __name__ == '__main__':
    print(json.dumps(audit(Path(__file__).resolve().parent), indent=2, ensure_ascii=False))
