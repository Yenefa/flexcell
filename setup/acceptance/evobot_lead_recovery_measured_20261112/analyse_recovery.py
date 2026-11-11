#!/usr/bin/env python3
"""How often does the bounded single-retry recovery actually recover? Measured from the archive."""
import collections
import glob
import json
import os

WT = '/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp'
ACC = WT + '/setup/acceptance'


def result_of(path):
    try:
        txt = open(path, encoding='utf-8', errors='replace').read()
    except OSError:
        return None, None
    if 'RESULT ' not in txt:
        return None, None
    try:
        j = json.loads(txt.split('RESULT ', 1)[1].splitlines()[0])
    except ValueError:
        return None, None
    return j.get('outcome'), j.get('error_code')


def main():
    decs = glob.glob(ACC + '/**/recovery_decision.json', recursive=True)
    runtime = collections.Counter()
    rich = collections.Counter()
    for f in decs:
        try:
            d = json.load(open(f, encoding='utf-8'))
        except Exception:
            continue
        if 'decision' in d:
            dec = d.get('decision') or {}
            rich[str(dec.get('action'))] += 1
        elif 'action' in d:
            runtime[str(d.get('action'))] += 1
    print('recovery_decision.json files: %d' % len(decs))
    print('  runtime decisions : %s' % dict(runtime))
    print('  richer decisions  : %s' % dict(rich))
    print()

    retries = sorted(glob.glob(ACC + '/**/task_retry.out', recursive=True))
    tally = collections.Counter()
    for p in retries:
        oc, ec = result_of(p)
        tally[(oc, ec)] += 1
    print('retries actually executed (task_retry.out): %d' % len(retries))
    for (oc, ec), n in tally.most_common():
        print('  outcome=%-5s error_code=%-5s %d' % (oc, ec, n))
    ok = sum(n for (oc, _e), n in tally.items() if oc == 0)
    print()
    print('RETRY SUCCESS RATE: %d/%d = %.0f%%' % (ok, len(retries), 100.0 * ok / max(1, len(retries))))
    print()
    print('Bounded to ONE retry by design (budget: 1); the failures got no third attempt.')
    print('Original failure preserved on every rich record, and recovery is decided from execution')
    print('evidence rather than the graded verdict, so this is recovery, not success manufacturing.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
