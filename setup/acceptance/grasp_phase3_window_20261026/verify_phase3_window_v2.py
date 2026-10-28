#!/usr/bin/env python3
"""Recorded facts and historical support inclusion; never a physical lag bound."""
import argparse
import importlib.util
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('phase3_facts', HERE.parents[1] / 'verify_phase3_facts.py')
facts = importlib.util.module_from_spec(spec); spec.loader.exec_module(facts)


def verify(archive=HERE, history=HERE.parent / 'grasp_b001_20261025'):
    result = facts.adjudicate(archive)
    assert result['status'] == 'FACTS_VERIFIED', result['errors']
    values = []
    for row in map(json.loads, (Path(history) / 'stage_pick.jsonl').read_text().splitlines()):
        if row.get('injected') or str(row.get('detail', '')).startswith('injected failure'):
            continue
        if str(row.get('error_code')) == '23' and 'box_rise_m' in row:
            value = row['box_rise_m']; assert math.isfinite(value)
            values.append(value)
    assert len(values) == 92 and sum(value < 0 for value in values) == 54
    failed, = [row for row in result['trials'] if not row['pick_ok']]
    rise = failed['rise_m']
    assert min(values) <= rise <= max(values), 'window failure is inside historical support'
    assert sum(value >= rise for value in values) == 7, 'historical upper tail must not be hidden'
    assert math.isclose(min(values), -.010278087884338557, abs_tol=1e-12)
    assert math.isclose(max(values), .02983547372742743, abs_tol=1e-12)
    return dict(schema_version=2, status='FACTS_AND_SUPPORT_VERIFIED', mechanism='UNKNOWN',
        historical_same_mechanism='UNKNOWN', historical_n=len(values), historical_negative=54,
        historical_support_m=[min(values), max(values)], window_failure_rise_m=rise,
        historical_at_or_above_window_failure=7, relation='WITHIN_SUPPORT; not evidence of equal mechanisms',
        observed_envelope_is_physical_bound=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path, nargs='?', default=HERE)
    parser.add_argument('history', type=Path, nargs='?', default=HERE.parent / 'grasp_b001_20261025')
    args = parser.parse_args()
    print(json.dumps(verify(args.archive, args.history), indent=2))
