#!/usr/bin/env python3
"""Offline tests for the recovery eligibility predicate (M2.2-2, issue #21).

Truth-table suite: the frozen Week-1.5 eligibility verbatim - PICK typed
failures in the frozen set only, VERIFY any non-success outcome (plumbing
included: the re-verify decides), PLACE/OBSERVE never.  Plus the frozen-set
identity (decision_policy re-exports the SAME object) and recipe names.
FSMPolicy behavior parity is proven by the untouched 15-test policy suite.
Run: python3 test/test_recovery.py
"""

import unittest

from flexcell_skills.contracts.error_codes import PLUMBING_OUTCOME
from flexcell_skills.contracts.recovery import (
    RECOVERABLE_PICK_ERRORS, RECIPE_PICK, RECIPE_VERIFY, recovery_eligible)
from flexcell_skills.decision_policy import (
    RECOVERABLE_PICK_ERRORS as POLICY_SET)

PLUMB = PLUMBING_OUTCOME  # 255: no typed skill verdict (plumbing failure)


class TestPickEligibility(unittest.TestCase):

    def test_frozen_recoverable_codes(self):
        for code in (22, 23, 30):
            self.assertTrue(recovery_eligible('PICK', code, 1))

    def test_object_not_found_deliberately_not_recoverable(self):
        self.assertFalse(recovery_eligible('PICK', 21, 1))

    def test_plumbing_not_recoverable(self):
        self.assertFalse(recovery_eligible('PICK', -1, PLUMB))

    def test_success_not_eligible(self):
        self.assertFalse(recovery_eligible('PICK', 0, 0))

    def test_budget_is_not_the_predicates_job(self):
        # eligibility is independent of how much budget was spent - the
        # budget math stays with the policy owner (issue #21)
        self.assertTrue(recovery_eligible('PICK', 23, 1))


class TestVerifyEligibility(unittest.TestCase):

    def test_mismatch_recoverable(self):
        self.assertTrue(recovery_eligible('VERIFY', 0, 1))

    def test_failed_recoverable(self):
        self.assertTrue(recovery_eligible('VERIFY', 2, 2))

    def test_plumbing_recoverable_frozen(self):
        # the reobserve result is IGNORED and the re-verify decides - frozen
        self.assertTrue(recovery_eligible('VERIFY', -1, PLUMB))

    def test_success_not_eligible(self):
        self.assertFalse(recovery_eligible('VERIFY', 0, 0))


class TestNeverRecoverable(unittest.TestCase):

    def test_place_never(self):
        for code in (21, 23, 24, 25, 30, -1):
            self.assertFalse(recovery_eligible('PLACE', code, 1))

    def test_observe_never(self):
        for code in (0, 2, 3, -1):
            self.assertFalse(recovery_eligible('OBSERVE', code, 1))

    def test_unknown_action_never(self):
        self.assertFalse(recovery_eligible('TELEPORT', 23, 1))


class TestFrozenSetIdentity(unittest.TestCase):

    def test_decision_policy_reexports_same_object(self):
        self.assertIs(RECOVERABLE_PICK_ERRORS, POLICY_SET)

    def test_frozen_values(self):
        self.assertEqual(RECOVERABLE_PICK_ERRORS, frozenset({22, 23, 30}))


class TestRecipes(unittest.TestCase):

    def test_recipe_names(self):
        self.assertEqual(RECIPE_PICK, 'REOBSERVE+RETRY')
        self.assertEqual(RECIPE_VERIFY, 'REOBSERVE+REVERIFY')


if __name__ == '__main__':
    unittest.main()
