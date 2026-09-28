"""Shared benchmark metric primitives (issue #8 / §4.3).

Pure functions only - every benchmark number in the repo must regenerate
from these plus the episode store, never from hand-written PASS lines.
"""

import math


def wilson(successes, n, z=1.96):
    """Wilson 95% CI for a binomial proportion (metric #1)."""
    if n == 0:
        return (0.0, 1.0)
    p = successes / float(n)
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def percentile(values, q):
    """Linear-interpolated percentile of a non-empty list (0..100)."""
    if not values:
        raise ValueError('percentile of empty list')
    s = sorted(float(v) for v in values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (q / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] + (s[c] - s[f]) * (k - f)


def latency_summary(values_ms):
    """Metric #3: p50/p95/p99 + max over decide() latencies (ms)."""
    if not values_ms:
        return None
    return {
        'n': len(values_ms),
        'p50_ms': round(percentile(values_ms, 50), 3),
        'p95_ms': round(percentile(values_ms, 95), 3),
        'p99_ms': round(percentile(values_ms, 99), 3),
        'max_ms': round(max(values_ms), 3),
    }


def invalid_per_1000(evaluated, rejected):
    """Metric #6: safety-gate rejections per 1000 decisions."""
    if evaluated <= 0:
        return 0.0
    return round(1000.0 * rejected / evaluated, 3)


def aggregate_safety(rows):
    """Sum per-episode safety blocks {evaluated, rejected} into per-1000."""
    ev = sum(int(r.get('evaluated', 0)) for r in rows)
    rej = sum(int(r.get('rejected', 0)) for r in rows)
    return {'evaluated': ev, 'rejected': rej,
            'invalid_per_1000': invalid_per_1000(ev, rej)}
