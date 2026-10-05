#!/usr/bin/env python3
"""Assemble disjoint 119_policy_eval segments without resampling any input."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

from flexcell_skills.contracts.metrics import wilson
from flexcell_skills.decision_policy import FSMPolicy, PolicyStateError


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bins_for(rows):
    bins = []
    for lower, upper in ((0., .5), (.5, .8), (.8, 1.)):
        group = [r for r in rows if r['partition'] == 'calibration'
                 and r['model_success']
                 and (lower <= r['reported_confidence'] < upper
                      or r['reported_confidence'] == upper == 1)]
        k, n = sum(r['agreement'] for r in group), len(group)
        lo, hi = wilson(k, n) if n else (0., 1.)
        bins.append(dict(lower=lower, upper=upper, n=n, agreements=k,
                         wilson_lower=lo, wilson_upper=hi))
    return bins


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--generator', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), 'Preserve previous evidence; use a new output'
    selection = json.loads((args.root / 'selection.json').read_text())
    segments = [args.root / ('calibration_' + name + '.json')
                for name in ('pilot', 'extension')]
    data = [json.loads(p.read_text()) for p in segments]
    identity_fields = ('schema_version', 'model', 'model_sha256',
                       'prompt_sha256', 'label_definition', 'scope', 'split')
    result = {key: data[0][key] for key in identity_fields}
    rows, excluded, sources = [], [], []
    for part in data:
        assert all(part[key] == result[key] for key in identity_fields)
        assert part['bins'] == bins_for(part['rows'])
        rows.extend(part['rows'])
        excluded.extend(part['excluded'])
        sources.extend(part['sources'])
    assert len({(r['episode_sha256'], r['seq']) for r in rows}) == len(rows)
    assert len({s['sha256'] for s in sources}) == len(sources) == 5
    expected_sources = {s['sha256'] for s in selection['episodes']}
    assert {s['sha256'] for s in sources} == expected_sources
    spec = importlib.util.spec_from_file_location('policy_eval', args.generator)
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    by_key = {(r['episode_sha256'], r['seq']): r for r in rows}
    excluded_keys = {(r['episode_sha256'], r['seq']) for r in excluded}
    checked = set()
    for index, source in enumerate(selection['episodes']):
        original, copy = Path(source['path']), Path(source['copy'])
        assert digest(original) == digest(copy) == source['sha256']
        record = json.loads(copy.read_text())
        assert record['runtime_fingerprint'] == selection['source_fingerprint']
        partition = 'heldout' if index % 3 == 2 else 'calibration'
        assert partition == source['partition']
        for step in record['steps']:
            inputs = evaluator.inputs(step)
            if inputs[0] is None:
                continue
            key = (source['sha256'], step['seq'])
            try:
                label = FSMPolicy().decide(*inputs).action
            except PolicyStateError:
                assert key in excluded_keys
                continue
            row = by_key[key]
            assert row['partition'] == partition
            assert row['expected_action'] == label
            trace = row['policy_trace']
            success = trace.get('fallback') is False
            assert row['model_success'] == success
            assert row['agreement'] == (row['action'] == label and success)
            if success:
                assert trace['backend'] == 'clef' and trace['source'] == 'jev'
                assert trace['model'] == result['model']
                assert trace['model_sha256'] == result['model_sha256']
                assert trace['reported_confidence'] == row['reported_confidence']
                assert type(trace['tokens']) is int and trace['tokens'] > 0
            assert row['latency_ms'] > 0
            checked.add(key)
    assert checked == set(by_key)
    held = [r for r in rows if r['partition'] == 'heldout']
    result.update(bins=bins_for(rows), rows=rows, excluded=excluded,
                  sources=sources,
                  heldout=dict(n=len(held),
                               model_successes=sum(r['model_success'] for r in held),
                               agreements=sum(r['agreement'] for r in held)),
                  assembly=dict(source_fingerprint=selection['source_fingerprint'],
                                disjoint_segments=True, resampled_inputs=0,
                                generator_sha256=digest(args.generator),
                                segments=[dict(path=str(p), sha256=digest(p))
                                          for p in segments]))
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(bins=result['bins'], heldout=result['heldout'],
                          rows=len(rows), excluded=len(excluded),
                          route_eligible_085=any(b['n'] >= 5 and b['wilson_lower'] >= .85
                                                 for b in result['bins'])), indent=2))


if __name__ == '__main__':
    main()
