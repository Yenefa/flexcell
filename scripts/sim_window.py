#!/usr/bin/env python3
"""Execute a declared <=5-task window once, stopping on the first gate failure."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid
import os
import signal

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--backend', choices=['velocity_servo', 'detachable_joint', 'teleport'], required=True)
    parser.add_argument('--skill-backend', choices=['legacy', 'mtc'], required=True)
    args = parser.parse_args()
    declaration = json.loads(args.manifest.read_text())
    if declaration['max_logical_tasks'] != 5 or not 1 <= len(declaration['episodes']) <= 5:
        raise ValueError('window must declare at most five logical tasks')
    if declaration.get('backend', args.backend) != args.backend or declaration.get('skill_backend', args.skill_backend) != args.skill_backend:
        raise ValueError('requested backend differs from declared window')
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / 'declaration.json').write_bytes(args.manifest.read_bytes())
    result = dict(schema_version=1, status='INCOMPLETE', episodes=[],
                  declaration_sha256=hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
                  backend=args.backend, skill_backend=args.skill_backend,
                  window_id=uuid.uuid4().hex, no_replacements=True)
    fingerprint = None
    try:
        for index, spec in enumerate(declaration['episodes']):
            cell = args.out / ('trial-%02d' % (index + 1))
            command = [sys.executable, str(ROOT / 'scripts/sim_smoke.py'), '--out', str(cell),
                       '--backend', args.backend, '--skill-backend', args.skill_backend,
                       '--case', spec['case'], '--object', spec['object']]
            if declaration.get('camera'):
                command.append('--camera')
            if declaration.get('false_attach'):
                injection = declaration['false_attach']
                command.extend(['--false-attach', '%s:%s:%s'
                                % (injection['object'], injection['offset_m'], injection['hold_s'])])
            if declaration.get('joint_hold_sim_s'):
                command.extend(['--joint-hold-sim-s', str(declaration['joint_hold_sim_s'])])
            if declaration.get('physics_step_s') is not None:
                command.extend(['--physics-step-s', str(declaration['physics_step_s'])])
            if declaration.get('contact_trace'):
                command.append('--contact-trace')
            if declaration.get('qualification_no_recovery'):
                command.append('--qualification-no-recovery')
            if declaration.get('required_planner_diagnostics'):
                command.append('--planner-diagnostics')
            if declaration.get('release_clearance_m') is not None:
                command.extend(['--release-clearance-m', str(declaration['release_clearance_m'])])
            if declaration.get('min_preflight_rtf'):
                command.extend(['--min-preflight-rtf', str(declaration['min_preflight_rtf'])])
            if declaration.get('world_sha256'):
                command.extend(['--expected-world-sha256', declaration['world_sha256']])
            if declaration.get('semantic_config_sha256'):
                command.extend(['--expected-config-sha256', declaration['semantic_config_sha256']])
            if declaration.get('camera_egl_vendor_sha256'):
                command.extend(['--expected-egl-vendor-sha256', declaration['camera_egl_vendor_sha256']])
            if fingerprint is not None:
                command.extend(['--expected-fingerprint', fingerprint])
            with (args.out / ('trial-%02d.log' % (index + 1))).open('x') as log:
                proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    proc.wait(timeout=900)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGTERM)  # harness performs its owned cleanup
                    try:
                        proc.wait(timeout=90)
                    except subprocess.TimeoutExpired:
                        # Last resort: only process groups whose start identities
                        # were recorded by this exact run, never a name-wide pkill.
                        for record in cell.glob('run-*/owned_processes.jsonl'):
                            for line in record.read_text().splitlines():
                                item = json.loads(line)
                                try:
                                    stat = Path('/proc/%d/stat' % item['pid']).read_text().rsplit(')', 1)[1].split()
                                    if stat[19] == item['start_ticks'] and os.getpgid(item['pid']) == item['pid']:
                                        os.killpg(item['pid'], signal.SIGKILL)
                                except ProcessLookupError:
                                    pass
                                except FileNotFoundError:
                                    pass
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait(timeout=5)
                    raise RuntimeError('trial timeout; terminal unknown; window stopped')
            runs = list(cell.glob('run-*'))
            if len(runs) != 1:
                raise RuntimeError('missing or ambiguous run directory')
            outcome = json.loads((runs[0] / 'result.json').read_text())
            result['episodes'].append(dict(spec, run=str(runs[0]), result=outcome))
            if proc.returncode != 0 or outcome.get('expectation_met') is not True:
                raise RuntimeError('trial %d gate failed; window stopped with no replacement' % (index + 1))
            if declaration.get('required_planner_diagnostics'):
                if spec['case'] != 'normal' or args.skill_backend != 'mtc':
                    raise ValueError('planner snapshot gate requires one normal MTC task')
                from planner_snapshot_gate import verify_run as verify_planner
                result['episodes'][-1]['planner_evidence'] = verify_planner(runs[0], spec['object'])
            if declaration.get('required_carry_follow'):
                if args.backend != 'detachable_joint':
                    raise ValueError('follow window requires the explicitly selected joint backend')
                from joint_follow_gate import verify_run
                step = declaration.get('physics_step_s')
                result['episodes'][-1]['follow_evidence'] = verify_run(
                    runs[0], spec['object'], min_duration_s=declaration.get('min_follow_sim_s', 0.),
                    physics_step_ns=int(step * 1e9) if step is not None else None,
                    require_camera=bool(declaration.get('camera')))
            if declaration.get('required_joint_contacts'):
                from integrated_contact_gate import verify_run as verify_contacts
                result['episodes'][-1]['contact_evidence'] = verify_contacts(runs[0], spec['object'], declaration)
            if declaration.get('required_preposition_reference'):
                if args.backend != 'detachable_joint':
                    raise ValueError('a pre-attach reference requires the explicitly selected joint backend')
                from preposition_gate import verify_run as verify_preposition
                result['episodes'][-1]['preposition_evidence'] = verify_preposition(
                    runs[0], spec['object'], declaration)
            if declaration.get('required_false_attach'):
                from false_attach_gate import verify_run as verify_false_attach
                result['episodes'][-1]['false_attach_evidence'] = verify_false_attach(
                    runs[0], spec['object'], declaration)
            current = outcome.get('runtime_fingerprint')
            if not current or fingerprint is not None and current != fingerprint:
                raise RuntimeError('runtime fingerprint drift; window stopped')
            fingerprint = current
        result.update(status='FUNCTIONAL_WINDOW_PASS', runtime_fingerprint=fingerprint)
    except (RuntimeError, OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired) as exc:
        result.update(status='STOPPED', error=str(exc))
    finally:
        (args.out / 'window.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
        print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'FUNCTIONAL_WINDOW_PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
