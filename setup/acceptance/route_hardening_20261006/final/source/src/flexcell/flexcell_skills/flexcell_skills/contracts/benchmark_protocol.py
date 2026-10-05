"""The frozen benchmark definition shared by runner and episode producer."""
import hashlib
import json
from pathlib import Path


def load_protocol():
    raw = Path(__file__).with_name('benchmark_protocol_v2.json').read_bytes()
    spec = json.loads(raw)
    return spec, hashlib.sha256(raw).hexdigest()


def check_scenario_execution(spec, episode):
    """Check that the intended fault/target was exercised, not just FAILED."""
    steps = episode.get('steps', [])
    injected = [s for s in steps if (s.get('executor_result') or {}).get(
        'detail', '').startswith('injected failure')]
    target = spec.get('injected_object')
    if target:
        if not injected:
            return False, 'required injection was never applied'
        if any((s.get('policy_output') or {}).get('target') != target for s in injected):
            return False, 'injection applied to the wrong object'
        if ':once' in spec['inject'] and len(injected) != 1:
            return False, 'once injection applied more than once'
    action = spec.get('required_failed_action')
    if action and not any((s.get('policy_output') or {}).get('action') == action
                          and (s.get('executor_result') or {}).get('outcome') == 1
                          for s in steps):
        return False, 'required %s failure was not exercised' % action
    error = spec.get('required_task_error')
    if error is not None and episode.get('final_state', {}).get('error_code') != error:
        return False, 'required task error %s was not produced' % error
    return True, ''
