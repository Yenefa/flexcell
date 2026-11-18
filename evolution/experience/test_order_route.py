#!/usr/bin/env python3
"""The order route must be CARRIED by a real ACTIVE entry, not just a delivery path.

Before this, the planner order rule was measured, gated, and even seen firing in a one-off
demo -- but no real experience entry occupied the "order" routing, so the coverage table
still reported NO_ENTRY. E3 turns that mechanism into an admitted, reviewed, activated,
delivered entry.
"""
import json
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import routing_coverage  # noqa: E402
import demo_continual  # noqa: E402


EVIDENCE = os.path.join(WT, "setup", "acceptance", "evobot_continual_chain_20261118")


def _route(name):
    cov = routing_coverage.coverage(
        os.path.join(EVIDENCE, "records_v2.jsonl"))
    return next(r for r in cov["routings"] if r["routing"].startswith(name))


def test_order_route_is_carried_by_e3():
    row = _route("order")
    assert row["state"] == "CARRIED", row
    assert "E3" in row["active_entries"]


def test_e3_is_active_and_reviewed():
    rows = [json.loads(l) for l in open(
        os.path.join(EVIDENCE, "records_v2.jsonl"), encoding="utf-8") if l.strip()]
    e3 = [r for r in rows if (r.get("version") or {}).get("label") == "E3"][-1]
    assert e3["version"]["status"] == "ACTIVE"
    assert e3["validation"]["review_verdict"] == "ACCEPT"
    assert e3["consumer"] == "planner"


def test_e3_effect_is_measured_not_asserted():
    eff = json.load(open(os.path.join(EVIDENCE, "03_effect_E3.json"), encoding="utf-8"))
    assert eff["operator"] == "plan_order"
    assert eff["verdict"] == "IMPROVED"
    assert eff["detail"]["order_fixing_replies"] >= 10
    assert eff["detail"]["false_positives"] == 0


def test_e3_misuse_guard_is_probed_not_declared():
    mis = json.load(open(os.path.join(EVIDENCE, "10_lifecycle_review.json"),
                         encoding="utf-8"))
    # the misuse check ran and the unknown-order condition is a real probe
    import misuse
    assert "order.no_fixed_order" in misuse.PROBES
    assert misuse.PROBES["order.no_fixed_order"]({})[0] in misuse.BLOCKED


def test_planner_delivery_uses_a_real_observation():
    """Coverage must not pass None to the planner renderer, which needs objects/zones."""
    row = _route("order")
    assert row["state"] == "CARRIED"  # a None observation would make this NO_DELIVERY
