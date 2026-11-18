#!/usr/bin/env python3
"""Strict-JSON serialization for non-finite measurements (issue #287)."""
import json
import unittest

from flexcell_skills.common import json_safe


class TestJsonSafe(unittest.TestCase):

    def test_non_finite_floats_become_null(self):
        payload = {
            'nan': float('nan'),
            'inf': float('inf'),
            'neg_inf': float('-inf'),
            'nested': [1.5, float('nan')],
            'keep': 2.0,
        }
        safe = json_safe(payload)
        self.assertIsNone(safe['nan'])
        self.assertIsNone(safe['inf'])
        self.assertIsNone(safe['neg_inf'])
        self.assertEqual(safe['nested'], [1.5, None])
        self.assertEqual(safe['keep'], 2.0)
        json.dumps(safe, allow_nan=False)

    def test_dict_keys_remain_strings(self):
        self.assertEqual(json_safe({1: float('nan')}), {'1': None})


if __name__ == '__main__':
    unittest.main()
