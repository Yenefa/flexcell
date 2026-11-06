"""Regression guard for the gate_refusal negative control (issue #121 review).

The review reproduced PASS/0 for a gate_refusal run whose place actually
succeeded: the ordinary success branch overrode the expected-failure branch.
The decision now lives in one pure function, so both branches stay pinned.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))

import sim_smoke


def test_gate_refusal_never_passes_on_success():
    # A place that reached the goal means the gate did not fire.
    assert sim_smoke.classify_outcome('gate_refusal', True, False) == 'ROBOT_FAILURE'
    assert sim_smoke.classify_outcome('gate_refusal', True, True) == 'ROBOT_FAILURE'


def test_gate_refusal_refusal_is_the_expected_outcome():
    assert sim_smoke.classify_outcome('gate_refusal', False, True) == 'EXPECTED_FAILURE'
    assert sim_smoke.classify_outcome('gate_refusal', False, False) == 'ROBOT_FAILURE'


def test_other_cases_unchanged():
    assert sim_smoke.classify_outcome('normal', True, False) == 'PASS'
    assert sim_smoke.classify_outcome('normal', False, False) == 'ROBOT_FAILURE'
    assert sim_smoke.classify_outcome('unreachable_place', False, True) == 'EXPECTED_FAILURE'
    assert sim_smoke.classify_outcome('regrasp', True, False) == 'PASS'
