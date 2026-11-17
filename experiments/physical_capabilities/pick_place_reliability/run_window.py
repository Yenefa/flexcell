#!/usr/bin/env python3
"""Fixed four-slot pick/place window (physical capability C).

Scope: FUNCTIONAL_SMOKE_ONLY. Reuses the existing sim_smoke entrypoint and the
original `normal` / `dual_object` cases without changing objects, targets,
tolerances or task budgets. Keeps every failure; stops the window on an unknown
terminal state instead of dispatching another goal.

A slot counts as completed only when its classified status is `OK`. On an outer
timeout or a user interrupt the whole slot is asked to exit, and any process
that escaped into its own session is found by the slot-id environment marker and
stopped before the manifest is written. A partial `results.json` is still written
so an interrupted window is evidence instead of a silent gap.

Run: python3 experiments/physical_capabilities/pick_place_reliability/run_window.py \
        --out /artifacts/pick-place
"""
import argparse
import contextlib
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
INTERRUPT_EXITS = {130: 'SIGINT', 129: 'SIGHUP', 143: 'SIGTERM'}
INTERRUPT_CODES = {name: code for code, name in INTERRUPT_EXITS.items()}


class WindowSignal(Exception):
    """SIGTERM/SIGHUP delivered to the driver while a slot is running."""

    def __init__(self, signum):
        self.signum = signum
        self.name = signal.Signals(signum).name
        self.exit_code = 128 + signum
        super().__init__(self.name)


def _raise_window_signal(signum, _frame):
    raise WindowSignal(signum)


def _install_signal_handlers(signals=(signal.SIGTERM, signal.SIGHUP), sink=None):
    """Install handlers; with `sink`, record names instead of raising.

    `run_slot` uses the raising form so a signal inside a slot starts the bounded
    cleanup. `run_window` uses the sink form between slots, so a late signal is
    answered after the slot's row is written instead of unwinding the window.
    """
    previous = {}
    for signum in signals:
        try:
            previous[signum] = signal.getsignal(signum)
            if sink is None:
                signal.signal(signum, _raise_window_signal)
            else:
                signal.signal(signum, _record_window_signal(sink))
        except (OSError, ValueError):
            # Not the main thread: the slot still has its own timeout.
            previous.pop(signum, None)
    return previous


def _record_window_signal(sink):
    def handler(signum, _frame):
        sink.append(signal.Signals(signum).name)
    return handler


def _restore_signal_handlers(previous):
    for signum, handler in previous.items():
        try:
            signal.signal(signum, handler)
        except (OSError, ValueError):
            pass


def _ignore_during_cleanup():
    """A second Ctrl+C must not skip stopping the slot's processes."""
    previous = {}
    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        try:
            previous[signum] = signal.getsignal(signum)
            signal.signal(signum, signal.SIG_IGN)
        except (OSError, ValueError):
            pass
    return previous


class _DeferredSignals:
    """Collect termination signals instead of raising, so cleanup can finish."""

    def __init__(self):
        self.names = []

    def __call__(self, signum, _frame):
        self.names.append(signal.Signals(signum).name)


@contextlib.contextmanager
def _defer_signals(signals=(signal.SIGINT, signal.SIGTERM, signal.SIGHUP)):
    """Record signals raised inside the block and replay nothing.

    Cleanup between slots must not be interrupted halfway: the slot's processes
    have to be stopped and its row written first. The caller turns a non-empty
    `names` into an INTERRUPTED slot and stops the window.
    """
    state = _DeferredSignals()
    previous = {}
    for signum in signals:
        try:
            previous[signum] = signal.getsignal(signum)
            signal.signal(signum, state)
        except (OSError, ValueError):
            previous.pop(signum, None)
    try:
        yield state
    finally:
        _restore_signal_handlers(previous)


def reap_after_slot(marker, row, label):
    """Reap leftovers after a slot without losing the slot to a Ctrl+C.

    The per-slot reaper can wait for a `TERM`-ignoring process. If a signal
    arrives during that wait it is recorded instead of unwinding the window, the
    reap still finishes, and the caller keeps the slot's evidence as INTERRUPTED.
    """
    with _defer_signals() as pending:
        orphans, killed = reap(marker)
    if orphans:
        row['orphans_stopped'] = orphans
        row['orphans_needed_sigkill'] = killed
    if pending.names:
        return pending.names[0]
    return None



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
    except (OSError, ValueError):
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
    """Exactly one run-* directory, and it must carry a readable result.

    Counting only `run-*/result.json` would hide an extra attempt whose result was
    never written, so the directory count is what gets checked.
    """
    runs = sorted(p for p in Path(directory).glob('run-*') if p.is_dir())
    if len(runs) != 1:
        raise ValueError('expected exactly one run-* directory, found %d' % len(runs))
    result_path = runs[0] / 'result.json'
    result = read(result_path)
    if not isinstance(result, dict):
        raise ValueError('unreadable result: %s' % result_path)
    if result.get('case') != expected_case:
        raise ValueError('case %r != declared %r' % (result.get('case'), expected_case))
    return result, result_path


SOURCE_PATTERNS = (
    'src/flexcell/**/*',
    'infra/**/*',
    'scripts/**/*',
    'worlds/**/*',
    'config/**/*',
    'setup/flexcell_admin.py',
    'plan_execute.py',
    'experiments/physical_capabilities/pick_place_reliability/*.py',
    'experiments/physical_capabilities/pick_place_reliability/*.json',
    'experiments/physical_capabilities/pick_place_reliability/tests/*.py',
)


def source_hashes():
    """Hash everything the slot can execute or load, not only Python sources.

    `scripts/sim_smoke.py` starts the run, `config/` selects behaviour and
    `sim_profile.py` parses `worlds/*.sdf` directly, so a changed world must
    change the frozen source set. This mirrors the first-party scope used by
    `infra/runtime_identity.py` and adds the window's own definition. Build
    products and byte caches are skipped.
    """
    files = set()
    for pattern in SOURCE_PATTERNS:
        for path in ROOT.glob(pattern):
            if not path.is_file() or path.suffix == '.pyc':
                continue
            if '__pycache__' in path.parts or 'node_modules' in path.parts:
                continue
            files.add(path)
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(files)}


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


def reap(marker, grace_s=10.0):
    """Stop every process still carrying this slot id; return (found, needed_kill)."""
    if not marker:
        return 0, 0
    strays = owned_pids(marker)
    if not strays:
        return 0, 0
    signal_pids(strays, signal.SIGTERM)
    deadline = time.monotonic() + grace_s
    while time.monotonic() < deadline and owned_pids(marker):
        time.sleep(0.2)
    stubborn = owned_pids(marker)
    if stubborn:
        signal_pids(stubborn, signal.SIGKILL)
        time.sleep(0.2)
    return len(strays), len(stubborn)


def stop_slot(proc, marker, cleanup, grace_s=30.0):
    """Ask one slot to exit, then stop anything that escaped its session."""
    if proc.poll() is None:
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
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
    if not marker:
        return
    cleanup['survivors'], cleanup['killed'] = reap(marker)
    cleanup['left'] = len(owned_pids(marker))


def run_slot(argv, env, log, timeout_s, grace_s=30.0):
    """Run one slot and return (exit_code, cleanup).

    `subprocess.run(timeout=...)` only kills sim_smoke.py, so its own `finally`
    cleanup never runs; the stack and the recorder start in separate sessions and
    stay alive. Every descendant inherits the slot marker, so after the window
    gives up they can be found and stopped, and the count is recorded.

    A timeout, Ctrl+C (130) and SIGTERM/SIGHUP all take the same bounded cleanup
    path. The exit code tells `run_window` to stop the window and keep partial
    evidence instead of continuing to the next slot.
    """
    marker = env.get(SLOT_MARKER)
    proc = None
    cleanup = dict(graceful=False, survivors=0, killed=0, left=0)
    previous = _install_signal_handlers(
        (signal.SIGINT, signal.SIGTERM, signal.SIGHUP))
    try:
        try:
            proc = subprocess.Popen(argv, env=env, stdout=log, stderr=subprocess.STDOUT,
                                    start_new_session=True)
            proc.wait(timeout=timeout_s)
            return proc.returncode, cleanup
        except subprocess.TimeoutExpired:
            exit_code, reason = 124, 'timeout'
        except KeyboardInterrupt:
            exit_code, reason = 130, 'SIGINT'
        except WindowSignal as exc:
            exit_code, reason = exc.exit_code, exc.name

        cleanup['reason'] = reason
        ignored = _ignore_during_cleanup()
        try:
            if proc is not None:
                stop_slot(proc, marker, cleanup, grace_s)
        finally:
            _restore_signal_handlers(ignored)
        return exit_code, cleanup
    finally:
        _restore_signal_handlers(previous)


def run_window(prereg, out, runner=None):
    """Execute the declared slots. runner(label, case, slot_out, index) -> exit_code."""
    slots = prereg['slots']
    if not slots:
        raise ValueError('preregistration declares no slots')
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
    interrupted = None
    window_pending = []
    previous_handlers = _install_signal_handlers(
        (signal.SIGINT, signal.SIGTERM, signal.SIGHUP), sink=window_pending)
    try:
        for index, slot in enumerate(slots):
            label, case = slot['label'], slot['case']
            if window_pending and not interrupted:
                interrupted = window_pending[0]
                stopped = 'interrupted by %s between slots' % interrupted
            if stopped:
                rows.append(dict(label=label, case=case, status='NOT_RUN', reason=stopped))
                continue
            if time.monotonic() - started + slot_timeout > budget:
                rows.append(dict(label=label, case=case, status='NOT_RUN', reason='window budget'))
                continue

            slot_out = out / label
            slot_id = None
            cleanup = None
            interrupted_now = False
            if runner is None:
                slot_id = '%s-%d-%s' % (label, index, uuid.uuid4().hex[:8])
                argv = slot_command(label, case, slot_out, backend, skill_backend)
                with (out / (label + '_driver.log')).open('x') as log:
                    exit_code, cleanup = run_slot(argv, slot_env(label, index, slot_id),
                                                  log, slot_timeout, cleanup_grace)
                if exit_code in INTERRUPT_EXITS:
                    interrupted_now = True
                    interrupted = INTERRUPT_EXITS[exit_code]
                    stopped = 'interrupted by %s during %s' % (interrupted, label)
                    if cleanup['left']:
                        stopped += '; %d owned processes survived cleanup' % cleanup['left']
                elif exit_code == 124:
                    stopped = 'outer timeout; action terminal requires reconciliation'
                    if cleanup['left']:
                        stopped += '; %d owned processes survived cleanup' % cleanup['left']
            else:
                exit_code = runner(label, case, slot_out, index)
                if exit_code in INTERRUPT_EXITS:
                    interrupted_now = True
                    interrupted = INTERRUPT_EXITS[exit_code]
                    stopped = 'interrupted by %s during %s' % (interrupted, label)

            row = dict(label=label, case=case, driver_exit=exit_code, status='UNKNOWN',
                       task_completed=False)
            if interrupted_now:
                row['status'] = 'INTERRUPTED'
                row['reason'] = stopped
            if cleanup is not None:
                row['slot_id'] = slot_id
                row['timeout_cleanup'] = cleanup
            if runner is None:
                signal_name = reap_after_slot(slot_id, row, label)
                if signal_name:
                    interrupted_now = True
                    interrupted = signal_name
                    stopped = 'interrupted by %s during cleanup after %s' % (
                        signal_name, label)
                    row['status'] = 'INTERRUPTED'
                    row['reason'] = stopped
            if window_pending and not interrupted_now:
                interrupted_now = True
                interrupted = window_pending[0]
                stopped = 'interrupted by %s after %s' % (interrupted, label)
                row['status'] = 'INTERRUPTED'
                row['reason'] = stopped
            with _defer_signals() as pending:
                try:
                    result, result_path = one_result(slot_out, case)
                    task = result.get('task') or {}
                    row.update(result_path=str(result_path),
                               harness_status=result.get('status'),
                               outcome=task.get('outcome'),
                               error_code=task.get('error_code'),
                               wall_seconds=task.get('wall_seconds'),
                               err_m=task.get('final_position_error_m'),
                               task_reported_pass=(exit_code == 0
                                                   and result.get('status') == 'PASS'))
                    if not interrupted_now and not pending.names:
                        row['status'] = classify(result, exit_code)
                        row['task_completed'] = row['status'] == 'OK'
                        if row['status'] == 'UNKNOWN' and not stopped:
                            stopped = 'unknown terminal state in %s' % label
                except ValueError as exc:
                    row['error'] = str(exc)
                    if not interrupted_now and not pending.names:
                        row['status'] = 'UNKNOWN'
                        if not stopped:
                            stopped = 'unknown terminal state in %s (%s)' % (label, exc)

                rows.append(row)
            if pending.names:
                interrupted_now = True
                interrupted = pending.names[0]
                stopped = 'interrupted by %s while finalizing %s' % (
                    interrupted, label)
                row['status'] = 'INTERRUPTED'
                row['reason'] = stopped
                row['task_completed'] = False
            (out / 'results.partial.json').write_text(
                json.dumps(rows, indent=2, ensure_ascii=False))
    except (KeyboardInterrupt, WindowSignal) as exc:
        interrupted = getattr(exc, 'name', 'SIGINT')
        stopped = 'interrupted by %s between slots' % interrupted
        seen = {r.get('label') for r in rows}
        for slot in slots:
            if slot['label'] in seen:
                continue
            rows.append(dict(label=slot['label'], case=slot['case'],
                             status='NOT_RUN', reason=stopped))
        (out / 'results.partial.json').write_text(
            json.dumps(rows, indent=2, ensure_ascii=False))
    finally:
        pass  # handlers stay installed until the manifest is written

    try:
        with _defer_signals() as finishing:
            after = source_hashes()
            if finishing.names and interrupted is None:
                interrupted = finishing.names[0]
                stopped = 'interrupted by %s during finalization' % interrupted
            changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
            (out / 'source_before.json').write_text(
                json.dumps(before, indent=2, sort_keys=True))
            (out / 'source_after.json').write_text(
                json.dumps(after, indent=2, sort_keys=True))
            payload = dict(
                experiment=prereg.get('experiment'),
                scope='FUNCTIONAL_SMOKE_ONLY',
                preregistration=prereg,
                results=rows,
                source_unchanged=(before == after),
                source_changed=changed,
                source_files=len(before),
                source_scope=list(SOURCE_PATTERNS),
                stop_reason=stopped,
                interrupted=interrupted is not None,
                interrupt_signal=interrupted,
                all_slots_completed=(len(rows) == len(slots)
                                     and stopped is None
                                     and all(r.get('status') == 'OK' for r in rows)),
                baseline_promoted=False,
            )
            (out / 'results.json').write_text(
                json.dumps(payload, indent=2, ensure_ascii=False))
            manifest = {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in out.rglob('*')
                        if p.is_file() and p.name != 'SHA256_MANIFEST.json'}
            (out / 'SHA256_MANIFEST.json').write_text(
                json.dumps(manifest, indent=2, sort_keys=True))
        if finishing.names and payload.get('interrupt_signal') != finishing.names[0]:
            payload['interrupted'] = True
            payload['interrupt_signal'] = finishing.names[0]
            payload['stop_reason'] = payload.get('stop_reason') or (
                'interrupted by %s during finalization' % finishing.names[0])
            (out / 'results.json').write_text(
                json.dumps(payload, indent=2, ensure_ascii=False))
        return payload
    finally:
        _restore_signal_handlers(previous_handlers)


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
        interrupted=payload['interrupted'],
        stop_reason=payload['stop_reason']), ensure_ascii=False))
    if payload['interrupted']:
        return INTERRUPT_CODES.get(payload['interrupt_signal'], 130)
    return 0 if payload['all_slots_completed'] and payload['source_unchanged'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
