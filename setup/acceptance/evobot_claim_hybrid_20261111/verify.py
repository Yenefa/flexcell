#!/usr/bin/env python3
"""Verify the two-condition claim, and that its false-success risk is now demonstrated elsewhere.

This batch measured an improvement (40/40 on coverage, 64/64 hybrid in-sample) and the decision
was still to refuse it. The evidence for that refusal lives in a later batch, so this verifier
points at it rather than pretending the refusal is self-evident here.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]
text = (HERE / "hybrid.txt").read_text(encoding="utf-8")


def main():
    def row(label):
        m = re.search(r"%s\s+coverage\s+(\d+)/(\d+)\s+correct\s+(\d+)\s+wrong\s+(\d+)"
                      % re.escape(label), text)
        assert m, label
        return tuple(int(x) for x in m.groups())

    d = row("two-condition check")
    l = row("LLM self-assessment")
    h = row("hybrid (det where possible)")
    assert d == (40, 64, 40, 0), d
    assert l[:3] == (64, 64, 45) and l[3] == 19, l
    assert h == (64, 64, 64, 0), h

    # the refusal reason must be on disk, not only in the commit message
    refusal = WT / "setup" / "acceptance" / "evobot_wrongplan_probe_20261111" / "verify.py"
    assert refusal.exists(), "the demonstration that this check admits false success is missing"

    # the module itself must not be wired into the runner
    runner = WT.parent / "ci-public-window" / "scripts" / "run_batch.sh"
    if runner.exists():
        src = runner.read_text(encoding="utf-8")
        assert "--agent-claim" in src          # the LLM claim path is still what runs
        assert "runtime/verifier/claim.py" not in src

    print(json.dumps({
        "verdict": "EVOBOT_TWO_CONDITION_CLAIM_MEASURED_NOT_ADOPTED",
        "two_condition": "40/64 coverage, 40 correct, 0 false success, 0 false failure",
        "llm": "64/64, 45 correct, 19 false failures",
        "hybrid_in_sample": "64/64",
        "adopted": False,
        "reason": ("verifies execution against the plan, not the plan against the "
                   "instruction - demonstrated by evobot_wrongplan_probe_20261111"),
        "evaluator_touched": False,
        "skill_layer_touched": False,
        "claim_mechanism_changed": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
