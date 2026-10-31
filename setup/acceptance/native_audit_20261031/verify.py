#!/usr/bin/env python3
"""Replay preserved native evidence offline; never start a simulator or ROS client."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import tempfile
import zipfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract(archive, root, expected=None):
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        names = bundle.namelist()
        assert len(names) == len(set(names))
        if expected is not None:
            assert set(names) == set(expected)
        for name in names:
            parts = PurePosixPath(name)
            assert not parts.is_absolute() and '..' not in parts.parts and '\\' not in name
            path = root.joinpath(*parts.parts)
            assert path.resolve().is_relative_to(root.resolve())
            if name.endswith('/'):
                path.mkdir(parents=True,exist_ok=True)
                continue
            data = bundle.read(name)
            if expected is not None:
                assert hashlib.sha256(data).hexdigest() == expected[name], name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(data)


def clocks(run):
    tables, summary = [], {}
    for name in ('physics_steps','contact_steps'):
        data = (run/(name+'.jsonl')).read_bytes()
        assert data.endswith(b'\n')
        rows = [json.loads(line) for line in data.splitlines()]
        assert len(rows) > 1
        assert all(b['sim_ns']-a['sim_ns'] == 2_000_000 and b['monotonic_ns']>a['monotonic_ns']
                   for a,b in zip(rows,rows[1:]))
        table = {r['sim_ns']:r['monotonic_ns'] for r in rows}
        assert len(table) == len(rows)
        tables.append(table)
        summary[name] = dict(rows=len(rows),raw_step_gaps=0,
            max_producer_gap_ns=max(b['monotonic_ns']-a['monotonic_ns'] for a,b in zip(rows,rows[1:])))
    assert tables[0].keys() == tables[1].keys()
    summary['max_clock_skew_ns'] = max(abs(tables[0][ns]-tables[1][ns]) for ns in tables[0])
    assert summary['max_clock_skew_ns'] <= 50_000_000
    return summary


def reader_timing(run):
    diagnostic = json.loads((run/'diagnostic-worker.json').read_text())
    assert len(diagnostic['followers']) == 5
    followers = diagnostic['followers']
    active_gc = [event['duration_ns'] for event in diagnostic['gc_events']
                 if any(wait['start_ns'] <= event['started_ns'] <= event['ended_ns'] <= wait['end_ns']
                        for follower in followers for wait in follower['waits'])]
    for follower in followers:
        assert len(follower['waits']) == 8 and all('returned_sim_ns' in w and 'error' not in w
                                                 for w in follower['waits'])
    return dict(max_live_collect_ns=max(f['max_collect_ns'] for f in followers),
        max_recorded_gc_inside_live_wait_ns=max(active_gc,default=0),
        max_recorded_gc_any_phase_ns=max(e['duration_ns'] for e in diagnostic['gc_events']),
        live_collect_ns_per_cycle=[f['max_collect_ns'] for f in followers],
        interpretation='one diagnostic window per version; no latency guarantee or CI root-cause claim')


def local_window(run, revision, source_binding=None):
    from native_cycle_gate import verify_run
    result = json.loads((run/'result.json').read_text())
    declaration = json.loads((run/'declaration.json').read_text())
    assert result['status'] == 'PASS' and result['worker_exit'] == 0
    assert result['recorder_exit'] == result['owned_exit'] == 0
    assert result['no_replacements'] is True and result['robot_motion_tasks'] == 0
    assert result['default_admission'] == 'NO_GO'
    assert sha(run/'declaration.json') == result['declaration_sha256']
    assert sha(run/'world.sdf') == result['world_sha256'] == declaration['world_sha256']
    identity = json.loads((run/'identity.stdout').read_text())
    assert not identity['mismatches']
    if source_binding is None:
        assert identity['source_revision'] == revision
        revision_metadata = 'VALID'
    else:
        # A documented receipt defect is preserved, never silently stripped.
        assert source_binding['canonical_source_revision'] == source_binding['git_archive_pax_comment'] == revision
        assert source_binding['source_revision_metadata'] == 'INVALID_TRAILING_CR'
        assert identity['source_revision'] == source_binding['recorded_source_revision'] == revision+'\r'
        assert identity['source_files'] == source_binding['source_files']
        assert len(identity['source_files']) == source_binding['verified_source_files'] == 209
        assert hashlib.sha256(json.dumps(identity['source_files'],sort_keys=True).encode()).hexdigest() == identity['source_tree_sha256']
        revision_metadata = source_binding['source_revision_metadata']
    for group in ('python_files','launch_files'):
        assert all(v['source_sha256'] == v['installed_sha256'] for v in identity[group].values())
    mapped = json.loads((run/'loaded_libraries.json').read_text())
    for name in ('flexcell_physics_trace','flexcell_contact_trace','flexcell_detachable_carry'):
        expected = identity['native_libraries']['lib/lib'+name+'.so']
        assert any(Path(path).name == 'lib'+name+'.so' and digest == expected for path,digest in mapped.items())
    health_counts = {}
    for name in ('health_after_cycles','health_after'):
        health = json.loads((run/(name+'.stdout')).read_text())
        assert health['ok'] and not health['hard_fail']
        assert health['checks']['task_state'] == 'IDLE' and health['checks']['carry_engaged'] is False
        health_counts[name] = len(health['checks'])
    reset = json.loads((run/'reset_after.stdout').read_text())
    assert reset['ok']
    gate = verify_run(run,declaration)
    assert gate['status'] == 'FIVE_NATIVE_CYCLES_PASS' and gate['qualification_cycles'] == 5
    return dict(source_revision=revision,source_revision_metadata=revision_metadata,
        partition=result['partition'],raw_clocks=clocks(run),
        gate=gate,reader_timing=reader_timing(run),health_checks=health_counts), identity


def historical_window(root, archive_sha):
    from native_cycle_gate import verify_cycle
    archive = root/'historical-ci/native-five-41116653853.zip'
    assert sha(archive) == archive_sha
    extracted = root/'historical-ci/extracted'
    extract(archive,extracted)
    run = extracted/'native-five-window'
    worker = json.loads((run/'worker.json').read_text())
    result = json.loads((run/'result.json').read_text())
    assert worker['status'] == result['status'] == 'STOPPED'
    assert 'native stream stale; age_ns=787690270' in worker['error']
    assert len(worker['cycles']) == 3 and 'evidence' not in worker['cycles'][2]
    physics = {r['sim_ns']:r for r in map(json.loads,(run/'physics_steps.jsonl').read_text().splitlines())}
    contacts = {r['sim_ns']:r for r in map(json.loads,(run/'contact_steps.jsonl').read_text().splitlines())}
    events = list(map(json.loads,(run/'native-events.jsonl').read_text().splitlines()))
    declaration = json.loads((run/'declaration.json').read_text())
    gated = [verify_cycle(physics,contacts,cycle,events,declaration)['status'] for cycle in worker['cycles'][:2]]
    release = next(e for e in events if e['cycle']==2 and e['label']=='release')
    physical_release = next(r for ns,r in sorted(physics.items()) if ns>worker['cycles'][2]['reference_sim_ns']
        and release['request_mono_ns'] <= r['monotonic_ns'] <= release['reply_mono_ns']
        and r['objects']['target_box_b']['joint_component'] is False)
    return dict(workflow_run=41116653853,status='STOPPED',completed_cycle_gates=gated,
        incomplete_cycle_index=2,raw_clocks=clocks(run),
        release_rpc_ns=release['reply_mono_ns']-release['request_mono_ns'],
        release_sim_ns=physical_release['sim_ns'],historical_pause_cause='UNKNOWN')


def verify(capsule, repo):
    sys.path[:0] = [str(repo/'scripts'),str(repo/'src/flexcell/flexcell_skills')]
    receipt = json.loads((capsule/'receipt.json').read_text())
    assert sha(capsule/'source-binding.json') == receipt['source_binding_sha256']
    binding = json.loads((capsule/'source-binding.json').read_text())
    for name,digest in receipt['verification_sources'].items():
        assert sha(repo/name) == digest, 'gate changed; use the recorded source revision: '+name
    assert sha(capsule/'raw-evidence.zip') == receipt['archive_sha256']
    with tempfile.TemporaryDirectory(prefix='flexcell-native-audit-') as temporary:
        root = Path(temporary)
        extract(capsule/'raw-evidence.zip',root,receipt['files'])
        baseline, old_identity = local_window(root/'baseline/window',receipt['baseline_source_revision'])
        export_receipt = json.loads((root/'preflight/patched-source-receipt.json').read_text())
        assert export_receipt['revision'] == binding['canonical_source_revision']
        assert export_receipt['sha256'] == binding['source_archive_sha256']
        sidecar = root/'preflight/patched-source-revision.txt'
        assert sha(sidecar) == binding['revision_sidecar_sha256']
        assert sidecar.read_bytes() == (binding['canonical_source_revision']+'\r\n').encode('ascii')
        patched, new_identity = local_window(root/'patched/window',receipt['patched_source_revision'],binding)
        assert old_identity['native_libraries'] == new_identity['native_libraries']
        assert old_identity['python_files'] == new_identity['python_files']
        assert old_identity['launch_files'] == new_identity['launch_files']
        historical = historical_window(root,receipt['historical_archive_sha256'])
        assert receipt['remaining_runtime_processes'] == 0 and receipt['old_wsl_dirty_patch_unchanged'] is True
        return dict(status='NATIVE_AUDIT_LIFETIME_REPLAY_PASS',baseline=baseline,patched=patched,
            historical=historical,old_wsl_dirty_patch_unchanged=True,remaining_runtime_processes=0,
            moving_parent_follow_qualified=False,default_admission='NO_GO')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[3])
    args = parser.parse_args()
    print(json.dumps(verify(Path(__file__).resolve().parent,args.repo),indent=2,allow_nan=False))
