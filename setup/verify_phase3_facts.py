#!/usr/bin/env python3
"""Re-adjudicate #52's recorded facts without asserting an unmeasured cause.

The historical verifier and raw archive remain unchanged. Its observed maximum
residual is not a physical bound, and endpoint poses are not simultaneous TF /
pin / object samples. This checker deliberately makes neither inference.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE = ROOT / 'setup/acceptance/grasp_phase3_window_20261026'
spec = importlib.util.spec_from_file_location('carry_observation_gate',
                                            ROOT / 'setup/112_carry_observation_gate.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def ballistic_drop(downward_speed_m_s, sim_interval_s, gravity_m_s2=9.81):
    """A counterexample model, not an estimate of any recorded object's speed."""
    if not all(math.isfinite(x) and x >= 0 for x in
               (downward_speed_m_s, sim_interval_s, gravity_m_s2)):
        raise ValueError('finite nonnegative model inputs required')
    return downward_speed_m_s * sim_interval_s + .5 * gravity_m_s2 * sim_interval_s ** 2


def adjudicate(archive=DEFAULT_ARCHIVE):
    archive = Path(archive)
    inputs, errors, segments, trials = {}, [], {}, []

    def load(relative, jsonl=True):
        rows, manifest = gate.read_input(archive / relative, jsonl=jsonl)
        inputs[relative] = manifest
        return rows

    picks = load('logs/pick_window.jsonl')
    carry = load('logs/carry_window.jsonl')
    for segment in ('A1', 'A4', 'B5'):
        rows = load(segment + '.jsonl')
        receipt = load(segment + '.exit', jsonl=False)
        result = gate.audit_segment(segment, rows, picks, carry,
                                    0 if receipt.strip() == '0' else -1)
        segments[segment] = result
        errors.extend('%s: %s' % (segment, e) for e in result['errors'])
        trials.extend(dict(t, segment=segment) for t in result['trials'])
    for field in ('session', 'evidence_id', 'goal_uuid'):
        if len({t[field] for t in trials}) != len(trials):
            errors.append('reused %s across segments' % field)
    health = {}
    for when in ('before', 'after'):
        relative = 'health_%s.json' % when
        data = (archive / relative).read_bytes()
        inputs[relative] = dict(path=str(archive / relative), size_bytes=len(data),
                                sha256=hashlib.sha256(data).hexdigest())
        doc = json.loads(data)
        checks = doc.get('checks', {})
        ok = (doc.get('ok') is True and doc.get('hard_fail') == []
              and checks.get('task_state') == 'IDLE' and checks.get('carry_engaged') is False)
        health[when] = ok
        if not ok:
            errors.append('health %s does not confirm IDLE / disengaged' % when)
    totals = {key: sum(t['session_totals'][key] for t in trials) for key in
              ('ee_lookup_count', 'ee_missing_count', 'pin_requests', 'pin_confirmed', 'pin_failed')}
    successes = sum(t['pick_ok'] for t in trials)
    failed = [t for t in trials if not t['pick_ok']]
    facts = (len(trials) == 10 and successes == 9 and len(failed) == 1
             and failed[0]['segment'] == 'B5' and failed[0]['trial'] == 2
             and failed[0]['error_code'] == 23
             and totals == dict(ee_lookup_count=639, ee_missing_count=0,
                                pin_requests=639, pin_confirmed=638, pin_failed=1))
    if not facts:
        errors.append('the frozen ten-trial window facts changed')
    return dict(schema_version=1, status='FACTS_VERIFIED' if not errors else 'FACTS_REJECTED',
                archive=str(archive), inputs=inputs, segments=segments,
                trials=trials, successes=successes, failures=len(failed),
                loop_totals=totals, health=health, errors=errors,
                mechanism='UNKNOWN', historical_same_mechanism='UNKNOWN',
                interpretation=[
                    'This failed trial recorded no empty EE lookup or rejected pin request.',
                    'A successful lookup does not establish TF freshness.',
                    'A successful set_pose reply does not establish sustained physical attachment.',
                    'Session totals can include subsequent PLACE; use PICK prefixes separately.',
                    'The largest observed endpoint residual is not a universal lag bound.',
                    'No continuous velocity / target / sample-phase trace was recorded here.',
                    'The counterexample model does not establish this trial\'s physical cause.'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    try:
        report = adjudicate(args.archive)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        report = dict(status='FACTS_REJECTED', mechanism='UNKNOWN', errors=[str(exc)])
    text = json.dumps(report, indent=2, allow_nan=False)
    if args.out:
        try:
            with args.out.open('x') as stream:
                stream.write(text + '\n')
        except OSError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    print(text)
    return 1 if report['errors'] else 0


if __name__ == '__main__':
    sys.exit(main())
