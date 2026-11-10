#!/usr/bin/env python3
"""Failure attribution from MEASURED evidence (experiment protocol rule 5).

The rule exists because the previous track published three wrong root causes; each was
a plausible story told before reading the data. This classifier only emits a class when
the evidence dict contains the discriminator for it. Otherwise it emits UNKNOWN.

It is deliberately conservative: UNKNOWN is better than a confident wrong story.
"""
import json
import sys
from pathlib import Path


def classify(evidence):
    """Return (class, measured_reason). evidence is the verifier/run evidence dict."""
    if not isinstance(evidence, dict) or not evidence:
        return "UNKNOWN", "no evidence supplied"
    err = str(evidence.get("error_code", ""))
    detail = str(evidence.get("detail", "")).lower()
    outcome = evidence.get("outcome")

    if "participant index" in detail or "failed to create domain" in detail:
        return "runtime", "DDS participant/domain creation failed"
    if "another" in detail and "goal is active" in detail:
        return "runtime", "a skill goal was still active at handover"
    if "declared destination occupied" in detail or "invalid clearance" in detail:
        return "planning", "plan declared an occupied or out-of-contract destination"
    if "plan must declare every observed object" in detail:
        return "planning", "plan omitted an object present in the scene"
    if "another task owns the arm" in detail:
        return "runtime", "arm admission held by another task"
    if "pose_not_reached" in detail or "outside tolerance" in detail:
        return "kinematics", "measured pose did not reach the planned target"
    if "object missing" in detail or evidence.get("absent"):
        return "perception", "an object was not observed in the final state"
    if "place failed" in detail or "err_place_failed" in detail:
        return "grasp", "release/place failed at the native component"
    if "grasp" in detail and "fail" in detail:
        return "grasp", "grasp failed"
    if outcome in (1, "1") and err in ("62", "60", "64"):
        return "UNKNOWN", "component failed (code %s); no discriminator" % err
    if evidence.get("harness") or "stack unavailable" in detail:
        return "tooling", "the launcher or observation pipeline failed"
    return "UNKNOWN", "no discriminator matched; refusing to guess"


def main(argv=None):
    argv = argv or sys.argv[1:]
    evidence = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    cls, why = classify(evidence)
    print(json.dumps({"failure_class": cls, "measured_reason": why}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
