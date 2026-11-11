#!/usr/bin/env python3
"""Are the failures a property of the INSTANCE, or of the RUN?

WHY THIS CHANGES WHAT A FIX SHOULD TARGET: I have been reporting failure counts as if they
described instances. If the same instance passes in one replicate and fails in another, then the
count describes runs, and a fix aimed at "the hard instances" would be aimed at nothing. It also
bounds how much a single batch can tell us: with one run per instance, a 3/16 failure count is
mostly run noise.

DATA: two seed sets were each run twice.
  7500/7600 : pair48 (arm B only - its recovery arm was invalid, but the first-attempt verdicts
              were valid measurements) and batch1
  8100/8200 : batch2 and batch3
Only attempt-1 verdicts are used, so the comparison is of the same thing in both replicates.
"""
import glob
import json
import os
import sys

SETS = {
    "seeds7500": ["/tmp/evobot-pair48", "/tmp/evobot-batch1"],
    "seeds8100": ["/tmp/evobot-batch2", "/tmp/evobot-batch3"],
}


def read(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def main():
    total_stable_pass = total_stable_fail = total_mixed = 0
    rows = []
    for setname, bases in SETS.items():
        ids = set()
        for b in bases:
            for p in glob.glob(os.path.join(b, "HO-*")):
                ids.add(os.path.basename(p))
        for oid in sorted(ids):
            seq = []
            for b in bases:
                v = read(os.path.join(b, oid, "verdict_after1.json"))
                if v is None:
                    seq.append(None)
                else:
                    seq.append(bool(v.get("passed")))
            known = [x for x in seq if x is not None]
            if len(known) < 2:
                continue
            if all(known):
                cls = "STABLE PASS"
                total_stable_pass += 1
            elif not any(known):
                cls = "STABLE FAIL"
                total_stable_fail += 1
            else:
                cls = "MIXED (run-dependent)"
                total_mixed += 1
            rows.append((setname, oid, seq, cls))

    print("%-12s %-20s %-20s %s" % ("set", "instance", "replicate outcomes", "class"))
    for setname, oid, seq, cls in rows:
        pretty = " ".join("-" if x is None else ("pass" if x else "FAIL") for x in seq)
        print("%-12s %-20s %-20s %s" % (setname, oid, pretty, cls))

    n = len(rows)
    print()
    print("instances with 2+ replicates :", n)
    print("  STABLE PASS                :", total_stable_pass)
    print("  STABLE FAIL                :", total_stable_fail)
    print("  MIXED (outcome flipped)    :", total_mixed)
    print()
    if n:
        print("flip rate over instances     : %.1f%%" % (100.0 * total_mixed / n))
    print()
    print("AND THE UNCOMFORTABLE CASE: if %d of %d instances flip, then a single-batch"
          % (total_mixed, n))
    print("failure count is mostly a statement about RUNS. A fix aimed at 'the failing")
    print("instances' would be aimed at coin flips, and a batch that happens to draw fewer")
    print("failures would look like progress.")
    print()
    print("WHAT SURVIVES: stable failures are the ones worth attributing. Those are the")
    print("instances where a fix could be shown to work.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
