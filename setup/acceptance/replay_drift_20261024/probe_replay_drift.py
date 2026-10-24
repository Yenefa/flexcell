#!/usr/bin/env python3
"""Separate decision-semantic replay drift from free-text replay drift.

`replay_episode` compares the whole recorded decision dict against the replayed
one, so `explanation` -- a free-text field the policy is free to reword -- takes
part in the equality test.  `5462124` (2026-10-23) changed the PLACE-abort text
to embed the typed skill code (`place failed (ERR_MOTION_FAILED, ...)`).  Measured
2026-10-24: the archived S4 episode now reports REPLAY-DIRTY with `action`,
`target`, `reason_code` and `confidence` all identical, and nothing else
different.

That is a real fidelity question, not a cosmetic one: an evidence archive whose
whole claim is "the decision can be recomputed" must not go dirty because a
message was reworded.  This probe states the invariant that actually matters --
**no semantic field may diverge** -- and reports textual drift separately instead
of failing on it.

Scope: only records whose `policy.name == 'fsm'` are replayable offline.  A
hybrid record's history is a sequence of model decisions; the frozen FSM cannot
continue it, and re-raising `PolicyStateError` is reported, never swallowed.

Exit 0 = semantic replay is exact everywhere it was measured.
Exit 1 = a semantic field diverged: the archive no longer reproduces and the
         claim attached to it must be withdrawn.
"""
import glob
import json
import os
import sys

SEMANTIC = ('action', 'target', 'reason_code', 'confidence')

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

TARGETS = [
    ('E-021 native recovery (FSM batch only)',
     'setup/acceptance/e021_native_recovery_20261024/episodes'),
    ('M3 online v2 S3/S4',
     'setup/acceptance/m3_online_v2_20260930/fsm_s3_s4/episodes'),
]


def measure(policy, episodes_dir, replay_episode, decision_to_dict,
            goal_from, constraints_from, history_from):
    stats = {'episodes': 0, 'fsm': 0, 'skipped': 0, 'raised': 0,
             'steps': 0, 'dirty_steps': 0, 'textual': 0, 'semantic': 0,
             'fields': {}, 'examples': []}
    for path in sorted(glob.glob(os.path.join(episodes_dir, '*.json'))):
        with open(path, encoding='utf-8') as stream:
            episode = json.load(stream)
        stats['episodes'] += 1
        if (episode.get('policy') or {}).get('name') != 'fsm':
            stats['skipped'] += 1
            continue
        stats['fsm'] += 1
        steps = episode.get('steps') or []
        stats['steps'] += len(steps)
        try:
            replayed = replay_episode(episode, policy)
        except Exception as exc:  # noqa: BLE001 - counted and shown
            stats['raised'] += 1
            if stats['raised'] <= 2:
                print('    raised  %s: %s: %s'
                      % (os.path.basename(path), type(exc).__name__, exc))
            continue
        for row in replayed:
            if row['ok']:
                continue
            stats['dirty_steps'] += 1
            step = steps[row['seq'] - 1]
            want = step.get('policy_output') or {}
            src = step['policy_input']
            world = (json.loads(src['world_state_canonical'])
                     if src.get('world_state_canonical') else None)
            got = decision_to_dict(policy.decide(
                world, goal_from(src['goal']),
                constraints_from(src['constraints']),
                history_from(src['history'])))
            if all(want.get(k) == got.get(k) for k in SEMANTIC):
                stats['textual'] += 1
                differing = [k for k in set(want) | set(got) if want.get(k) != got.get(k)]
                for key in differing:
                    stats['fields'][key] = stats['fields'].get(key, 0) + 1
                if len(stats['examples']) < 2:
                    stats['examples'].append(
                        (os.path.basename(path), row['seq'],
                         {k: (want.get(k), got.get(k)) for k in differing}))
            else:
                stats['semantic'] += 1
    return stats


def main():
    pkg = os.path.join(REPO, 'src/flexcell/flexcell_skills')
    if not os.path.isdir(pkg):
        print('MISSING: %s' % pkg)
        return 2
    sys.path.insert(0, pkg)
    from flexcell_skills.contracts.episode import (  # noqa: E402
        _constraints_from_dict, _goal_from_dict, _history_from_dicts,
        decision_to_dict, replay_episode)
    from flexcell_skills.decision_policy import FSMPolicy  # noqa: E402

    policy = FSMPolicy()
    semantic_fail = 0
    for label, rel in TARGETS:
        episodes_dir = os.path.join(REPO, rel)
        if not os.path.isdir(episodes_dir):
            print('%s\n  MISSING: %s' % (label, rel))
            semantic_fail += 1
            continue
        print(label)
        print('  %s' % rel)
        stats = measure(policy, episodes_dir, replay_episode, decision_to_dict,
                        _goal_from_dict, _constraints_from_dict, _history_from_dicts)
        print('  episodes %d  (fsm-replayable %d, skipped non-fsm %d, raised %d)'
              % (stats['episodes'], stats['fsm'], stats['skipped'], stats['raised']))
        print('  decision steps %d  ->  diverging %d'
              % (stats['steps'], stats['dirty_steps']))
        print('    textual drift (semantic fields identical) : %d' % stats['textual'])
        print('    SEMANTIC drift                            : %d' % stats['semantic'])
        if stats['fields']:
            print('    fields involved                           : %s' % stats['fields'])
        for name, seq, diffs in stats['examples']:
            print('    e.g. %s seq %d' % (name, seq))
            for key, (want, got) in diffs.items():
                print('           %s' % key)
                print('             recorded: %r' % (want,))
                print('             replayed: %r' % (got,))
        semantic_fail += stats['semantic']
        print()

    print('REPLAY DRIFT PROBE: %s' % (
        'SEMANTIC DRIFT PRESENT' if semantic_fail
        else 'semantic replay exact; textual drift reported above'))
    return 1 if semantic_fail else 0


if __name__ == '__main__':
    sys.exit(main())
