#!/usr/bin/env python3
"""Replay the complete bounded window; no ROS services or robot actions."""
import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import sys
import tempfile
import zipfile


def verify(capsule, repo, planner=False):
    sys.path[:0] = [str(repo/'scripts'), str(repo/'src/flexcell/flexcell_skills')]
    from preposition_gate import verify_run as preposition
    from joint_follow_gate import verify_run as follow
    from integrated_contact_gate import verify_run as contact

    receipt = json.loads((capsule/'receipt.json').read_text())
    archive = capsule/'raw-window.zip'
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == receipt['archive_sha256']
    with tempfile.TemporaryDirectory(prefix='flexcell-world-hold-') as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(archive) as bundle:
            assert bundle.testzip() is None
            assert len(bundle.namelist()) == len(set(bundle.namelist())) == len(receipt['files'])
            assert set(bundle.namelist()) == set(receipt['files'])
            for name, digest in receipt['files'].items():
                parts = PurePosixPath(name)
                assert not parts.is_absolute() and '..' not in parts.parts
                target = root.joinpath(*parts.parts)
                assert target.resolve().is_relative_to(root.resolve())
                data = bundle.read(name)
                assert hashlib.sha256(data).hexdigest() == digest, name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        window = json.loads((root/'window/window.json').read_text())
        declaration = json.loads((root/'window/declaration.json').read_text())
        assert window['status'] == 'FUNCTIONAL_WINDOW_PASS' and window['no_replacements'] is True
        assert len(window['episodes']) == len(declaration['episodes']) == 1
        assert hashlib.sha256((root/'window/declaration.json').read_bytes()).hexdigest() == window['declaration_sha256']
        runs = list((root/'window').glob('trial-*/run-*'))
        assert len(runs) == 1
        run = runs[0]
        result = json.loads((run/'result.json').read_text())
        assert result == window['episodes'][0]['result']
        assert result['status'] == 'PASS' and result['expectation_met'] is True
        assert result['physical_tasks_dispatched'] == 1 and result['native_identity_verified_before_dispatch'] is True
        assert result['task']['outcome_val'] == 0 and result['task']['skip_verify'] is False
        assert result['task']['fsm_trace'] == ['PICK_A(attempt=1):OK', 'PLACE_A:OK', 'VERIFY_A(attempt=1):OK']
        health = json.loads((run/'health_after.stdout').read_text())
        assert health['ok'] and not health['hard_fail'] and health['checks']['task_state'] == 'IDLE'
        assert health['checks']['carry_engaged'] is False
        identifier = declaration['episodes'][0]['object']
        p = preposition(run, identifier, declaration)
        f = follow(run, identifier, min_duration_s=10., physics_step_ns=2_000_000)
        c = contact(run, identifier, declaration)
        assert p['runtime']['world_motion_observation'] == 'RECORDED'
        assert set(p['runtime']['world_at_rest']) == {'parent', 'body'}
        raw = [json.loads(line) for line in (run/'physics_steps.jsonl').read_text().splitlines()]
        assert all(b['sim_ns']-a['sim_ns'] == 2_000_000 and b['monotonic_ns'] > a['monotonic_ns']
                   for a,b in zip(raw, raw[1:]))
        task = [row for row in raw if result['task_start_monotonic_ns'] <= row['monotonic_ns'] <= result['task_end_monotonic_ns']]
        assert len(task) > 2
        age_ms = (result['task_end_monotonic_ns']-task[-1]['monotonic_ns'])/1e6
        assert 0 <= age_ms <= 500
        error = math.dist(task[-1]['objects'][identifier]['pose'][:3], result['goal_pose'])
        assert math.isfinite(error) and error < .06
        identity = json.loads((run/'identity.stdout').read_text())
        assert identity['source_revision'] == receipt['source_revision'] and identity['mismatches'] == []
        native = json.loads((run/'runtime_native_mapping.json').read_text())
        for relative in ('lib/libflexcell_physics_trace.so', 'lib/libflexcell_contact_trace.so',
                         'lib/libflexcell_detachable_carry.so', 'lib/flexcell_mtc/mtc_planner'):
            assert [digest for path,digest in native.items() if Path(path).name == Path(relative).name] == [identity['native_libraries'][relative]]
        planner_report = None
        if planner:
            from planner_snapshot_gate import verify_run as verify_planner
            planner_report = verify_planner(run, identifier)
        return dict(status='WORLD_HOLD_WINDOW_REPLAY_PASS', source_revision=identity['source_revision'],
                    window_id=window['window_id'], raw_steps=len(raw), raw_step_gaps=0,
                    raw_final_error_mm=error*1000, latest_physics_age_ms=age_ms,
                    post_health_checks=len(health['checks']), preposition=p, follow=f, contact=c,
                    planner=planner_report, default_admission='NO_GO')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--planner', action='store_true', help='also decode CDR with the ROS message packages')
    args = parser.parse_args()
    print(json.dumps(verify(Path(__file__).resolve().parent, args.repo, args.planner),indent=2,allow_nan=False))
