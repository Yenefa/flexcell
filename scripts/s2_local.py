#!/usr/bin/env python3
"""Prepare, then explicitly execute two bounded local Gazebo integration windows."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = [('normal', 's2-joint-camera.json'),
           ('false_attach', 's2-false-attach-camera.json')]


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def identity():
    """Read source/import/install provenance; no simulator or robot service."""
    result = subprocess.run([sys.executable, str(ROOT / 'infra/runtime_identity.py')],
                            check=True, capture_output=True, text=True)
    value = json.loads(result.stdout)
    require(not value['mismatches'], 'source/import/install mismatch')
    require(re.fullmatch('[0-9a-f]{40}', value['source_revision']) is not None,
            'build the candidate image with SOURCE_REV set to its full Git SHA')
    require(re.fullmatch('[0-9a-f]{64}', value['source_tree_sha256']) is not None,
            'source tree fingerprint absent')
    return value


def prepare(out):
    current = identity()
    manifests = []
    for case, name in WINDOWS:
        path = ROOT / 'infra' / name
        declaration = read(path)
        require(declaration['camera'] is True and declaration['backend'] == 'detachable_joint'
                and declaration['skill_backend'] == 'mtc'
                and declaration['qualification_no_recovery'] is True
                and len(declaration['episodes']) == 1
                and declaration['episodes'][0]['case'] == case,
                'unexpected integration declaration: ' + name)
        manifests.append(dict(case=case, manifest=name, sha256=digest(path)))
    out.mkdir(parents=True, exist_ok=False)
    (out / 'declarations').mkdir()
    for item in manifests:
        shutil.copyfile(ROOT / 'infra' / item['manifest'], out / 'declarations' / item['manifest'])
    save(out / 'identity.json', current)
    plan = dict(schema_version=1, status='PREPARED_NOT_RUN',
                declared_host_role='S2', host_role_verified=False,
                source_revision=current['source_revision'], windows=manifests,
                logical_tasks=2, no_replacements=True, default_admission='NO_GO',
                observation_source='SIMULATION_GROUND_TRUTH; RGB is data-only',
                fault_boundary='guard_input_pose; not physical slip')
    save(out / 'plan.json', plan)
    return plan


def camera_evidence(run, injection=None):
    from export_lerobot import episode
    result, frames, _ = episode(run)  # existing complete aligned-frame/gap gate
    for row in frames:
        image = (run / 'data' / row['image']).resolve()
        require(image.is_relative_to((run / 'data').resolve()), 'image escapes run data')
        with image.open('rb') as stream:
            require(stream.read(8) == b'\x89PNG\r\n\x1a\n', 'missing or invalid PNG: ' + str(image))
    if injection is not None:
        lo, hi = injection['injection_first_sim_ns'], injection['injection_last_sim_ns']
        require(frames[0]['sim_ns'] <= lo <= hi <= frames[-1]['sim_ns'],
                'RGB does not cover the injected interval')
        visible = [row for row in frames if lo <= row['sim_ns'] <= hi]
        require(visible, 'no same-round RGB frame during injection')
        preview = visible[0]
    else:
        preview = frames[len(frames) // 2]
    return dict(frames=len(frames), preview=preview['image'],
                preview_sim_ns=preview['sim_ns'],
                preview_sha256=digest(run / 'data' / preview['image']),
                runtime_fingerprint=result['runtime_fingerprint'],
                interpretation='Aligned raw RGB files; no perception or physical-slip claim')


def run_window(manifest, out, log):
    command = [sys.executable, str(ROOT / 'scripts/sim_window.py'),
               '--manifest', str(manifest), '--out', str(out),
               '--backend', 'detachable_joint', '--skill-backend', 'mtc']
    with log.open('x') as stream:
        return subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT).returncode


def execute(out):
    plan = read(out / 'plan.json')
    expected = [dict(case=case, manifest=name, sha256=digest(ROOT / 'infra' / name))
                for case, name in WINDOWS]
    require(plan['status'] == 'PREPARED_NOT_RUN' and plan['windows'] == expected,
            'plan differs from the fixed candidate; do not modify or resume it')
    for item in expected:
        require(digest(out / 'declarations' / item['manifest']) == item['sha256'],
                'prepared declaration changed')
    current = identity()
    require(read(out / 'identity.json') == current
            and plan['source_revision'] == current['source_revision'],
            'candidate identity changed after preparation')
    # Exclusive reservation survives crashes. A second invocation cannot replace samples.
    with (out / 'attempt.json').open('x') as stream:
        json.dump(dict(pid=os.getpid(), source_revision=plan['source_revision']), stream)
    report = dict(schema_version=1, status='RUNNING', default_admission='NO_GO',
                  declared_host_role='S2', host_role_verified=False, no_replacements=True,
                  source_revision=plan['source_revision'],
                  windows=[dict(case=case, status='NOT_RUN') for case, _ in WINDOWS])
    save(out / 'report.json', report)
    try:
        for index, item in enumerate(expected):
            entry = report['windows'][index]
            entry['status'] = 'RUNNING'
            save(out / 'report.json', report)
            directory = out / item['case']
            code = run_window(out / 'declarations' / item['manifest'], directory,
                              out / (item['case'] + '.log'))
            entry['returncode'] = code
            require(code == 0, item['case'] + ' window failed; no replacement or next window')
            window = read(directory / 'window.json')
            require(window['status'] == 'FUNCTIONAL_WINDOW_PASS' and len(window['episodes']) == 1,
                    'missing or incomplete window evidence')
            trial = window['episodes'][0]
            require(trial['case'] == item['case'] and trial['object'] == 'target_box_a'
                    and trial['result'].get('expectation_met') is True,
                    'window result does not match its declaration')
            if item['case'] == 'false_attach':
                injection = trial['false_attach_evidence']
                require(injection['status'] == 'FALSE_ATTACH_REJECTED'
                        and injection['boundary'] == 'guard_input_pose'
                        and injection['place_dispatched'] is False,
                        'guard response evidence missing')
            else:
                injection = None
            run = Path(trial['run']).resolve()
            require(run.is_relative_to(directory.resolve()), 'run is outside this window')
            camera = camera_evidence(run, injection)
            shutil.copyfile(run / 'data' / camera['preview'], out / (item['case'] + '-preview.png'))
            entry.update(status='PASS', window=str(directory / 'window.json'), camera=camera)
            save(out / 'report.json', report)
        report['status'] = 'LOCAL_INTEGRATION_PASS'
    except (Exception, KeyboardInterrupt) as exc:
        if 'entry' in locals() and entry['status'] == 'RUNNING':
            entry['status'] = 'STOPPED'
        report.update(status='STOPPED', error=str(exc) or type(exc).__name__)
    finally:
        save(out / 'report.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--execute', action='store_true', help='Execute a previously prepared plan once')
    args = parser.parse_args()
    report = execute(args.out) if args.execute else prepare(args.out)
    print(json.dumps(report, indent=2, allow_nan=False))
    return int(report['status'] == 'STOPPED')


if __name__ == '__main__':
    raise SystemExit(main())
