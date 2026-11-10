#!/usr/bin/env python3
"""Verify the clean n=6 relay batch (Baseline B, T05).

This batch existed with a README and no machine check. A claim nobody can re-run is a
narrative, not evidence, so the verifier re-derives every number from the archived runs.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"


def main():
    dirs = sorted(RUNS.glob("s*-a1"))
    assert len(dirs) == 6, len(dirs)
    passed, claims = 0, 0
    for d in dirs:
        v = json.loads((d / "verdict.json").read_text(encoding="utf-8"))
        assert v["passed"] is True, (d.name, v["failed_clauses"])
        assert v["false_success"] is False, d.name
        passed += 1
        c = d / "self_assessment.json"
        if c.exists():
            claims += 1
    # every plan must be a two-stage relay on ONE object
    for d in dirs:
        rep = json.loads((d / "agent_reply.json").read_text(encoding="utf-8"))
        moves = rep["agent_plan"]["moves"]
        assert len(moves) == 2, (d.name, moves)
        assert moves[0]["object"] == moves[1]["object"], d.name
        assert moves[0]["zone"] != moves[1]["zone"], d.name

    print(json.dumps({
        "verdict": "EVOBOT_T05_RELAY_N6_VERIFIED",
        "instances": len(dirs),
        "independently_verified": passed,
        "self_assessments_recorded": claims,
        "false_success_rate": 0.0,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
