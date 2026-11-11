#!/usr/bin/env python3
"""Show what experience retrieval returns for the frozen unseen templates, and who consumes it."""
import sys

WT = '/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp'
for p in ('evolution/experience', 'evolution/diagnosis', 'evolution/validation', 'experiments/baselines'):
    sys.path.insert(0, WT + '/' + p)
import baseline_c as C  # noqa: E402

STORE = WT + '/evolution/experience/records.jsonl'

CASES = {
    'T12_triple_revisit': ('Put the red block in the left bin, then move it to the right bin, then put it '
                          'back in the left bin. It must actually visit the right bin. Leave the other '
                          'block exactly where it is.'),
    'T13_geometric':      ('Compare distances before moving: if the red block is closer to the left bin than '
                          'to the right bin, put BOTH blocks in the right bin; otherwise put BOTH blocks in '
                          'the left bin. Do not guess from the colours.'),
    'T14_ordered_pair':   ('Put both blocks in the right bin. The red block must be put there FIRST, then the '
                          'blue block. Doing it in the other order is not acceptable even if both end up in '
                          'the right bin.'),
    'T05_relay':          'Pass the red block through the right bin first, then the blue block to the left bin.',
}


def main():
    print('%-22s %-9s %s' % ('frozen template', 'retrieved', 'records'))
    print('-' * 96)
    for name in sorted(CASES):
        obs = {'instruction': CASES[name], 'objects': [], 'zones': [], 'skills': []}
        got = C.retrieve(obs, STORE)
        prov = sum(1 for r in got if r.get('provenance_verified') is True)
        print('%-22s %-9d %s' % (name, len(got), ', '.join(r['task_id'] for r in got) or '-'))
        print('%-22s %-9s verified=%d of %d' % ('', '', prov, len(got)))
    print()
    print('WHO CONSUMES THE FIELD')
    print('  A (rule planner)   : no  - deterministic, ignores observation["experience"]')
    print('  B (model planner)  : yes - if its prompt includes the field')
    print('  C                  : yes - this is what Baseline C adds')
    print('  D                  : undefined (North Star 8-14 BLOCKED_MISSION_TEXT_MISSING)')
    print()
    print('  Retrieval reaching a plan is a PRECONDITION, not the P4 result. No plan-consumption')
    print('  measurement and no D arm exist, so EVOLUTION_ADVANTAGE_NOT_DEMONSTRATED stands.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
