#!/usr/bin/env python3
"""Local frozen-model evaluation and Jev calibration; never dispatches ROS.

Historical episodes from other models are counterfactual evaluations. A strict
model replay requires a matching frozen backend identity in the source episode.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request

REPO = Path(__file__).resolve().parents[1]
from flexcell_skills.canonical_state import deserialize_envelope
from flexcell_skills.contracts.episode import (
    _goal_from_dict, _constraints_from_dict, _history_from_dicts, decision_to_dict)
from flexcell_skills.contracts.metrics import wilson
from flexcell_skills.decision_policy import FSMPolicy, PolicyStateError
from flexcell_skills.jev_backends import LocalReproductionBackend
from flexcell_skills.jev_policy import JevPolicy
from flexcell_skills.llm_policy import LLMPolicy
from flexcell_skills.confidence_calibration import prompt_digest


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def inputs(step):
    pi = step['policy_input']
    text = pi['world_state_canonical']
    if text is not None:
        deserialize_envelope(text)  # refuse unknown schemas
    return (json.loads(text) if text is not None else None,
            _goal_from_dict(pi['goal']), _constraints_from_dict(pi['constraints']),
            _history_from_dicts(pi['history']))


def local_profile(arm):
    base = Path.home()/'.local/share/flexcell/inference/linux'
    saved = json.loads((base/(arm+'_server.json')).read_text())
    # Only an owned loopback server with verified weights/runtime is eligible.
    args = saved['arguments']
    actual = Path('/proc/%d/cmdline' % saved['pid']).read_bytes().rstrip(b'\0').decode().split('\0')
    if actual != args or Path('/proc/%d/exe' % saved['pid']).resolve() != Path(args[0]).resolve():
        raise ValueError('local server ownership mismatch')
    if sha(args[args.index('-m')+1]) != saved['model']['sha256']:
        raise ValueError('model hash mismatch')
    if sha(base/'runtime.tar.gz') != saved['runtime']['sha256']:
        raise ValueError('runtime archive hash mismatch')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(saved['endpoint'].replace('/v1/chat/completions', '/health'), timeout=3) as rep:
        if json.load(rep)['status'] != 'ok':
            raise ValueError('local model not ready')
    return dict(endpoint=saved['endpoint'], model='flexcell-'+arm,
                model_sha256=saved['model']['sha256'], runtime=saved['runtime'],
                executable_sha256=sha(args[0]), server_arguments=args)


def configure(arm, profile):
    prefix = 'FLEXCELL_JEV_' if arm == 'fast' else 'FLEXCELL_LLM_'
    os.environ[prefix+'ENDPOINT'] = profile['endpoint']
    os.environ[prefix+'MODEL'] = profile['model']
    os.environ[prefix+'MODEL_SHA256'] = profile['model_sha256']
    os.environ[prefix+'TIMEOUT_S'] = '60'
    if arm == 'slow':
        # These are LOCAL evaluation settings, not the live paid backend profile.
        for name in ('FLEXCELL_LLM_API_KEY_FILE', 'FLEXCELL_LLM_BUDGET_FILE', 'FLEXCELL_LLM_THINKING'):
            os.environ.pop(name, None)
        os.environ['FLEXCELL_LLM_BACKEND'] = 'frozen-local-counterfactual'
        os.environ['FLEXCELL_LLM_RESPONSE_FORMAT'] = 'json_schema'
        os.environ['FLEXCELL_LLM_MAX_TOKENS'] = '160'


def frozen(profile, policy):
    files = ('llm_policy.py', 'decision_policy.py', 'canonical_state.py',
             'contracts/episode.py')
    pkg = REPO/'src/flexcell/flexcell_skills/flexcell_skills'
    data = dict(profile, policy=policy.name, policy_version=policy.version,
                source_hashing='UTF8 with LF line endings',
                source_sha256={name: hashlib.sha256((pkg/name).read_text().encode()).hexdigest() for name in files},
                decoding=dict(temperature=0., seed=20260930, max_tokens=160,
                              response_format='json_schema'))
    identity = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    return dict(data, identity=identity)


def signature(decision):
    return {k: decision[k] for k in ('action', 'target', 'reason_code')}


def evaluate(paths, out, repeatability=False):
    profile = local_profile('slow')
    configure('slow', profile)
    policy = LLMPolicy()
    freeze = frozen(profile, policy)
    summary = dict(schema_version=1, freeze=freeze, comparison_fields=['action', 'target', 'reason_code'],
                   mode='COUNTERFACTUAL_MODEL_EVALUATION', episodes=[])
    for path in paths:
        record = json.loads(path.read_text())
        same = record.get('model_freeze', {}).get('identity') == freeze['identity']
        rows, fixture_steps = [], []
        for step in record['steps']:
            args = inputs(step)
            t0 = time.monotonic()
            got = decision_to_dict(policy.decide(*args))
            want = step['policy_output']
            bootstrap = args[0] is None
            usable = bootstrap or not (got.get('policy_trace') or {}).get('fallback', True)
            rows.append(dict(seq=step['seq'], ok=usable and signature(got)==signature(want),
                             model_called=not bootstrap, model_success=usable and not bootstrap,
                             latency_ms=(time.monotonic()-t0)*1000, recorded=want, replayed=got))
            fixture_steps.append(dict(step, policy_output=got, executor_result=None,
                                      decide_latency_ms=rows[-1]['latency_ms'],
                                      decide_latency_clock='monotonic'))
        status = ('PASS' if rows and all(r['ok'] for r in rows) else 'FAIL') if same else 'COUNTERFACTUAL'
        result = dict(episode_file=str(path), episode_sha256=sha(path), run_id=record['run_id'],
                      same_frozen_model=same, replay_status=status, steps=rows,
                      agreement_steps=sum(r['ok'] for r in rows), total_steps=len(rows),
                      model_successes=sum(r['model_success'] for r in rows))
        summary['episodes'].append(result)
        if repeatability:
            fixture = dict(record, steps=fixture_steps, model_freeze=freeze,
                           record_kind='MODEL_INPUT_FIXTURE', final_state={'outcome': 'NOT_EXECUTED'}, policy={'name': policy.name, 'version': policy.version})
            fixture_path = out.parent/'fixtures'/path.name
            fixture_path.parent.mkdir(parents=True, exist_ok=True)
            fixture_path.write_text(json.dumps(fixture, sort_keys=True)+'\n')
        out.write_text(json.dumps(summary, indent=2)+'\n')
        print(json.dumps({k: result[k] for k in ('run_id', 'replay_status', 'agreement_steps', 'total_steps', 'model_successes')}), flush=True)
    if summary['episodes'] and all(r['same_frozen_model'] for r in summary['episodes']):
        summary['mode'] = 'SAME_FROZEN_MODEL_REPLAY'
    out.write_text(json.dumps(summary, indent=2)+'\n')
    return 1 if any(r['replay_status']=='FAIL' for r in summary['episodes']) else 0


def calibrate(paths, out):
    profile = local_profile('fast')
    configure('fast', profile)
    os.environ.pop('FLEXCELL_JEV_CALIBRATION', None)
    policy, reference = JevPolicy(LocalReproductionBackend()), FSMPolicy()
    rows, excluded = [], []
    # Split by episode before any model calls; correlated steps never cross sets.
    for index, path in enumerate(paths):
        partition = 'heldout' if index % 3 == 2 else 'calibration'
        record = json.loads(path.read_text())
        for step in record['steps']:
            args = inputs(step)
            if args[0] is None:
                continue
            try:
                label = reference.decide(*args).action
            except PolicyStateError:
                excluded.append(dict(episode_sha256=sha(path), seq=step['seq'], reason='outside_FSM_grammar'))
                continue
            t0 = time.monotonic()
            decision = policy.decide(*args)
            trace = decision.policy_trace or {}
            row = dict(episode_sha256=sha(path), seq=step['seq'], partition=partition,
                       expected_action=label, action=decision.action,
                       reported_confidence=trace.get('reported_confidence'),
                       model_success=not trace.get('fallback', True),
                       agreement=decision.action==label and not trace.get('fallback', True),
                       latency_ms=(time.monotonic()-t0)*1000, policy_trace=trace)
            rows.append(row)
            print(json.dumps(row), flush=True)
    bins=[]
    for lower, upper in ((0., .5), (.5, .8), (.8, 1.)):
        group = [r for r in rows if r['partition']=='calibration' and r['model_success']
                 and (lower <= r['reported_confidence'] < upper or r['reported_confidence']==upper==1)]
        k, n = sum(r['agreement'] for r in group), len(group)
        lo, hi = wilson(k, n) if n else (0., 1.)
        bins.append(dict(lower=lower, upper=upper, n=n, agreements=k, wilson_lower=lo, wilson_upper=hi))
    data=dict(schema_version=1, model=profile['model'], model_sha256=profile['model_sha256'],
              prompt_sha256=prompt_digest(), label_definition='FSM_ACTION_AGREEMENT',
              scope='S1 recorded-input routing only; not physical success or other scenario calibration',
              split='episode_index_mod_3_equals_2_heldout', bins=bins, rows=rows, excluded=excluded,
              sources=[dict(path=str(p), sha256=sha(p)) for p in paths])
    held=[r for r in rows if r['partition']=='heldout']
    data['heldout']=dict(n=len(held), model_successes=sum(r['model_success'] for r in held),
                         agreements=sum(r['agreement'] for r in held))
    out.write_text(json.dumps(data, indent=2)+'\n')
    return 0 if held and any(b['n']>=5 for b in bins) else 1


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mode', choices=('replay', 'calibrate'))
    ap.add_argument('--episodes', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--make-repeatability-fixtures', action='store_true')
    args=ap.parse_args()
    paths=sorted(p for p in args.episodes.glob('*.json') if 'steps' in json.loads(p.read_text()))
    if not paths:
        raise ValueError('no episode records')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    return calibrate(paths, args.out) if args.mode=='calibrate' else evaluate(paths, args.out, args.make_repeatability_fixtures)


if __name__=='__main__':
    raise SystemExit(main())
