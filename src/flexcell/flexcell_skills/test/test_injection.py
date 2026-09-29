"""Offline guards for the injection lifecycle contract (T6 hardening).

Pins the four states the chief asked for - requested / armed / applied /
cleared - and, with them, the two measured benchmark failures:

- a request that is never delivered must not be able to pass unnoticed
  (`on_request` records a refusal instead of ignoring a bad payload);
- a clear must actually disarm (`on_pick_attempt` returns None afterwards),
  which is what the runner's broken `if payload:` guard prevented.

Pure python: no rclpy, no simulator.
"""

import unittest

from flexcell_skills.contracts.injection import (
    APPLIED, ARMED, CLEARED, IDLE, REQUESTED, InjectionLifecycle,
    parse_request)


class TestParseRequest(unittest.TestCase):
    def test_scenario_only_defaults_to_once(self):
        self.assertEqual(parse_request('recovery_demo_v1'),
                         ('recovery_demo_v1', 'once', ''))

    def test_explicit_mode(self):
        self.assertEqual(parse_request('exhaust_demo_v1:always'),
                         ('exhaust_demo_v1', 'always', ''))

    def test_request_id_suffix(self):
        self.assertEqual(parse_request('s5:always#r42'),
                         ('s5', 'always', 'r42'))

    def test_empty_payload_is_the_clear_signal(self):
        self.assertEqual(parse_request(''), ('', '', ''))
        self.assertEqual(parse_request('   '), ('', '', ''))

    def test_clear_can_carry_a_request_id(self):
        self.assertEqual(parse_request('#r7'), ('', '', 'r7'))
        self.assertEqual(parse_request(' #r7 '), ('', '', 'r7'))

    def test_bad_mode_raises(self):
        with self.assertRaises(ValueError):
            parse_request('x:sometimes')

    def test_empty_scenario_raises(self):
        with self.assertRaises(ValueError):
            parse_request(':once')


class TestLifecycle(unittest.TestCase):
    def setUp(self):
        self.lc = InjectionLifecycle()

    def test_starts_idle_and_inert(self):
        self.assertEqual(self.lc.state, IDLE)
        self.assertIsNone(self.lc.on_pick_attempt('target_box_a'))

    def test_request_then_armed(self):
        state = self.lc.on_request('recovery_demo_v1:once')
        self.assertEqual(state, ARMED)
        self.assertTrue(self.lc.snapshot()['live'])

    def test_bad_request_is_recorded_not_ignored(self):
        state = self.lc.on_request('x:sometimes')
        self.assertEqual(state, REQUESTED)
        snap = self.lc.snapshot()
        self.assertFalse(snap['live'])
        self.assertIn('bad mode', snap['error'])
        # and it must not fail any pick
        self.assertIsNone(self.lc.on_pick_attempt('target_box_a'))

    def test_once_applies_to_the_first_attempt_per_object(self):
        self.lc.on_request('recovery_demo_v1:once')
        first = self.lc.on_pick_attempt('target_box_a')
        self.assertIsNotNone(first)
        self.assertIn('attempt=1', first)
        self.assertEqual(self.lc.state, APPLIED)
        # retry of the SAME object passes
        self.assertIsNone(self.lc.on_pick_attempt('target_box_a'))
        # a different object has its own first attempt
        self.assertIsNotNone(self.lc.on_pick_attempt('target_box_b'))

    def test_always_applies_to_every_attempt(self):
        self.lc.on_request('exhaust_demo_v1:always')
        for i in (1, 2, 3):
            detail = self.lc.on_pick_attempt('target_box_a')
            self.assertIsNotNone(detail)
            self.assertIn('attempt=%d' % i, detail)
        self.assertEqual(self.lc.snapshot()['applied_count'], 3)

    def test_clear_disarms_and_resets_counters(self):
        self.lc.on_request('exhaust_demo_v1:always')
        self.lc.on_pick_attempt('target_box_a')
        state = self.lc.on_request('')
        self.assertEqual(state, CLEARED)
        snap = self.lc.snapshot()
        self.assertFalse(snap['live'])
        self.assertEqual(snap['applied_count'], 0)
        self.assertIsNone(self.lc.on_pick_attempt('target_box_a'))

    def test_rearm_after_clear_starts_fresh_once(self):
        self.lc.on_request('s:once')
        self.assertIsNotNone(self.lc.on_pick_attempt('target_box_a'))
        self.lc.on_request('')
        self.lc.on_request('s:once')
        # a fresh arm must fail the first attempt again
        self.assertIsNotNone(self.lc.on_pick_attempt('target_box_a'))

    def test_snapshot_is_json_ready_and_carries_request_id(self):
        self.lc.on_request('s5:always#r7')
        snap = self.lc.snapshot()
        self.assertEqual(snap['request_id'], 'r7')
        self.assertEqual(snap['state'], ARMED)
        self.assertEqual(snap['mode'], 'always')
        import json
        self.assertIsInstance(json.loads(json.dumps(snap)), dict)

    def test_sequential_cells_cannot_inherit_each_other(self):
        """The S7 0/10 regression, as a unit test.

        S5 arms `always`, then the clear must disarm it before another cell
        runs - otherwise every later episode is pre-failed.
        """
        self.lc.on_request('exhaust_demo_v1:always')
        self.assertIsNotNone(self.lc.on_pick_attempt('target_box_a'))
        cleared = self.lc.on_request('')
        self.assertEqual(cleared, CLEARED)
        # a following, non-injecting cell must see a clean slate
        self.assertIsNone(self.lc.on_pick_attempt('target_box_a'))
        self.assertEqual(self.lc.snapshot()['live'], False)


if __name__ == '__main__':
    unittest.main()
