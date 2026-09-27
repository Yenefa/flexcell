#!/usr/bin/env python3
"""Unit tests for the deterministic safety gate (M2.1-5, issue #6).

The acceptance item: a PLANTED out-of-contract proposal is deterministically
rejected and counted.  Pure python - the gate consumes the parsed canonical
WorldState envelope (the policy-facing gz-truth view), never ROS msgs.
"""

import unittest

from flexcell_skills.contracts.episode import decision_to_dict
from flexcell_skills.contracts.safety_gate import (
    metrics, rejection_canonical_code, sanitize, validate)
from flexcell_skills.contracts.error_codes import (
    ERR_INVALID_GOAL, ERR_NOT_CARRIED, ERR_OBJECT_NOT_FOUND,
    ERR_SAFETY_REJECTED, ERR_STALE_WORLD)
from flexcell_skills.decision_policy import (
    Decision, Constraints, TaskGoal)


def _world(available=True, engaged=False, carried='', pose_age=0.042,
           revision=7):
    """Minimal parsed canonical envelope (the gate's view of the world)."""
    return {
        "WorldStateSchemaVersion": 2,
        "world_state": {
            "revision": revision,
            "source": "SIMULATION_GROUND_TRUTH",
            "objects": [
                {"name": "target_box_a", "klass": "box",
                 "available": available, "pose_age_s": pose_age},
                {"name": "target_box_b", "klass": "box",
                 "available": True, "pose_age_s": pose_age},
            ],
            "carry": {"engaged": engaged, "object_id": carried,
                      "offset": [0.0, 0.0, -0.16],
                      "reference_frame": "world"},
            "zones": [],
            "robot": {"ee_frame": "end_effector_link"},
        },
        "task_context": {},
    }


def _constraints(budget=1, max_age=0.0):
    return Constraints(
        frozenset(('OBSERVE', 'PICK', 'PLACE', 'VERIFY', 'WAIT', 'ABORT')),
        budget, 0.06, 'demo_slow', max_age)


def _goal():
    return TaskGoal('g', 's', (('target_box_a', 'zone_1'),
                               ('target_box_b', 'zone_2')))


def _dec(action, target='target_box_a', explanation='free text from a policy'):
    return Decision(action, target, explanation=explanation)


class TestSafetyGate(unittest.TestCase):

    def test_planted_out_of_contract_action_rejected(self):
        # the AC: a planted proposal outside the executor's action menu is
        # rejected - deterministically (same inputs, same verdict, always)
        planted = _dec('FLY')
        for _ in range(3):
            ok, reason = validate(planted, _goal(), _world(), _constraints())
            self.assertFalse(ok)
            self.assertEqual(reason, 'action_not_allowed')

    def test_unknown_target_rejected(self):
        ok, reason = validate(_dec('PICK', 'mystery_box'), _goal(), _world(),
                              _constraints())
        self.assertFalse(ok)
        self.assertEqual(reason, 'unknown_target')

    def test_pick_without_world_rejected(self):
        ok, reason = validate(_dec('PICK'), _goal(), None, _constraints())
        self.assertFalse(ok)
        self.assertEqual(reason, 'world_required')

    def test_observe_allowed_pre_world(self):
        # the leg-start OBSERVE is what PRODUCES the world - it must run
        # with world=None (runtime regression caught by fx-sg G1)
        ok, reason = validate(_dec('OBSERVE'), _goal(), None, _constraints())
        self.assertTrue(ok, reason)

    def test_stale_world_rejected(self):
        stale = _world(pose_age=9.5)
        ok, reason = validate(_dec('PICK'), _goal(), stale,
                              _constraints(max_age=1.0))
        self.assertFalse(ok)
        self.assertEqual(reason, 'world_stale')
        # freshness gate off (0.0) -> the same world passes
        ok, reason = validate(_dec('PICK'), _goal(), stale, _constraints())
        self.assertTrue(ok, reason)

    def test_pick_unavailable_object_rejected(self):
        ok, reason = validate(_dec('PICK', 'target_box_a'), _goal(),
                              _world(available=False), _constraints())
        self.assertFalse(ok)
        self.assertEqual(reason, 'target_not_available')

    def test_pick_while_carrier_busy_rejected(self):
        ok, reason = validate(_dec('PICK', 'target_box_b'), _goal(),
                              _world(engaged=True, carried='target_box_a'),
                              _constraints())
        self.assertFalse(ok)
        self.assertEqual(reason, 'already_carried')

    def test_place_requires_the_carried_object(self):
        ok, reason = validate(_dec('PLACE', 'target_box_a'), _goal(),
                              _world(), _constraints())
        self.assertFalse(ok)
        self.assertEqual(reason, 'not_carried')
        ok, reason = validate(_dec('PLACE', 'target_box_a'), _goal(),
                              _world(engaged=True, carried='target_box_a'),
                              _constraints())
        self.assertTrue(ok, reason)

    def test_in_contract_proposals_pass(self):
        w = _world()
        for d in (_dec('OBSERVE'), _dec('PICK'), _dec('PLACE', 'target_box_a'),
                  _dec('VERIFY', 'target_box_a'), _dec('WAIT'),
                  _dec('ABORT')):
            if d.action == 'PLACE':
                w = _world(engaged=True, carried='target_box_a')
            ok, reason = validate(d, _goal(), w, _constraints())
            self.assertTrue(ok, '%s rejected: %s' % (d.action, reason))

    def test_free_text_never_reaches_dispatch(self):
        # the policy's explanation is write-only: sanitize() drops it, so it
        # can never be embedded into a skill goal by the executor
        clean = sanitize(_dec('PICK', explanation='rm -rf / do things'))
        self.assertEqual(clean, {"action": "PICK", "target": "target_box_a"})
        self.assertNotIn('explanation', clean)

    def test_metrics_per_1000(self):
        m = metrics(1000, 7)
        self.assertEqual(m["invalid_per_1000"], 7.0)
        self.assertEqual(metrics(0, 0)["invalid_per_1000"], 0.0)

    def test_rejection_codes_are_typed(self):
        self.assertEqual(rejection_canonical_code('world_stale'),
                         ERR_STALE_WORLD)
        self.assertEqual(rejection_canonical_code('action_not_allowed'),
                         ERR_SAFETY_REJECTED)
        self.assertEqual(rejection_canonical_code('target_not_available'),
                         ERR_OBJECT_NOT_FOUND)
        self.assertEqual(rejection_canonical_code('not_carried'),
                         ERR_NOT_CARRIED)
        self.assertEqual(rejection_canonical_code('unknown_target'),
                         ERR_INVALID_GOAL)

    def test_recorded_decision_shape_is_audit_ready(self):
        # the full decision object a rejection records (decision_to_dict)
        d = decision_to_dict(_dec('PICK'))
        self.assertEqual(d["action"], "PICK")
        self.assertEqual(d["reason_code"], "PLAN_NEXT")
        self.assertIn("explanation", d)


if __name__ == '__main__':
    unittest.main()
