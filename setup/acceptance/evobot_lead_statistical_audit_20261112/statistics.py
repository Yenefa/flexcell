#!/usr/bin/env python3
"""Exact statistics behind README.md. No simulator, no model calls."""
import math
from math import comb


def fisher_exact_two_sided(a, b, c, d):
    """a=success arm1, b=fail arm1, c=success arm2, d=fail arm2."""
    n1, n2 = a + b, c + d
    n = n1 + n2

    def prob(a_, b_, c_, d_):
        return comb(n1, a_) * comb(n2, c_) / comb(n, a_ + c_)

    p_obs = prob(a, b, c, d)
    total = 0.0
    for a_ in range(0, min(n1, a + c) + 1):
        c_ = (a + c) - a_
        b_ = n1 - a_
        d_ = n2 - c_
        if b_ < 0 or d_ < 0:
            continue
        pv = prob(a_, b_, c_, d_)
        if pv <= p_obs + 1e-12:
            total += pv
    return p_obs, min(total, 1.0)


def wilson(k, n, z=1.96):
    ph = k / n
    den = 1 + z * z / n
    centre = (ph + z * z / (2 * n)) / den
    half = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    return max(0.0, centre - half), min(1.0, centre + half)


def main():
    print("=== Fisher exact, terminal clause, two-sided ===")
    arms = [
        ("recovery 4/5 vs single-shot 2/5", (4, 1, 2, 3)),
        ("recovery 4/5 vs single-shot 3/5 (RTF=0)", (4, 1, 3, 2)),
        ("recovery 4/5 vs single-shot 0/5 (contact 0.030)", (4, 1, 0, 5)),
    ]
    for label, (a, b, c, d) in arms:
        _, p = fisher_exact_two_sided(a, b, c, d)
        print("  %-46s p = %.4f" % (label, p))

    print()
    print("=== Wilson 95% CI ===")
    for k, n, lab in [(4, 5, "recovery"), (2, 5, "single-shot"), (3, 5, "single-shot RTF=0")]:
        lo, hi = wilson(k, n)
        print("  %-20s %d/%d = %.0f%%  Wilson95 [%.3f, %.3f]" % (lab, k, n, 100 * k / n, lo, hi))

    print()
    print("=== n per arm to detect 80%% vs 40%% (alpha .05, power .80) ===")
    p1, p2 = 0.80, 0.40
    h = 2 * math.asin(math.sqrt(p1)) - 2 * math.asin(math.sqrt(p2))
    n = (1.96 + 0.84) ** 2 / (h ** 2 / 2)
    print("  n per arm ~= %.1f" % n)

    print()
    print("=== displacement distributions (mm) ===")
    base = [32.63, 137.84, 57.71, 5.05, 2.63]
    rec = [73.95, 90.60, 145.58, 97.45, 122.67]
    for lab, xs in [("single-shot", base), ("recovery", rec)]:
        s = sorted(xs)
        print("  %-12s min %6.1f  median %6.1f  max %6.1f  spread %6.1f"
              % (lab, s[0], s[2], s[-1], s[-1] - s[0]))
    ceiling = 150.0
    print("  ceiling margin of the recovery arm's max: %.1f mm" % (ceiling - sorted(rec)[-1]))


if __name__ == "__main__":
    main()
