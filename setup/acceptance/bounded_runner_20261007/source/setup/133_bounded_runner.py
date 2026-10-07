#!/usr/bin/env python3
"""Default dry-run; explicit execution permits only six development slots / ten episodes."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'transferbench'))
import bounded_runner as runner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    dry = modes.add_parser('dry-run'); reg = modes.add_parser('register')
    for mode in (dry, reg):
        mode.add_argument('--package', required=True, type=Path)
        mode.add_argument('--expected-sha256', required=True)
    reg.add_argument('--out', required=True, type=Path)
    reg.add_argument('--history', required=True, type=Path)
    reg.add_argument('--budget', required=True, type=Path)
    reg.add_argument('--revision', required=True)
    execute = modes.add_parser('run'); inspect = modes.add_parser('status')
    for mode in (execute, inspect): mode.add_argument('--root', required=True, type=Path)
    execute.add_argument('--execute', action='store_true')
    execute.add_argument('--max-slots', type=int, default=6)
    for mode in (dry, reg, execute, inspect):
        mode.add_argument('--workspace', type=Path, default=Path('/home/ros/agentic_workcell_ws'))
    args = parser.parse_args()
    try:
        if args.mode == 'dry-run':
            result = runner.preview(args.package, args.expected_sha256, args.workspace)
        elif args.mode == 'register':
            result = runner.register(args.out, args.package, args.expected_sha256, args.workspace,
                                     args.history, args.budget, args.revision)
        elif args.mode == 'status' or not args.execute:
            result = runner.status(args.root, args.workspace)
            result['dispatch_authorized'] = False
        else:
            from bounded_live import LiveBackend
            result = runner.run(args.root, args.workspace, LiveBackend(args.workspace), args.max_slots)
    except Exception as exc:
        result = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc),
                  'dispatch_authorized': False, 'ready_for_large_test': False, 'n_ge_50': 'FROZEN'}
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result['ok'] and result.get('state') not in ('STOPPED', 'UNKNOWN_TAIL') else 2


if __name__ == '__main__':
    raise SystemExit(main())
