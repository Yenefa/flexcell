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


@pytest.mark.parametrize('guard', ['world', 'config', 'fingerprint', 'rendering', 'egl_vendor'])
def test_declared_identity_mismatch_dispatches_no_stack_or_task(tmp_path, monkeypatch, guard):
    module = script('sim_smoke', monkeypatch)
    def profile(out, *args, **kwargs):
        # The runner may gain declared options (policy, clearance, ...); this stub
        # stands in for the whole materialisation step and must stay signature-agnostic.
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
    if guard == 'rendering':
        def reject(out):
            raise RuntimeError('camera EGL preflight failed; no robot task dispatched')
        monkeypatch.setattr(module, 'preflight_rendering', reject)
        options = ['--camera']
    elif guard == 'egl_vendor':
        monkeypatch.setattr(module, 'preflight_rendering', lambda out: dict(status='PASS', vendor_files={}))
        options = ['--camera', '--expected-egl-vendor-sha256', '0' * 64]
    else:
        option = {'world': '--expected-world-sha256', 'config': '--expected-config-sha256',
                  'fingerprint': '--expected-fingerprint'}[guard]
        options = [option, '0' * 64]
    monkeypatch.setattr(sys, 'argv', ['sim_smoke.py', '--out', str(tmp_path), *options])
    assert module.main() == 1
    result = json.loads(next(tmp_path.glob('run-*/result.json')).read_text())
    assert result['physical_tasks_dispatched'] == 0
    assert 'no robot task dispatched' in result['error']
    assert not launches


@pytest.mark.parametrize('defect', ['no_surfaceless', 'only_device', 'old_gl', 'missing_renderer'])
def test_camera_preflight_rejects_other_platform_success(monkeypatch, defect):
    module = script('camera_preflight', monkeypatch)
    good = ('Surfaceless platform:\nEGL vendor string: Mesa Project\n'
            'OpenGL core profile renderer: llvmpipe\n'
            'OpenGL core profile version: 4.5 (Core Profile) Mesa\n')
    assert module.parse_surfaceless(good)['OpenGL core profile renderer'] == 'llvmpipe'
    bad = {
        'no_surfaceless': good.replace('Surfaceless', 'X11'),
        'only_device': 'Surfaceless platform:\neglinfo: eglInitialize failed\n\n' +
                       good.replace('Surfaceless', 'Device'),
        'old_gl': good.replace('4.5 (Core Profile)', '3.2 (Core Profile)'),
        'missing_renderer': good.replace('OpenGL core profile renderer: llvmpipe\n', ''),
    }[defect]
    with pytest.raises(ValueError):
        module.parse_surfaceless(bad)


def test_surfaceless_context_survives_other_platform_exit_errors(tmp_path, monkeypatch):
    module = script('camera_preflight', monkeypatch)
    stdout = ('X11 platform:\neglinfo: eglInitialize failed\n\n'
              'Surfaceless platform:\nEGL vendor string: Mesa Project\n'
              'OpenGL core profile renderer: llvmpipe\n'
              'OpenGL core profile version: 4.5 (Core Profile) Mesa\n')
    probe = module.subprocess.CompletedProcess(['eglinfo', '-B'], 3, stdout, '')
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **k: probe)
    report = module.preflight_rendering(tmp_path)
    assert report['status'] == 'PASS' and report['returncode'] == 3
    assert (tmp_path / 'camera_preflight.stdout').read_text() == stdout
    assert report['simulator_started'] is False


def test_identity_rejects_stale_installed_launch_with_matching_python(tmp_path, monkeypatch):
    from types import SimpleNamespace
    spec = importlib.util.spec_from_file_location('runtime_identity', ROOT / 'infra/runtime_identity.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    repo, install = tmp_path / 'repo', tmp_path / 'install'
    package = repo / 'src/flexcell/flexcell_skills'
    source = package / 'flexcell_skills/__init__.py'
    imported = install / 'lib/python/flexcell_skills/__init__.py'
    launch_source = package / 'launch/trusted_sim.launch.py'
    launch_installed = install / 'share/flexcell_skills/launch/trusted_sim.launch.py'
    for path in (source, imported, launch_source, launch_installed,
                 repo / 'setup/flexcell_admin.py', repo / 'plan_execute.py'):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# matching fixture\n')
    monkeypatch.setattr(module.importlib.util, 'find_spec', lambda name: SimpleNamespace(origin=str(imported)))
    assert module.snapshot(repo, install)['mismatches'] == []
    launch_installed.write_text('# stale launch still uses the old startup sequence\n')
    identity = module.snapshot(repo, install)
    assert identity['mismatches'] == ['launch/trusted_sim.launch.py']
    assert all(row['source_sha256'] == row['installed_sha256']
               for row in identity['python_files'].values())
