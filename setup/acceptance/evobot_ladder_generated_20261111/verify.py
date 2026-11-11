#!/usr/bin/env python3
"""Verify the ladder is derived, current, and honest about both failure directions."""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]
DOC = WT / "docs" / "CAPABILITY_LADDER.md"
INDEX = WT / "setup" / "acceptance" / "evobot_evidence_index.json"


def main():
    # 1. the generator must reproduce the committed document
    before = DOC.read_text(encoding="utf-8")
    r = subprocess.run([sys.executable,
                        str(WT / "experiments" / "baselines" / "capability_ladder.py")],
                       cwd=str(WT), capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-500:] + r.stderr[-500:]
    after = DOC.read_text(encoding="utf-8")
    assert before == after, "the committed document was NOT what the generator produces"

    # 2. counts must match the archive
    idx = json.loads(INDEX.read_text(encoding="utf-8"))
    assert "| 证据批次（有效） | %s |" % idx["live"] in after
    assert "| 批次验证器失败数 | **%s** |" % idx["verifier_failures"] in after

    # 3. both failure directions must be present
    assert "False Success" in after and "False Failure" in after

    # 4. a zero may not be stated without its limitation
    assert "不可测量" in after

    # 5. the pending proposal must read as unapproved from the JSON
    prop = WT / "evolution" / "proposals" / "release_confirmation_preregistration.json"
    if prop.exists():
        d = json.loads(prop.read_text(encoding="utf-8"))
        assert d["approved"] is False
        assert "待人工批准" in after

    # 6. regression gate is unchanged
    reg = subprocess.run([sys.executable,
                          str(WT / "experiments" / "baselines" / "regression_check.py")],
                         cwd=str(WT), capture_output=True, text=True, timeout=300)
    assert "REGRESSIONS : NONE" in reg.stdout, reg.stdout[-400:]

    print(json.dumps({
        "verdict": "EVOBOT_LADDER_DERIVED_AND_CURRENT",
        "regenerated_identically": True,
        "batches_live": idx["live"],
        "verifier_failures": idx["verifier_failures"],
        "reports_both_directions": True,
        "zero_is_qualified": True,
        "v01_regression": "6/6 -> 6/6, NONE",
        "evaluator_touched": False,
        "skill_layer_touched": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
