#!/usr/bin/env python3
"""Required sample size to detect the recovery effect, using the MEASURED per-draw pass rate.

WHY THIS EXISTS
    A round-18 audit computed n ~= 22 per arm to detect 80% vs 40%, from the observed 4/5 vs 2/5.
    But 4/5 and 2/5 are themselves n=5 estimates - the effect size used to size the study was
    computed from the same tiny sample the study is meant to replace. Round 17 measured the actual
    per-draw behaviour over 197 contact-height moves, which gives an INDEPENDENT estimate of what
    a single attempt should achieve. This script sizes the experiment from that instead.
"""
import math

# From round 17: of 197 successful contact-height moves, the share landing in the only passing
# displacement band (69.92 mm, inside [30, 150] mm) was 14.7%. The other bands (151.14, 6.32,
# 3.55, 0.59 mm) all fail the frozen clause.
P_SINGLE = 29 / 197.0          # 0.1472
ATTEMPTS = 3                   # push_recover budget
ALPHA = 0.05
POWER = 0.80


def p_recovery(p, k):
    return 1.0 - (1.0 - p) ** k


def n_per_arm(p1, p2, alpha=ALPHA, power=POWER):
    z_a = 1.959963985
    z_b = 0.8416212336
    num = (z_a + z_b) ** 2 * (p1 * (1 - p1) + p2 * (1 - p2))
    return num / (p1 - p2) ** 2


def main():
    p_rec = p_recovery(P_SINGLE, ATTEMPTS)
    print('Per-draw pass rate, measured (round 17, n=197) : %.3f' % P_SINGLE)
    print('Predicted rate with <=%d attempts               : %.3f   [1-(1-p)^k]' % (ATTEMPTS, p_rec))
    print()
    print('Effect size the n=22 audit assumed : 80%% vs 40%%  (from 4/5 vs 2/5)')
    print('Effect size the measurement implies : %.1f%% vs %.1f%%' % (100 * p_rec, 100 * P_SINGLE))
    print()
    n_audit = n_per_arm(0.80, 0.40)
    n_meas = n_per_arm(p_rec, P_SINGLE)
    print('n per arm to detect 80%% vs 40%%     : %.1f  -> the audit rounded to 22' % n_audit)
    print('n per arm to detect the REAL effect : %.1f  -> round UP' % n_meas)
    print()
    need = math.ceil(n_meas)
    print('REQUIRED: %d trials per arm = %d Gazebo runs total.' % (need, 2 * need))
    print()
    print('=== what n=22 per arm would actually deliver ===')
    z_a, z_b = 1.959963985, 0.8416212336
    var = (p_rec * (1 - p_rec) + P_SINGLE * (1 - P_SINGLE)) / 22.0
    se = math.sqrt(var)
    power22 = 1.0 - _norm_cdf(z_a - (p_rec - P_SINGLE) / se)
    print('  power at n=22 : %.2f  (target %.2f)' % (power22, POWER))
    print('  => a 22-per-arm run is UNDER-POWERED and would likely report a null that means nothing.')
    return 0


def _norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


if __name__ == '__main__':
    raise SystemExit(main())
