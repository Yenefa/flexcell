#!/usr/bin/env python3
"""Stage unpublished qualification candidates offline; publish commitments only."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'transferbench'))
from qualification_private import prepare, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    make = modes.add_parser('prepare')
    for flag in ('out', 'commitment', 'deployment', 'familiar-inputs'):
        make.add_argument('--' + flag, type=Path, required=True)
    make.add_argument('--published', nargs=2, metavar=('ROOT', 'SHA256'), action='append', required=True)
    make.add_argument('--revision', required=True)
    check = modes.add_parser('verify')
    check.add_argument('--commitment', type=Path, required=True)
    check.add_argument('--expected-sha256', required=True)
    for sub in (make, check):
        for flag in ('workspace', 'history', 'calibration', 'budget'):
            sub.add_argument('--' + flag, type=Path, required=True)
    args = parser.parse_args()
    common = dict(workspace=args.workspace, history_root=args.history,
                  calibration_path=args.calibration, budget_path=args.budget)
    try:
        if args.mode == 'prepare':
            refs = [{'root': str(Path(root).absolute()), 'package_sha256': sha}
                    for root, sha in args.published]
            result = prepare(args.out, args.commitment, refs, deployment_path=args.deployment,
                             reference_path=args.familiar_inputs, revision=args.revision, **common)
        else:
            result = verify(args.commitment, args.expected_sha256, **common)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        # Never dump private inputs or exception arguments containing their data.
        message = str(exc) if isinstance(exc, (ValueError, OSError)) else 'invalid input structure'
        result = {'ok': False, 'error': type(exc).__name__ + ': ' + message,
                  'sampling_authorized': False, 'ready_for_large_test': False,
                  'model_calls': 0, 'native_episodes_executed': 0}
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
