"""Persistent, process-safe RMB reservations for the authorized DeepSeek run.

Use published peak, uncached prices (2 RMB/M input, 8 RMB/M output), ignoring
cache discounts. Unknown network outcomes keep their entire reservation. This
is an upper bound on charges, not an invoice. The credential is never logged.
"""
import fcntl
import json
import os
from pathlib import Path
import time
import uuid


class BudgetExceeded(RuntimeError):
    pass


class InferenceBudget:
    LIMIT_MICROYUAN = 5_000_000
    INPUT_MICROYUAN = 2
    OUTPUT_MICROYUAN = 8
    MAX_OUTPUT_TOKENS = 65536

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _update(self, operation):
        with open(str(self.path) + '.lock', 'a') as lock:
            os.chmod(lock.name, 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX)
            state = (json.loads(self.path.read_text()) if self.path.exists() else
                     dict(currency='CNY', limit_microyuan=self.LIMIT_MICROYUAN,
                          pricing_source='https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',
                          pricing_checked='2026-10-01', input_microyuan_per_token=2,
                          output_microyuan_per_token=8, calls=[]))
            if (state['limit_microyuan'] != self.LIMIT_MICROYUAN
                    or state['input_microyuan_per_token'] != self.INPUT_MICROYUAN
                    or state['output_microyuan_per_token'] != self.OUTPUT_MICROYUAN):
                raise ValueError('budget or tariff mismatch')
            result = operation(state)
            state['committed_upper_bound_microyuan'] = sum(
                c.get('settled_microyuan', c['reserved_microyuan']) for c in state['calls'])
            temporary = self.path.with_name(self.path.name + '.' + uuid.uuid4().hex + '.tmp')
            with open(temporary, 'x') as stream:
                os.chmod(temporary, 0o600)
                json.dump(state, stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            return result

    def reserve(self, endpoint, payload):
        if (endpoint != 'https://api.deepseek.com/chat/completions'
                or payload.get('model') != 'deepseek-flash'
                or payload.get('thinking') not in ({'type': 'disabled'}, {'type': 'enabled'})):
            raise ValueError('budget tariff only permits official deepseek-flash')
        effort = payload.get('reasoning_effort')
        if effort not in (None, 'none', 'low', 'high', 'max'):
            raise ValueError('unsupported reasoning effort')
        if (payload['thinking']['type'] == 'disabled' and effort not in (None, 'none')):
            raise ValueError('thinking and reasoning effort conflict')
        if payload['thinking']['type'] == 'enabled' and effort == 'none':
            raise ValueError('thinking and reasoning effort conflict')
        maximum = payload.get('max_tokens')
        if type(maximum) is not int or not 1 <= maximum <= self.MAX_OUTPUT_TOKENS:
            raise ValueError('budget requires output cap <= 65536 tokens')
        # UTF-8 bytes overestimate byte-based text tokenization. Add ample chat
        # framing overhead and double the whole reservation as safety margin.
        input_bound = len(json.dumps(payload['messages'], ensure_ascii=False).encode()) + 4096
        reservation = 2 * (input_bound * self.INPUT_MICROYUAN + maximum * self.OUTPUT_MICROYUAN)

        def operation(state):
            committed = sum(c.get('settled_microyuan', c['reserved_microyuan']) for c in state['calls'])
            if committed + reservation > self.LIMIT_MICROYUAN:
                raise BudgetExceeded('DeepSeek RMB 5 budget exhausted; no request sent')
            call_id = uuid.uuid4().hex
            state['calls'].append(dict(id=call_id, created_at_unix=time.time(),
                                      model=payload['model'], input_token_bound=input_bound,
                                      thinking=payload['thinking']['type'], reasoning_effort=effort,
                                      max_output_tokens=maximum, reserved_microyuan=reservation,
                                      status='RESERVED_OR_UNKNOWN'))
            return call_id

        return self._update(operation)

    def settle(self, call_id, response):
        usage = response.get('usage') or {}
        prompt, completion = usage.get('prompt_tokens'), usage.get('completion_tokens')
        if (not isinstance(prompt, int) or not isinstance(completion, int)
                or prompt < 0 or completion < 0):
            return {'call_id': call_id, 'status': 'RESERVED_OR_UNKNOWN'}

        def operation(state):
            call = next(c for c in state['calls'] if c['id'] == call_id)
            cost = prompt * self.INPUT_MICROYUAN + completion * self.OUTPUT_MICROYUAN
            if (prompt > call['input_token_bound'] or completion > call['max_output_tokens']
                    or cost > call['reserved_microyuan']):
                raise ValueError('provider usage exceeded reservation assumptions')
            call.update(status='USAGE_SETTLED_AT_PEAK_UNCACHED_CEILING',
                        prompt_tokens=prompt, completion_tokens=completion,
                        settled_microyuan=cost, response_model=response.get('model'),
                        provider_request_id=response.get('id'))
            return dict(call_id=call_id, upper_bound_cny=cost / 1_000_000,
                        status=call['status'])

        return self._update(operation)
