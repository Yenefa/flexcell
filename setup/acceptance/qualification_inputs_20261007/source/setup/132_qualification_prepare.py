#!/usr/bin/env python3
"""Prepare/verify frozen candidate inputs without ROS, inference or sampling."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'transferbench'))
from qualification_prepare import prepare, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    make = modes.add_parser('prepare')
    for flag in ('out', 'history', 'deployment', 'calibration', 'familiar-inputs', 'budget', 'workspace'):
        make.add_argument('--' + flag, type=Path, required=True)
    make.add_argument('--revision', required=True)
    make.add_argument('--seed', type=int, required=True)
    check = modes.add_parser('verify')
    check.add_argument('--root', type=Path, required=True)
    check.add_argument('--expected-sha256', required=True)
    check.add_argument('--workspace', type=Path)
    check.add_argument('--history', type=Path)
    args = parser.parse_args()
    try:
        if args.mode == 'prepare':
            result = prepare(args.out, seed=args.seed, history_root=args.history,
                             deployment_path=args.deployment, calibration_path=args.calibration,
                             reference_path=args.familiar_inputs, budget_path=args.budget,
                             revision=args.revision, workspace=args.workspace)
        else:
            result = verify(args.root, args.expected_sha256, workspace=args.workspace, history_root=args.history)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        result = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc),
                  'sampling_authorized': False, 'ready_for_large_test': False,
                  'model_calls': 0, 'native_episodes_executed': 0}
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
