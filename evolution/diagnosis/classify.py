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
    # The composite contract raises TWO different wordings for the same condition:
    #   prepare_plan  -> "declared destination occupied at <stage>"
    #   pre-stage snap-> "state drift or occupied destination before <stage>"
    # The second is what the unseen task runs actually hit (err 61), so the classifier
    # must recognise it; otherwise every real same-bin conflict is reported UNKNOWN.
    # The composite contract uses THREE wordings for the same occupancy condition:
    #   prepare_plan  -> "declared destination occupied at <stage>"
    #   pre-stage snap-> "state drift or occupied destination before <stage>"  (err 61)
    # The unseen-task runs hit the second, and a naive "destination occupied" match
    # misses it because the words are reversed. Match BOTH orders, and check the
    # combined phrase BEFORE the bare "state drift" so a real same-bin conflict is not
    # misfiled as a state problem.
    if "occupied destination" in detail or "destination occupied" in detail:
        return "planning", "plan declared an occupied destination"
    if "invalid clearance" in detail:
        return "planning", "plan declared an out-of-contract clearance"
    if "state drift" in detail:
        return "state", "measured state drifted from the expected chain position"
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
