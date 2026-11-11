#!/usr/bin/env python3
"""Paired analysis of the recovery experiment, and whether the 2/5 baseline reproduces.

WHY
    The headline claim is 2/5 -> 4/5. Two problems with comparing those two numbers:
      1. they come from DIFFERENT experiments, so the comparison is unpaired;
      2. the recovery run's own trials already contain a single-shot observation each.

    Every recovery trial records how many attempts it took. A trial with attempts == 1 IS a
    single-shot trial: the first attempt was the final attempt. A trial with attempts > 1 failed
    its first attempt by construction, because recovery only fires on failure. So one recovery run
    yields BOTH arms, PAIRED, on the same instance in the same session - which is a stronger design
    than two independent arms and costs half the runs.
"""

# recovery.tsv, verbatim from evobot_push_recover_20261112/evidence_v2/
# trial, attempts, achieved_mm, terminal_passed
RECOVERY = [
    (1, 2, 73.95, False),
    (2, 1, 90.60, True),
    (3, 1, 145.58, True),
    (4, 1, 97.45, True),
    (5, 2, 122.67, True),
]

# repeats.tsv, verbatim from evobot_t08_saturation_diagnosis_20261112/evidence/
# trial, displacement_mm, direction_cos
REPEATS = [
    (1, 32.63, 0.9849),
    (2, 137.84, 0.9998),
    (3, 57.71, 0.9999),
    (4, 5.05, 0.8290),
    (5, 2.63, -0.6633),
]

PUSH_MIN_MM, PUSH_MAX_MM = 30.0, 150.0
COS_MIN = 0.90


def main():
    print('=== 1. PAIRED view inside the recovery run ===')
    first = []
    for trial, attempts, mm, passed in RECOVERY:
        # attempts == 1 means the first attempt was the only attempt, so it succeeded
        first_ok = (attempts == 1) and passed
        first.append(first_ok)
        print('  trial %d: attempts=%d  first_attempt=%-5s  final=%-5s'
              % (trial, attempts, first_ok, passed))
    a = sum(first)
    b = sum(1 for _t, _n, _m, p in RECOVERY if p)
    print()
    print('  FIRST-ATTEMPT passes : %d/5' % a)
    print('  FINAL passes         : %d/5' % b)
    improved = sum(1 for f, (_t, _n, _m, p) in zip(first, RECOVERY) if not f and p)
    regressed = sum(1 for f, (_t, _n, _m, p) in zip(first, RECOVERY) if f and not p)
    print('  discordant pairs     : %d improved, %d regressed' % (improved, regressed))
    print()
    print('  McNemar exact, on %d discordant pair(s): p = 1.0' % (improved + regressed))
    print('  => within its own experiment, recovery changed ONE trial.')
    print()

    print('=== 2. does the claimed 2/5 single-shot baseline reproduce? ===')
    passes = 0
    for trial, mm, cos in REPEATS:
        d_ok = PUSH_MIN_MM <= mm <= PUSH_MAX_MM
        c_ok = cos >= COS_MIN
        ok = d_ok and c_ok
        passes += ok
        print('  trial %d: disp=%6.2f mm %-6s cos=%+.4f %-5s -> %s'
              % (trial, mm, 'OK' if d_ok else 'FAIL', cos,
                 'OK' if c_ok else 'FAIL', 'PASS' if ok else 'FAIL'))
    print()
    print('  passes on the two recorded clauses: %d/5' % passes)
    print('  the audit states                      : 2/5')
    if passes != 2:
        print()
        print('  DISCREPANCY: the archived columns do not support 2/5. The remaining frozen')
        print('  clauses (|dz| <= 0.020 and final pose inside the zone radius) are not in this')
        print('  file, so whether 3/5 or 2/5 is correct cannot be decided from repeats.tsv alone.')
        print('  It needs the per-trial verdicts, which this archive does not contain.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
