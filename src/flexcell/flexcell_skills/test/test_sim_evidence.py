"""Failed examples and missing data must survive without successful defaults."""
import importlib.util
import json
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[4]


def script(name, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'scripts'))
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_unmeasured_failure_error_is_null_without_erasing_failed_outcome(monkeypatch):
    module = script('sim_smoke', monkeypatch)
    raw = dict(status='EXPECTED_FAILURE', task=dict(outcome_val=1,
        error_code='ERR_RECOVERY_EXHAUSTED', final_position_error_m=float('nan')))
    result = module.json_result(raw)
    encoded = json.dumps(result, allow_nan=False)
    assert result['task']['outcome_val'] == 1
    assert result['task']['error_code'] == 'ERR_RECOVERY_EXHAUSTED'
    assert result['task']['final_position_error_m'] is None
    assert result['unavailable_numeric_fields'] == {'task.final_position_error_m': 'nan'}
    assert 'NaN' in json.dumps(raw)  # original input was not rewritten
    assert 'NaN' not in encoded


@pytest.mark.parametrize('defect', ['missing_alignment', 'gap', 'missing_outcome'])
def test_export_refuses_bad_data_without_selecting_good_subset(tmp_path, monkeypatch, defect):
    module = script('export_lerobot', monkeypatch)
    (tmp_path / 'data').mkdir()
    result = dict(task={'outcome_val': 1}, runtime_fingerprint='fixture',
                  task_start_monotonic_ns=0, task_end_monotonic_ns=10**10)
    if defect == 'missing_outcome':
        result.pop('task')
    (tmp_path / 'result.json').write_text(json.dumps(result))
    (tmp_path / 'data/collection.json').write_text(json.dumps(dict(errors=[], rosbag_exit=0)))
    rows = [dict(valid=True, sim_ns=i * 100_000_000, monotonic_ns=i + 1) for i in range(3)]
    if defect == 'missing_alignment': rows[1]['valid'] = False
    if defect == 'gap': rows[2]['sim_ns'] += 200_000_000
    raw = '\n'.join(json.dumps(row) for row in rows) + '\n'
    path = tmp_path / 'data/frames.jsonl'
    path.write_text(raw)
    with pytest.raises(ValueError):
        module.episode(tmp_path)
    assert path.read_text() == raw


@pytest.mark.parametrize('guard', ['world', 'config', 'fingerprint'])
def test_declared_identity_mismatch_dispatches_no_stack_or_task(tmp_path, monkeypatch, guard):
    module = script('sim_smoke', monkeypatch)
    def profile(out, *args):
        params, world = out / 'params.yaml', out / 'world.sdf'
        params.write_text('node:\n  ros__parameters:\n    log_dir: /tmp/record\n')
        world.write_text('<sdf><world name="empty"/></sdf>')
        return params, world
    def identity(argv, out, timeout=120):
        out.with_suffix('.stdout').write_text('{}')
        return 0
    launches = []
    monkeypatch.setattr(module, 'profile', profile)
    monkeypatch.setattr(module, 'command', identity)
    monkeypatch.setattr(module.subprocess, 'Popen', lambda *a, **k: launches.append(a))
    option = {'world': '--expected-world-sha256', 'config': '--expected-config-sha256',
              'fingerprint': '--expected-fingerprint'}[guard]
    monkeypatch.setattr(sys, 'argv', ['sim_smoke.py', '--out', str(tmp_path), option, '0' * 64])
    assert module.main() == 1
    result = json.loads(next(tmp_path.glob('run-*/result.json')).read_text())
    assert result['physical_tasks_dispatched'] == 0
    assert 'no robot task dispatched' in result['error']
    assert not launches
