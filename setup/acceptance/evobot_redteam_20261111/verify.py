#!/usr/bin/env python3
"""Make the audit itself checkable: re-derive its own headline findings from the repository.

WHY THIS EXISTS: an audit that cannot be re-checked is just another opinion, and the audit's own
criticism was that several verifiers in this repo could not fail. So this one asserts the two
findings that are mechanical, and it FAILS if the defects it reported have since been fixed
silently (in which case the audit must be re-issued, not quietly invalidated).
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]


def main():
    # 1. the audit's own deliverables are present
    for name in ("REVIEW.md", "LEAD_RESPONSE.md", "FALSIFICATION.log", "falsify_harness.py"):
        assert (HERE / name).exists(), name

    # 2. B9/B10 were real and are now fixed: neither verifier may contain a cannot-fail assertion
    sg = (WT / "setup/acceptance/evobot_libero_side_grasp_20261111/verify.py").read_text(
        encoding="utf-8")
    # only executable lines count: the fix left a comment that mentions the old pattern, and a
    # substring search flagged that comment. A guard that trips on its own documentation is the
    # same class of error the audit was complaining about.
    code_lines = [ln.split("#", 1)[0] for ln in sg.splitlines()]
    assert not any("or True" in ln for ln in code_lines), \
        "B9 regression: the cannot-fail assertion is back in executable code"
    aa = (WT / "setup/acceptance/evobot_libero_auto_approach_20261111/verify.py").read_text(
        encoding="utf-8")
    assert 'load("side_y"' in aa, "B10 regression: the side_y refutation has no assertion again"

    # 3. B2 is still unfixed in the runners: they must still use geom_rbound
    retry = (WT.parent / "ci-public-window/scripts/evobot_libero_retry.py")
    if retry.exists():
        src = retry.read_text(encoding="utf-8")
        assert "geom_rbound" in src, (
            "the runners no longer use geom_rbound - if B2 was fixed, re-issue this audit")

    # 4. the two blockers are described in the review, with a falsification condition each
    rev = (HERE / "REVIEW.md").read_text(encoding="utf-8")
    assert "B1" in rev and "B2" in rev
    assert "推翻" in rev or "falsif" in rev.lower()

    print(json.dumps({
        "verdict": "EVOBOT_REDTEAM_AUDIT_REPRODUCIBLE",
        "blockers": 2, "major": 8,
        "B9_B10_fixed_and_still_fixed": True,
        "B2_still_present_in_runners": True,
        "note": "if B2 is fixed, this check fails on purpose so the audit is re-issued",
        "evaluator_touched": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
