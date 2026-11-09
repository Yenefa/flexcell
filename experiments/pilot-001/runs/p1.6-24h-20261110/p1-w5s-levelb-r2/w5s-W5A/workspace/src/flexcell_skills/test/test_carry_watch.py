"""A pose-pattern report cannot invent timing or turn ambiguity into a verdict."""
import importlib.util
import json
import math
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[4]


def watch():
    spec = importlib.util.spec_from_file_location('carry_watch', ROOT / 'setup/114_carry_watch.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frames(kind):
    out = []
    for i in range(200):
        if kind == 'stable':
            z = .1 + .0002 * math.sin(i)
        elif kind == 'sawtooth':
            z = .11 - .016 * (i % 5)
        elif kind == 'none':
            z = .0175
        else:
            z = .09 + .03 * math.sin(i * .02 * 2 * math.pi)
        ns = i * 20_000_000
        out.append(dict(header=dict(stamp=dict(sec=ns // 10**9, nsec=ns % 10**9)), pose=[
            dict(name='target_box_a', position=dict(z=z)),
            dict(name='gripper_left_link', position=dict(z=.26)),
            dict(name='gripper_right_link', position=dict(z=.26))]))
    return out


@pytest.mark.parametrize('kind,expected', [('stable', 'CONSTANT_OFFSET'),
    ('sawtooth', 'SAWTOOTH'), ('none', 'NO_CARRY'), ('other', 'INDETERMINATE')])
def test_patterns_describe_the_observed_shape(tmp_path, kind, expected):
    path, result = tmp_path / 'poses.jsonl', tmp_path / 'result.json'
    path.write_text('\n'.join(json.dumps(row) for row in frames(kind)) + '\n')
    assert watch().main(['--poses', str(path), '--rest', '.0175', '--json', str(result)]) == 0
    assert json.loads(result.read_text())['verdict'] == expected


@pytest.mark.parametrize('defect', ['missing_stamp', 'backward', 'nonfinite',
    'missing_box', 'sampling_gap', 'bad_json'])
def test_bad_source_cannot_gain_a_shape_verdict(tmp_path, defect):
    rows = frames('sawtooth')
    if defect == 'missing_stamp':
        rows[30].pop('header')
    elif defect == 'backward':
        rows[30]['header'] = rows[29]['header']
    elif defect == 'nonfinite':
        rows[30]['pose'][0]['position']['z'] = float('nan')
    elif defect == 'missing_box':
        rows[30]['pose'].pop(0)
    elif defect == 'sampling_gap':
        del rows[30:40]
    text = '\n'.join(json.dumps(row) for row in rows) + '\n'
    if defect == 'bad_json':
        text += '{invalid\n'
    source, result = tmp_path / 'poses.jsonl', tmp_path / 'result.json'
    source.write_text(text)
    assert watch().main(['--poses', str(source), '--rest', '.0175', '--json', str(result)]) == 2
    assert not result.exists()
