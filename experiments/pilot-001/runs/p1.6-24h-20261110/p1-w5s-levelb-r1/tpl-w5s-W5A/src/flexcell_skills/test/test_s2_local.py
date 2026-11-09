"""Exercise the handoff without launching Docker, ROS, Gazebo or an action."""
import hashlib
import json
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import zlib

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
import s2_local as s2
from sim_profile import profile


@pytest.fixture
def candidate(monkeypatch, tmp_path):
    current = dict(source_revision='a' * 40, source_tree_sha256='b' * 64,
                   mismatches=[], native_libraries={'plugin': 'c' * 64})
    monkeypatch.setattr(s2, 'identity', lambda: current.copy())
    out = tmp_path / 'candidate'
    s2.prepare(out)
    return out, current


def png():
    def chunk(kind, data):
        return (struct.pack('>I', len(data)) + kind + data
                + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff))
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', 640, 480, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress((b'\0' + b'\0' * 1920) * 480))
            + chunk(b'IEND', b''))


def completed(directory):
    case = directory.name
    run = directory / 'trial-01/run-example'
    data = run / 'data'
    data.mkdir(parents=True)
    s2.save(run / 'result.json', dict(task={'outcome_val': int(case == 'false_attach')},
                                    runtime_fingerprint='frozen-runtime',
                                    task_start_monotonic_ns=50, task_end_monotonic_ns=350))
    s2.save(data / 'collection.json', dict(errors=[], rosbag_exit=0))
    frames = []
    for index in range(3):
        image = '%d.png' % index
        (data / image).write_bytes(png())
        frames.append(dict(monotonic_ns=(index + 1) * 100,
                           sim_ns=1_000_000_000 + index * 100_000_000,
                           valid=True, image=image))
    (data / 'frames.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in frames))
    trial = dict(case=case, object='target_box_a', run=str(run),
                 result=dict(expectation_met=True))
    if case == 'false_attach':
        trial['false_attach_evidence'] = dict(status='FALSE_ATTACH_REJECTED',
            boundary='guard_input_pose', place_dispatched=False,
            injection_first_sim_ns=1_050_000_000, injection_last_sim_ns=1_150_000_000)
    s2.save(directory / 'window.json', dict(status='FUNCTIONAL_WINDOW_PASS', episodes=[trial]))
    return run


@pytest.mark.parametrize('source,name', [('joint-preposition-world.json', 's2-joint-camera.json'),
                                       ('joint-false-attach-window.json', 's2-false-attach-camera.json')])
def test_new_camera_declarations_keep_every_original_gate_and_materialized_hash(tmp_path, source, name):
    old = s2.read(ROOT / 'infra' / source)
    new = s2.read(ROOT / 'infra' / name)
    changed = {'purpose', 'camera', 'world_sha256', 'semantic_config_sha256',
               'prior_implementation_revision', 'review_reference'}
    assert {k: v for k, v in old.items() if k not in changed} == {
        k: v for k, v in new.items() if k not in changed}
    assert old['camera'] is False and new['camera'] is True
    params, world = profile(tmp_path / 'profile', new['backend'], True, new['skill_backend'],
                            new.get('joint_hold_sim_s', 0.), new['physics_step_s'],
                            contact_trace=True, release_clearance_m=new.get('release_clearance_m'),
                            qualification_no_recovery=True)
    config = yaml.safe_load(params.read_text())
    for node in config.values():
        for key in list(node.get('ros__parameters', {})):
            if key in ('log_dir', 'episode_dir'):
                node['ros__parameters'][key] = '$RUN/' + key
    assert s2.digest(world) == new['world_sha256']
    assert hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest() == new['semantic_config_sha256']


def test_prepare_is_not_execution_and_never_overwrites(candidate, monkeypatch):
    out, _ = candidate
    monkeypatch.setattr(s2, 'run_window', lambda *args: pytest.fail('prepare dispatched a task'))
    plan = s2.read(out / 'plan.json')
    assert plan['status'] == 'PREPARED_NOT_RUN' and plan['logical_tasks'] == 2
    assert plan['default_admission'] == 'NO_GO' and plan['host_role_verified'] is False
    assert not (out / 'attempt.json').exists()
    with pytest.raises(FileExistsError):
        s2.prepare(out)


@pytest.mark.parametrize('change', [lambda x: x.update(source_revision='WORKTREE'),
                                  lambda x: x.update(source_tree_sha256='missing'),
                                  lambda x: x.update(mismatches=['carry_server.py'])])
def test_identity_rejects_unqualified_build_metadata(monkeypatch, change):
    value = dict(source_revision='a' * 40, source_tree_sha256='b' * 64, mismatches=[])
    change(value)
    monkeypatch.setattr(s2.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout=json.dumps(value)))
    with pytest.raises(ValueError):
        s2.identity()


def test_both_windows_are_serial_and_do_not_grant_admission(candidate, monkeypatch):
    out, _ = candidate
    calls = []
    def run(manifest, directory, log):
        calls.append(directory.name)
        completed(directory)
        return 0
    monkeypatch.setattr(s2, 'run_window', run)
    report = s2.execute(out)
    assert calls == ['normal', 'false_attach']
    assert report['status'] == 'LOCAL_INTEGRATION_PASS' and report['default_admission'] == 'NO_GO'
    assert report['host_role_verified'] is False
    assert report['windows'][1]['camera']['preview_sim_ns'] == 1_100_000_000
    assert (out / 'false_attach-preview.png').read_bytes() == png()
    with pytest.raises(FileExistsError):
        s2.execute(out)
    assert calls == ['normal', 'false_attach']


@pytest.mark.parametrize('failure', ['nonzero', 'no_window', 'missing_image', 'bad_png',
                                    'camera_gap', 'unknown_terminal', 'interrupt'])
def test_first_unexpected_failure_preserves_not_run_and_blocks_replacement(candidate, monkeypatch, failure):
    out, _ = candidate
    calls = []
    def run(manifest, directory, log):
        calls.append(directory.name)
        if failure == 'interrupt':
            raise KeyboardInterrupt
        if failure == 'nonzero':
            return 1
        if failure == 'no_window':
            return 0
        path = completed(directory)
        if failure == 'missing_image':
            (path / 'data/1.png').unlink()
        elif failure == 'bad_png':
            (path / 'data/1.png').write_bytes(b'not an image')
        elif failure == 'camera_gap':
            index = path / 'data/frames.jsonl'
            rows = index.read_text().splitlines()
            index.write_text(rows[0] + '\n' + rows[2] + '\n')
        elif failure == 'unknown_terminal':
            s2.save(directory / 'window.json', dict(status='STOPPED', episodes=[]))
        return 0
    monkeypatch.setattr(s2, 'run_window', run)
    report = s2.execute(out)
    assert calls == ['normal'] and report['status'] == 'STOPPED'
    assert [w['status'] for w in report['windows']] == ['STOPPED', 'NOT_RUN']
    with pytest.raises(FileExistsError):
        s2.execute(out)


@pytest.mark.parametrize('changed', ['identity', 'declaration', 'revision'])
def test_changed_candidate_stops_before_dispatch(candidate, monkeypatch, changed):
    out, current = candidate
    monkeypatch.setattr(s2, 'run_window', lambda *args: pytest.fail('changed candidate was dispatched'))
    if changed == 'identity':
        current['native_libraries']['plugin'] = 'd' * 64
    elif changed == 'declaration':
        (out / 'declarations/s2-joint-camera.json').write_text('{}')
    else:
        plan = s2.read(out / 'plan.json'); plan['source_revision'] = 'e' * 40
        s2.save(out / 'plan.json', plan)
    with pytest.raises(ValueError):
        s2.execute(out)
    assert not (out / 'attempt.json').exists()


def test_fault_video_must_cover_the_same_injection(tmp_path):
    run = completed(tmp_path / 'false_attach')
    with pytest.raises(ValueError, match='RGB does not cover'):
        s2.camera_evidence(run, dict(injection_first_sim_ns=2_000_000_000,
                                   injection_last_sim_ns=2_200_000_000))


def test_normal_video_cannot_substitute_for_missing_fault_video(candidate, monkeypatch):
    out, _ = candidate
    def run(manifest, directory, log):
        path = completed(directory)
        if directory.name == 'false_attach':
            (path / 'data/1.png').unlink()
        return 0
    monkeypatch.setattr(s2, 'run_window', run)
    report = s2.execute(out)
    assert report['status'] == 'STOPPED'
    assert [w['status'] for w in report['windows']] == ['PASS', 'STOPPED']
