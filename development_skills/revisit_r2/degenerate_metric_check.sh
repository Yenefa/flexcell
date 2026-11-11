#!/usr/bin/env bash
# N3 -- is a reported metric an independent signal, or does it degenerate into one
#        of the values it is supposed to be compared against?
#
# The round-2 instance: verdict.false_failure was quoted as evidence of a defect, but
# evaluate.py:344 defines false_failure = bool(passed and not claimed), so in any run
# with no agent claim it is EXACTLY equal to passed. The exec-mystery lane measured
# 9/9 runs showing it; this script proves the RULE that makes those 9/9 inevitable.
#
# No Gazebo, no bundle, no sample size: this is an arithmetic identity.
set -u
python3 - <<'PY'
print("Definition (benchmark/evaluators/evaluate.py):")
print("   254: claimed       = bool(final_state.get('agent_claimed_success'))")
print("   343: false_success = bool(claimed and not passed)")
print("   344: false_failure = bool(passed and not claimed)")
print()
print("Exhaustive truth table over (passed, claimed):")
print("  passed  claimed | false_success  false_failure")
rows = []
for passed in (False, True):
    for claimed in (False, True):
        fs = bool(claimed and not passed)
        ff = bool(passed and not claimed)
        rows.append((passed, claimed, fs, ff))
        print("  %-7s %-7s | %-14s %s" % (passed, claimed, fs, ff))

print()
print("Question: in runs with NO claim, is false_failure distinguishable from passed?")
sub = [(p, c, fs, ff) for (p, c, fs, ff) in rows if c is False]
ident = all(ff == p for (p, c, fs, ff) in sub)
for p, c, fs, ff in sub:
    print("   passed=%-5s claimed=False -> false_failure=%-5s  equals passed: %s"
          % (p, ff, ff == p))
print()
print("  identity holds for every claimed=False row: %s" % ident)
print()
print("  => with no claim, false_failure == passed EXACTLY. Zero information.")
print("     It is informative only across runs where a claim exists.")
print()
print("REVIEW QUESTION (general form):")
print("  For a metric M defined over (A, B), check whether M collapses to A (or B)")
print("  on the subpopulation actually being reported. If it does, quoting M there")
print("  is quoting A under a second name. Enumerate the truth table; it is free.")
PY
