#!/usr/bin/env python3
"""Warm both actual endpoints on a recorded input. Does not execute ROS skills.

This is endpoint readiness evidence, never an episode or behavior acceptance.
Long warm-up timeout is recorded separately from production policy timeouts.
"""
import argparse
import dataclasses
import hashlib
import json
import os
import time
import urllib.request

from flexcell_skills.contracts.episode import (
    _constraints_from_dict, _goal_from_dict, _history_from_dicts)
from flexcell_skills.jev_backends import LocalReproductionBackend
from flexcell_skills.jev_policy import JevPolicy
from flexcell_skills.llm_policy import LLMPolicy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--episode', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--policy', choices=('both', 'jev', 'llm'), default='both')
    args = ap.parse_args()
    for name, value in dict(FLEXCELL_JEV_ENDPOINT='http://127.0.0.1:18081/v1/chat/completions',
                           FLEXCELL_JEV_MODEL='flexcell-fast',
                           FLEXCELL_LLM_ENDPOINT='http://127.0.0.1:18082/v1/chat/completions',
                           FLEXCELL_LLM_MODEL='flexcell-slow').items():
        os.environ.setdefault(name, value)
    raw = open(args.episode, 'rb').read()
    pi = next(s['policy_input'] for s in json.loads(raw)['steps']
              if s['policy_input']['world_state_canonical'] is not None)
    inputs = (json.loads(pi['world_state_canonical']), _goal_from_dict(pi['goal']),
              _constraints_from_dict(pi['constraints']), _history_from_dicts(pi['history']))
    calls = []

    def transport(url, payload, timeout):
        call = {'endpoint': url, 'payload': payload, 'timeout_s': timeout}
        calls.append(call)
        t0 = time.perf_counter_ns()
        req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                     headers={'Content-Type': 'application/json'})
        try:
            if url == os.environ['FLEXCELL_LLM_ENDPOINT']:
                call['response'] = LLMPolicy._http(url, payload, timeout)
            else:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    call['response'] = json.load(response)
            return call['response']
        except Exception as exc:
            call['error'] = type(exc).__name__
            call['http_status'] = getattr(exc, 'code', None)
            raise
        finally:
            call['latency_ms'] = (time.perf_counter_ns() - t0) / 1e6

    results = []
    policies = []
    if args.policy in ('both', 'jev'):
        policies.append(JevPolicy(LocalReproductionBackend(transport=transport, timeout_s=60)))
    if args.policy in ('both', 'llm'):
        policies.append(LLMPolicy(transport=transport, timeout_s=60))
    for policy in policies:
        decision = policy.decide(*inputs)
        results.append({'policy': policy.name, 'version': policy.version,
                        'decision': dataclasses.asdict(decision), 'stats': policy.stats})
        print(json.dumps(results[-1]), flush=True)
    evidence = dict(stage='ENDPOINT_WARMUP_NOT_BEHAVIOR_ACCEPTANCE',
                    input_episode_sha256=hashlib.sha256(raw).hexdigest(),
                    input=pi, calls=calls, results=results)
    with open(args.out, 'w') as stream:
        json.dump(evidence, stream, indent=2)
    return 0 if all(not r['decision']['policy_trace'].get('fallback') for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
