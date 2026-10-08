#!/usr/bin/env python3
"""Register two direct Pick diagnostics; default run only inspects the plan."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'transferbench'))
import grasp_diagnostic as diagnostic


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    register = modes.add_parser('register')
    register.add_argument('--deployment', type=Path, required=True)
    register.add_argument('--revision', required=True)
    register.add_argument('--protect', type=Path, action='append', required=True)
    inspect = modes.add_parser('status'); run = modes.add_parser('run')
    for mode in (inspect, run): mode.add_argument('--expected-sha256', required=True)
    run.add_argument('--execute', action='store_true')
    for mode in (register, inspect, run):
        mode.add_argument('--root', type=Path, required=True)
        mode.add_argument('--workspace', type=Path, default=diagnostic.AUTHORITY)
    args = parser.parse_args()
    try:
        if args.mode == 'register':
            result = diagnostic.register(args.root, args.workspace, args.deployment, args.revision, args.protect)
        elif args.mode == 'status' or not args.execute:
            result = diagnostic.status(args.root, args.expected_sha256, args.workspace)
        else:
            result = diagnostic.run(args.root, args.expected_sha256, args.workspace, diagnostic.LiveBackend(args.workspace))
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
        result = dict(ok=False, error=type(exc).__name__ + ': ' + str(exc), dispatch_authorized=False,
                      ready_for_large_test=False, n_ge_50='FROZEN')
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return 0 if result['ok'] and result.get('state') not in ('STOPPED', 'UNKNOWN_TAIL') else 2


if __name__ == '__main__': raise SystemExit(main())
