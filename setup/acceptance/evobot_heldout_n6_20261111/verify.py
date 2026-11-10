#!/usr/bin/env python3
"""Verify the FIRST held-out generalisation batch (superseded baseline).

Kept because it is the first time a generalisation number was legal to report, and a
superseded result must remain auditable rather than be quietly replaced.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"


def main():
    dirs = sorted(p for p in RUNS.iterdir() if p.is_dir())
    assert len(dirs) == 6, len(dirs)
    passed, clean, disputed = 0, 0, 0
    for d in dirs:
        v = json.loads((d / "verdict.json").read_text(encoding="utf-8"))
        assert not v.get("false_success"), d.name
        if v["passed"]:
            passed += 1
            t = d / "task.out"
            txt = t.read_text() if t.exists() else ""
            outcome = (json.loads(txt.split("RESULT ", 1)[1]).get("outcome")
                       if "RESULT " in txt else None)
            if outcome == 0:
                clean += 1
            else:
                disputed += 1
    # the recorded summary must match what the verdicts say
    assert passed == 6 and clean == 5 and disputed == 1, (passed, clean, disputed)
    print(json.dumps({
        "verdict": "EVOBOT_FIRST_HELDOUT_VERIFIED",
        "instances": len(dirs),
        "independent_pass": passed,
        "clean_pass": clean,
        "disputed_pass": disputed,
        "status": "superseded by evobot_regression_v01_20261111",
        "false_success_rate": 0.0,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
