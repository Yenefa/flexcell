#!/usr/bin/env python3
"""Guard the three existing Hybrid slots; default status never dispatches."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'transferbench'))
import bounded_hybrid_guard as guard
import qualification_prepare as q


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    reg = modes.add_parser('register')
    reg.add_argument('--root', type=Path, required=True)
    reg.add_argument('--out', type=Path, required=True)
    reg.add_argument('--revision', required=True)
    inspect = modes.add_parser('status'); execute = modes.add_parser('run')
    for mode in (inspect, execute):
        mode.add_argument('--guard', type=Path, required=True)
        mode.add_argument('--expected-sha256', required=True)
    execute.add_argument('--execute', action='store_true')
    execute.add_argument('--max-slots', type=int, default=1)
    for mode in (reg, inspect, execute):
        mode.add_argument('--workspace', type=Path, default=Path('/home/ros/agentic_workcell_ws'))
    args = parser.parse_args()
    try:
        if args.mode == 'run':
            q.require(1 <= args.max_slots <= 3, 'Hybrid continuation max-slots must be 1..3')
        if args.mode == 'register':
            result = guard.register(args.out, args.root, args.workspace, args.revision)
        elif args.mode == 'status' or not args.execute:
            result = guard.status(args.guard, args.expected_sha256, args.workspace)
        else:
            from bounded_live import LiveBackend
            result = guard.run(args.guard, args.expected_sha256, args.workspace,
                               LiveBackend(args.workspace), args.max_slots)
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
        result = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc),
                  'dispatch_authorized': False, 'ready_for_large_test': False, 'n_ge_50': 'FROZEN'}
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result['ok'] and result.get('state') not in ('STOPPED', 'UNKNOWN_TAIL') else 2


if __name__ == '__main__':
    raise SystemExit(main())
