#!/usr/bin/env python3
"""Offline policy-input replay runner (issue #7 AC).

Re-runs a policy on the recorded policy inputs of one or more episode files
and compares its decisions against the recorded ones - no robot needed.

Usage (ROS env sourced, or any env that can import flexcell_skills):
  python3 setup/93_replay.py <episode.json | episodes-dir> [--policy MOD:CLS]

Exit 0 = REPLAY: PASS (every recorded decision reproduced), 1 = FAIL,
2 = no episodes found.
"""
import argparse
import glob
import importlib
import json
import os
import sys

from flexcell_skills.contracts.episode import replay_episode


def load_policy(spec):
    mod, _, attr = spec.partition(':')
    cls = getattr(importlib.import_module(mod), attr)
    return cls()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('path', help='episode .json file or a directory of them')
    ap.add_argument('--policy',
                    default='flexcell_skills.decision_policy:FSMPolicy')
    args = ap.parse_args()

    if os.path.isdir(args.path):
        files = sorted(glob.glob(os.path.join(args.path, '*.json')))
    else:
        files = [args.path]
    if not files:
        print('REPLAY: no episode files found in %s' % args.path)
        return 2

    policy = load_policy(args.policy)
    print('replaying %d episode(s) with %s' % (len(files), args.policy))
    bad = 0
    for f in files:
        try:
            with open(f) as fh:
                record = json.load(fh)
        except (OSError, ValueError) as exc:
            print('REPLAY FAIL %s: unreadable (%s)' % (os.path.basename(f), exc))
            bad += 1
            continue
        results = replay_episode(record, policy)
        fails = [r for r in results if not r['ok']]
        print('%s %s: %d steps, %d diverged %s' % (
            'REPLAY PASS' if not fails else 'REPLAY FAIL',
            os.path.basename(f), len(results), len(fails),
            '' if not fails else fails[:2]))
        bad += len(fails)

    print('REPLAY: %s' % ('PASS' if bad == 0 else 'FAIL (%d diverged steps)'
                          % bad))
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
