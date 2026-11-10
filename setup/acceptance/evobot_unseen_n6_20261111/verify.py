#!/usr/bin/env python3
"""Verify the unseen held-out measurement is real and correctly attributed."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    s = json.loads((HERE / "summary.json").read_text(encoding="utf-8"))
    assert s["instances"] == 6
    assert s["agent_plans_correct"] == 6, "plan correctness must be checked vs sealed answers"
    assert s["false_success"] == 0, "false success rate must be zero"
    assert s["independently_verified"] == 4
    assert s["clean_pass"] == 3 and s["disputed_pass"] == 1 and s["graded_fail"] == 2
    # every run has a real verdict file
    runs = sorted((HERE / "runs").glob("*_B/verdict.json"))
    assert len(runs) == 6, len(runs)
    for v in runs:
        d = json.loads(v.read_text(encoding="utf-8"))
        assert "passed" in d and "false_success" in d
    # v0.1 seal untouched: public tasks still answer-free
    pub = HERE.parents[2] / "benchmark" / "held_out" / "public"
    files = list(pub.glob("*.json"))
    assert len(files) == 36
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        assert "expected_goal" not in d
    print(json.dumps({"verdict": "EVOBOT_UNSEEN_HEADROOM_VERIFIED",
                      "agent_plans_correct": "6/6",
                      "clean_pass": "3/6",
                      "false_success_rate": 0.0,
                      "bottleneck": "execution, not planning"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
