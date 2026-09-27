#!/usr/bin/env python3
"""Offline contract tests for the SkillResult v2 layer (M2.2-1, issue #20).

Covers: legacy->canonical mapping (full key paths), verify outcome-context
(VERIFIED=OK vs MISMATCH=VERIFY_FAILED), plumbing sentinel -> TIMEOUT,
fail-closed unknowns (ERR_INTERNAL + mapping_warning), backward-compatible
canonical values, status derivation (incl. the VERIFY asymmetry),
previous_skill_result shaping, and the STATUS_* constant consistency
across all four skill action files (parsed as text - no ROS imports).
Run: python3 test/test_contracts.py
"""

import re
import unittest
from pathlib import Path

from flexcell_skills.contracts import error_codes as ec
from flexcell_skills.contracts.skill_result import (
    derive_status, previous_skill_result)

ACTION_DIR = Path(__file__).resolve().parents[2] / 'flexcell_interfaces' / 'action'


class TestBackwardCompat(unittest.TestCase):
    """Canonical values reuse legacy numbers - backward compat by value."""

    def test_shared_values_unchanged(self):
        self.assertEqual(ec.ERR_OK, 0)
        self.assertEqual(ec.ERR_INVALID_GOAL, 1)
        self.assertEqual(ec.ERR_INTERNAL, 2)
        self.assertEqual(ec.ERR_IK_UNREACHABLE, 10)
        self.assertEqual(ec.ERR_OBJECT_NOT_FOUND, 21)   # legacy ERR_OBJECT_UNKNOWN
        self.assertEqual(ec.ERR_WORLD_STATE_UNAVAILABLE, 22)
        self.assertEqual(ec.ERR_GRASP_FAILED, 23)
        self.assertEqual(ec.ERR_NOT_CARRIED, 24)
        self.assertEqual(ec.ERR_PLACE_FAILED, 25)
        self.assertEqual(ec.ERR_MOTION_FAILED, 30)
        self.assertEqual(ec.ERR_CANCELED, 32)
        self.assertEqual(ec.ERR_RESOURCE_BUSY, 41)
        self.assertEqual(ec.ERR_SKILL_CONTRACT_VIOLATION, 52)

    def test_new_values_in_free_range(self):
        for v in (ec.ERR_VERIFY_FAILED, ec.ERR_TIMEOUT,
                  ec.ERR_STALE_WORLD, ec.ERR_SAFETY_REJECTED):
            self.assertNotIn(v, (0, 1, 2, 3, 10, 21, 22, 23, 24, 25, 30, 32,
                                 41, 50, 51, 52), 'collides with a legacy code')


class TestMapping(unittest.TestCase):

    def test_observe_world_state_normalized(self):
        self.assertEqual(ec.canonicalize('OBSERVE', 3, 1),
                         (ec.ERR_WORLD_STATE_UNAVAILABLE, None))

    def test_pick_full_path(self):
        for code, canon, outcome in (
                (0, ec.ERR_OK, 0), (1, ec.ERR_INVALID_GOAL, 1),
                (2, ec.ERR_INTERNAL, 1), (10, ec.ERR_IK_UNREACHABLE, 1),
                (21, ec.ERR_OBJECT_NOT_FOUND, 1),
                (22, ec.ERR_WORLD_STATE_UNAVAILABLE, 1),
                (23, ec.ERR_GRASP_FAILED, 1), (30, ec.ERR_MOTION_FAILED, 1),
                (32, ec.ERR_CANCELED, 2), (41, ec.ERR_RESOURCE_BUSY, 1)):
            self.assertEqual(ec.canonicalize('PICK', code, outcome)[0], canon)

    def test_place_specific_codes(self):
        self.assertEqual(ec.canonicalize('PLACE', 24, 1)[0], ec.ERR_NOT_CARRIED)
        self.assertEqual(ec.canonicalize('PLACE', 25, 1)[0], ec.ERR_PLACE_FAILED)

    def test_verify_outcome_context(self):
        self.assertEqual(ec.canonicalize('VERIFY', 0, 0)[0], ec.ERR_OK)
        self.assertEqual(ec.canonicalize('VERIFY', 0, 1)[0], ec.ERR_VERIFY_FAILED)

    def test_plumbing_sentinel_maps_to_timeout(self):
        for skill in ('OBSERVE', 'PICK', 'PLACE', 'VERIFY'):
            self.assertEqual(ec.canonicalize(skill, -1, 255),
                             (ec.ERR_TIMEOUT, None))
            self.assertEqual(ec.canonicalize(skill, -1, None)[0], ec.ERR_TIMEOUT)

    def test_unknown_code_fails_closed(self):
        canon, warning = ec.canonicalize('PICK', 99, 1)
        self.assertEqual(canon, ec.ERR_INTERNAL)
        self.assertIn('unmapped', warning)

    def test_unknown_skill_fails_closed(self):
        canon, warning = ec.canonicalize('TELEPORT', 0, 0)
        self.assertEqual(canon, ec.ERR_INTERNAL)
        self.assertIn('unknown skill', warning)

    def test_planted_violation_no_silent_passthrough(self):
        # a future unmapped code must never reach a policy unnamed
        for skill in ('OBSERVE', 'PICK', 'PLACE', 'VERIFY'):
            canon, warning = ec.canonicalize(skill, 77, 1)
            self.assertEqual(canon, ec.ERR_INTERNAL)
            self.assertTrue(warning)


class TestStatusDerivation(unittest.TestCase):

    def test_pick_observe_place(self):
        for skill in ('OBSERVE', 'PICK', 'PLACE'):
            self.assertEqual(derive_status(skill, 0), ec.STATUS_SUCCESS)
            self.assertEqual(derive_status(skill, 1), ec.STATUS_FAILURE)
            self.assertEqual(derive_status(skill, 2), ec.STATUS_CANCELED)
            self.assertEqual(derive_status(skill, 255), ec.STATUS_NONE)

    def test_verify_asymmetry(self):
        self.assertEqual(derive_status('VERIFY', 0), ec.STATUS_SUCCESS)
        self.assertEqual(derive_status('VERIFY', 1), ec.STATUS_FAILURE)
        self.assertEqual(derive_status('VERIFY', 2), ec.STATUS_FAILURE)


class TestPreviousSkillResult(unittest.TestCase):

    def test_real_pick_failure(self):
        d = previous_skill_result('PICK', 1, 23)
        self.assertEqual(d['skill'], 'PICK')
        self.assertEqual(d['status'], ec.STATUS_FAILURE)
        self.assertEqual(d['error_code'], 23)
        self.assertEqual(d['canonical_error_code'], ec.ERR_GRASP_FAILED)
        self.assertNotIn('mapping_warning', d)

    def test_plumbing_shape(self):
        d = previous_skill_result('PICK', 255, -1)
        self.assertEqual(d['status'], ec.STATUS_NONE)
        self.assertEqual(d['canonical_error_code'], ec.ERR_TIMEOUT)
        self.assertNotIn('mapping_warning', d)

    def test_verify_mismatch_shape(self):
        d = previous_skill_result('VERIFY', 1, 0)
        self.assertEqual(d['status'], ec.STATUS_FAILURE)
        self.assertEqual(d['canonical_error_code'], ec.ERR_VERIFY_FAILED)

    def test_unmapped_carries_mapping_warning(self):
        d = previous_skill_result('PICK', 1, 99)
        self.assertEqual(d['canonical_error_code'], ec.ERR_INTERNAL)
        self.assertIn('mapping_warning', d)


class TestActionConstantConsistency(unittest.TestCase):
    """STATUS_* values must be identical across all four skill actions."""

    EXPECTED = {'NONE': 0, 'SUCCESS': 1, 'FAILURE': 2, 'SKIPPED': 3,
                'CANCELED': 4}

    def test_status_constants_across_actions(self):
        for name in ('Observe', 'PickObject', 'PlaceObject', 'VerifyObject'):
            text = (ACTION_DIR / ('%s.action' % name)).read_text(encoding='utf-8')
            found = dict(re.findall(r'uint8 STATUS_(\w+)=(\d+)', text))
            self.assertEqual(found, {k: str(v) for k, v in self.EXPECTED.items()},
                             '%s.action STATUS constants drifted' % name)
            self.assertIn('uint8 status', text)


if __name__ == '__main__':
    unittest.main()
