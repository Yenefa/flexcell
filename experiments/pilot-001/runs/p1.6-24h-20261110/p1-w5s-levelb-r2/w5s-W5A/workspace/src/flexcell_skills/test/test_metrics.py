#!/usr/bin/env python3
"""Unit tests for the benchmark metric primitives (issue #8)."""

import unittest

from flexcell_skills.contracts.metrics import (
    aggregate_safety, invalid_per_1000, latency_summary, percentile, wilson)


class TestMetrics(unittest.TestCase):

    def test_wilson_known_values(self):
        self.assertEqual(wilson(0, 0), (0.0, 1.0))
        lo, hi = wilson(7, 1000)
        self.assertAlmostEqual(lo, 0.0034, delta=0.001)
        self.assertAlmostEqual(hi, 0.0144, delta=0.001)
        lo, hi = wilson(0, 10)
        self.assertEqual(lo, 0.0)
        self.assertLess(hi, 0.35)

    def test_wilson_is_monotone_in_successes(self):
        prev = -1.0
        for s in range(0, 21):
            lo, _ = wilson(s, 20)
            self.assertGreaterEqual(lo, prev - 1e-9)
            prev = lo

    def test_percentile(self):
        self.assertEqual(percentile([5], 50), 5)
        self.assertEqual(percentile([1, 2, 3, 4], 50), 2.5)
        self.assertEqual(percentile(list(range(1, 101)), 95), 95.05)
        with self.assertRaises(ValueError):
            percentile([], 50)

    def test_latency_summary(self):
        self.assertIsNone(latency_summary([]))
        s = latency_summary([1, 2, 3, 4, 100])
        self.assertEqual(s['n'], 5)
        self.assertEqual(s['p50_ms'], 3)
        self.assertEqual(s['max_ms'], 100)
        self.assertLessEqual(s['p50_ms'], s['p95_ms'])
        self.assertLessEqual(s['p95_ms'], s['p99_ms'])

    def test_invalid_per_1000(self):
        self.assertEqual(invalid_per_1000(1000, 7), 7.0)
        self.assertEqual(invalid_per_1000(0, 0), 0.0)
        self.assertEqual(invalid_per_1000(3, 1), 333.333)

    def test_aggregate_safety(self):
        rows = [{'evaluated': 12, 'rejected': 0},
                {'evaluated': 1, 'rejected': 1},
                None]
        agg = aggregate_safety([r for r in rows if r])
        self.assertEqual(agg['evaluated'], 13)
        self.assertEqual(agg['rejected'], 1)
        self.assertAlmostEqual(agg['invalid_per_1000'], 76.923, places=2)


if __name__ == '__main__':
    unittest.main()
