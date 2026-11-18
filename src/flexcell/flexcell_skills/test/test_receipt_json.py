#!/usr/bin/env python3
"""Typed receipt equality: persisted booleans/ints/floats must not collapse."""
import json
import unittest

from flexcell_skills.contracts.receipt_json import loads, same_typed


class SameTypedTest(unittest.TestCase):

    def test_bool_is_not_int(self):
        self.assertFalse(same_typed({'x': False}, {'x': 0}))
        self.assertFalse(same_typed({'x': True}, {'x': 1}))
        self.assertFalse(same_typed({'x': 0}, {'x': False}))

    def test_int_is_not_float(self):
        self.assertFalse(same_typed({'x': 1}, {'x': 1.0}))
        self.assertFalse(same_typed({'x': 0.0}, {'x': 0}))

    def test_key_order_does_not_matter(self):
        self.assertTrue(same_typed({'a': 1, 'b': 2}, {'b': 2, 'a': 1}))

    def test_nested_type_changes_are_detected(self):
        self.assertFalse(same_typed({'x': [1, 2]}, {'x': [1, 2.0]}))
        self.assertFalse(same_typed({'x': {'y': 1}}, {'x': {'y': True}}))
        self.assertFalse(same_typed({'x': [False]}, {'x': [0]}))

    def test_nonfinite_values_are_refused(self):
        for value in (float('nan'), float('inf'), float('-inf')):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    same_typed({'x': value}, {'x': value})

    def test_duplicate_keys_and_nonfinite_constants_are_refused(self):
        for text in ('{"x":1,"x":2}', '{"x":NaN}',
                     '{"x":Infinity}', '{"x":-Infinity}', '{"x":1e999}'):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    loads(text)

    def test_round_trip_preserves_python_types(self):
        value = {'ok': True, 'n': 1, 'f': 1.5, 's': 'text',
                 'items': [None, False, 0, 1.0, {'nested': True}]}
        self.assertTrue(same_typed(value, loads(json.dumps(value))))


if __name__ == '__main__':
    unittest.main()
