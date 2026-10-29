#!/usr/bin/env python3
"""Run one declared standalone contact pipeline spike, with no arm or carry tasks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import uuid

from contact_gate import require, verify_file
from sim_smoke import command, remember_owned, terminate_owned

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mapped_libraries(pid):
    """Read only this run's process tree; no process-name-wide operations."""
    parents = {}
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            fields = path.read_text().rsplit(')', 1)[1].split()
            parents[int(path.parent.name)] = int(fields[1])
        except (OSError, ValueError, IndexError):
            continue
    owned = {pid}
    while True:
        added = {child for child, parent in parents.items() if parent in owned}
        if added <= owned: break
        owned |= added
    paths = set()
    for child in owned:
        try:
            for line in Path('/proc/%d/maps' % child).read_text().splitlines():
                value = line.split(maxsplit=5)[-1]
                name = Path(value).name
                if (value.startswith('/') and
                        ('flexcell_contact_trace' in name or
                         name.startswith('libgz') and ('physics' in name or 'contact' in name))):
                    paths.add(value)
        except OSError:
            continue
    return {path: digest(path) for path in sorted(paths) if Path(path).is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--declaration', type=Path, default=ROOT / 'infra/contact-probe.json')
    args = parser.parse_args()
    spec = json.loads(args.declaration.read_text())
    require(spec['schema_version'] == 1 and spec['kind'] == 'CONTACT_SENSOR_PIPELINE_SPIKE_ONLY' and
            spec['logical_robot_tasks'] == 0 and 1 <= spec['samples'] <= 5000 and
            spec['step_ns'] == 2_000_000, 'invalid bounded sensor-only declaration')
    args.out.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(args.declaration, args.out / 'declaration.json')
    source_world = ROOT / spec['world']
    result = dict(schema_version=1, status='STOPPED', logical_robot_tasks=0,
                  declaration_sha256=digest(args.declaration), source_world_sha256=digest(source_world),
                  no_replacements=True, default_admission='NO_GO')
    proc = None
    log = (args.out / 'simulator.log').open('x')
    def interrupted(signum, _frame):
        raise RuntimeError('contact probe interrupted by signal %d' % signum)
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        require(result['source_world_sha256'] == spec['world_sha256'], 'world differs from declaration')
        require(command([sys.executable, str(ROOT / 'infra/runtime_identity.py')], args.out / 'identity') == 0,
                'source/install identity mismatch')
        identity = json.loads((args.out / 'identity.stdout').read_text())
        library_sha = identity['native_libraries'].get('lib/libflexcell_contact_trace.so')
        require(library_sha, 'contact observer was not built')
        world = args.out / 'world.sdf'; shutil.copyfile(source_world, world)
        capture = args.out / 'contact_steps.jsonl'
        result['partition'] = 'flexcell-contact-' + uuid.uuid4().hex
        env = dict(os.environ, FLEXCELL_CONTACT_STEP_LOG=str(capture.resolve()),
                   GZ_PARTITION=result['partition'])
        argv = ['gz', 'sim', '-s', '-r', '-v', '4', '--iterations', str(spec['samples']), str(world)]
        result['command'] = argv
        result['runtime_fingerprint'] = hashlib.sha256(json.dumps(dict(
            identity=identity, declaration=spec), sort_keys=True).encode()).hexdigest()
        proc = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
        remember_owned(args.out, proc)
        deadline = time.monotonic() + 30
        loaded = {}
        while proc.poll() is None and time.monotonic() < deadline:
            if capture.exists() and capture.stat().st_size:
                loaded = mapped_libraries(proc.pid)
                if any('libflexcell_contact_trace' in path and sha == library_sha
                       for path, sha in loaded.items()):
                    break
            time.sleep(.02)
        (args.out / 'loaded_libraries.json').write_text(json.dumps(loaded, indent=2) + '\n')
        require(any('libflexcell_contact_trace' in path and sha == library_sha for path, sha in loaded.items()),
                'actual loaded observer identity unconfirmed')
        require(any('dartsim' in path for path in loaded), 'declared DART engine identity unconfirmed')
        proc.wait(timeout=30)
        result['simulator_exit'] = proc.returncode
        require(proc.returncode == 0, 'simulator failed; preserve data without replacement')
        result['evidence'] = verify_file(capture, spec)
        result.update(status='CONTACT_PIPELINE_PASS', raw_sha256=digest(capture))
    except (Exception, KeyboardInterrupt) as exc:
        result['error'] = repr(exc)
    finally:
        if proc is not None:
            terminate_owned(proc)
            result['owned_exit'] = proc.returncode
        log.close()
        (args.out / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
        print(json.dumps(result, indent=2, allow_nan=False), flush=True)
    return 0 if result['status'] == 'CONTACT_PIPELINE_PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
