#!/usr/bin/env python3
"""Fixed four-slot pick/place window (physical capability C).

Scope: FUNCTIONAL_SMOKE_ONLY. Reuses the existing sim_smoke entrypoint and the
original `normal` / `dual_object` cases without changing objects, targets,
tolerances or task budgets. Keeps every failure; stops the window on an unknown
terminal state instead of dispatching another goal.

A slot counts as completed only when its classified status is `OK`. On an outer
timeout the whole slot is asked to exit, and any process that escaped into its
own session is found by the slot-id environment marker and stopped before the
manifest is written.

Run: python3 experiments/physical_capabilities/pick_place_reliability/run_window.py \
        --out /artifacts/pick-place
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
SLOT_MARKER = 'FLEXCELL_WINDOW_SLOT_ID'


def _repo_root():
    """Locate the repository without assuming a fixed directory depth."""
    env = os.environ.get('FLEXCELL_REPO')
    if env:
        return Path(env)
    for candidate in HERE.parents:
        if (candidate / 'src/flexcell').is_dir():
            return candidate
    return Path.cwd()


ROOT = _repo_root()
DEFAULT_PREREG = HERE / 'preregistration.json'


def read(path):
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, ValueError):
        return None


def unknown(value):
    """Recursively detect an unknown terminal state: missing evidence is UNKNOWN."""
    if isinstance(value, dict):
        if (value.get('status') in ('STATE_UNKNOWN', 'ACTION_TERMINAL_UNKNOWN')
                or value.get('motion_terminal_known') is False
                or value.get('terminal_known') is False
                or value.get('error_code') == 33):
            return True
        return any(unknown(v) for v in value.values())
    if isinstance(value, list):
        return any(unknown(v) for v in value)
    if isinstance(value, str) and value.startswith(('{', '[')):
        try:
            return unknown(json.loads(value))
        except ValueError:
            pass
    return False


def one_result(directory, expected_case):
    """Exactly one run-* directory whose case matches the declared slot."""
    paths = list(Path(directory).glob('run-*/result.json'))
    if len(paths) != 1:
        raise ValueError('expected exactly one run-* result, found %d' % len(paths))
    result = read(paths[0])
    if not isinstance(result, dict):
        raise ValueError('unreadable result: %s' % paths[0])
    if result.get('case') != expected_case:
        raise ValueError('case %r != declared %r' % (result.get('case'), expected_case))
    return result, paths[0]


def source_hashes():
    paths = list((ROOT / 'src/flexcell').rglob('*.py'))
    paths += list((ROOT / 'src/flexcell/flexcell_interfaces').rglob('*.action'))
    paths += list((ROOT / 'src/flexcell/flexcell_interfaces').rglob('*.msg'))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths)}


def slot_command(label, case, slot_out, backend, skill_backend):
    return [sys.executable, str(ROOT / 'scripts/sim_smoke.py'),
            '--out', str(slot_out), '--case', case,
            '--backend', backend, '--skill-backend', skill_backend]


def slot_env(label, index, slot_id=None):
    """Per-slot ROS/Gazebo isolation: a leftover graph must not leak into the next slot.

    The slot id is inherited by every descendant, so a timeout can stop its own
    processes by identity instead of guessing from names.
    """
    env = dict(os.environ, ROS_DOMAIN_ID=str(51 + index), GZ_PARTITION='pp-' + label)
    if slot_id:
        env[SLOT_MARKER] = slot_id
    return env


def classify(result, exit_code):
    if exit_code == 124:
        return 'UNKNOWN'
    if unknown(result):
        return 'UNKNOWN'
    if exit_code == 0 and result.get('status') == 'PASS':
        return 'OK'
    return 'TASK_FAILED'


def owned_pids(marker):
    """PIDs whose environment carries this slot's marker (Linux only)."""
    needle = ('%s=%s' % (SLOT_MARKER, marker)).encode()
    found = []
    proc = Path('/proc')
    if not proc.is_dir():
        return found
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == os.getpid():
            continue
        try:
            environ = (entry / 'environ').read_bytes()
        except OSError:
            continue
        if needle in environ:
            found.append(pid)
    return found


def signal_pids(pids, sig):
    for pid in pids:
        try:
            os.kill(pid, sig)
        except OSError:
            pass


def signal_group(pid, sig):
    try:
        os.killpg(pid, sig)
    except (AttributeError, OSError):
        try:
            os.kill(pid, sig)
        except OSError:
            pass


def run_slot(argv, env, log, timeout_s, grace_s=30.0):
    """Run one slot and return (exit_code, cleanup).

    `subprocess.run(timeout=...)` only kills sim_smoke.py, so its own `finally`
    cleanup never runs; the stack and the recorder start in separate sessions and
    stay alive. Every descendant inherits the slot marker, so after the window
    gives up they can be found and stopped, and the count is recorded.
    """
    marker = env.get(SLOT_MARKER)
    proc = subprocess.Popen(argv, env=env, stdout=log, stderr=subprocess.STDOUT,
                            start_new_session=True)
    cleanup = dict(graceful=False, survivors=0, killed=0, left=0)
    try:
        proc.wait(timeout=timeout_s)
        return proc.returncode, cleanup
    except subprocess.TimeoutExpired:
        pass

    signal_group(proc.pid, signal.SIGINT)
    try:
        proc.wait(timeout=grace_s)
        cleanup['graceful'] = True
    except subprocess.TimeoutExpired:
        signal_group(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=5)
            cleanup['graceful'] = True
        except subprocess.TimeoutExpired:
            signal_group(proc.pid, signal.SIGKILL)
            proc.wait()

    if not marker:
        return 124, cleanup

    strays = owned_pids(marker)
    cleanup['survivors'] = len(strays)
    if strays:
        signal_pids(strays, signal.SIGTERM)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and owned_pids(marker):
            time.sleep(0.2)
        left = owned_pids(marker)
        if left:
            signal_pids(left, signal.SIGKILL)
            time.sleep(0.2)
        cleanup['killed'] = len(left)
    cleanup['left'] = len(owned_pids(marker))
    return 124, cleanup


def run_window(prereg, out, runner=None):
    """Execute the declared slots. runner(label, case, slot_out, index) -> exit_code."""
    slots = prereg['slots']
    slot_timeout = float(prereg['slot_timeout_s'])
    cleanup_grace = float(prereg.get('cleanup_grace_s', 30.0))
    budget = float(prereg['window_budget_s'])
    backend = prereg['backend']
    skill_backend = prereg['skill_backend']
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    before = source_hashes()
    rows = []
    started = time.monotonic()
    stopped = None

    for index, slot in enumerate(slots):
        label, case = slot['label'], slot['case']
        if stopped:
            rows.append(dict(label=label, case=case, status='NOT_RUN', reason=stopped))
            continue
        if time.monotonic() - started + slot_timeout > budget:
            rows.append(dict(label=label, case=case, status='NOT_RUN', reason='window budget'))
            continue

        slot_out = out / label
        slot_id = None
        cleanup = None
        if runner is None:
            slot_id = '%s-%d-%s' % (label, index, uuid.uuid4().hex[:8])
            argv = slot_command(label, case, slot_out, backend, skill_backend)
            with (out / (label + '_driver.log')).open('x') as log:
                exit_code, cleanup = run_slot(argv, slot_env(label, index, slot_id),
                                              log, slot_timeout, cleanup_grace)
            if exit_code == 124:
                stopped = 'outer timeout; action terminal requires reconciliation'
                if cleanup['left']:
                    stopped += '; %d owned processes survived cleanup' % cleanup['left']
        else:
            exit_code = runner(label, case, slot_out, index)

        row = dict(label=label, case=case, driver_exit=exit_code, status='UNKNOWN',
                   task_completed=False)
        if cleanup is not None:
            row['slot_id'] = slot_id
            row['timeout_cleanup'] = cleanup
        try:
            result, result_path = one_result(slot_out, case)
            task = result.get('task') or {}
            row.update(result_path=str(result_path),
                       harness_status=result.get('status'),
                       outcome=task.get('outcome'),
                       error_code=task.get('error_code'),
                       wall_seconds=task.get('wall_seconds'),
                       err_m=task.get('final_position_error_m'),
                       task_reported_pass=(exit_code == 0 and result.get('status') == 'PASS'))
            row['status'] = classify(result, exit_code)
            row['task_completed'] = row['status'] == 'OK'
            if row['status'] == 'UNKNOWN' and not stopped:
                stopped = 'unknown terminal state in %s' % label
        except ValueError as exc:
            row['status'] = 'UNKNOWN'
            row['error'] = str(exc)
            if not stopped:
                stopped = 'unknown terminal state in %s (%s)' % (label, exc)

        rows.append(row)
        (out / 'results.partial.json').write_text(
            json.dumps(rows, indent=2, ensure_ascii=False))

    after = source_hashes()
    payload = dict(
        experiment=prereg.get('experiment'),
        scope='FUNCTIONAL_SMOKE_ONLY',
        results=rows,
        source_unchanged=(before == after),
        stop_reason=stopped,
        all_slots_completed=(len(rows) == len(slots)
                             and stopped is None
                             and all(r.get('status') == 'OK' for r in rows)),
        baseline_promoted=False,
    )
    (out / 'results.json').write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    manifest = {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in out.rglob('*') if p.is_file() and p.name != 'SHA256_MANIFEST.json'}
    (out / 'SHA256_MANIFEST.json').write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--preregistration', type=Path, default=DEFAULT_PREREG)
    args = parser.parse_args(argv)

    prereg = read(args.preregistration)
    if not isinstance(prereg, dict) or not prereg.get('slots'):
        raise SystemExit('invalid preregistration: %s' % args.preregistration)
    payload = run_window(prereg, args.out)
    print('WINDOW ' + json.dumps(dict(
        all_slots_completed=payload['all_slots_completed'],
        source_unchanged=payload['source_unchanged'],
        stop_reason=payload['stop_reason']), ensure_ascii=False))
    return 0 if payload['all_slots_completed'] and payload['source_unchanged'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
