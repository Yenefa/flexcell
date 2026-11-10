#!/usr/bin/env python3
"""The old P2 attempt is VOID. This verifier asserts exactly that.

Two separate reasons, both recorded rather than papered over:
  1. the run hit budget_exceeded at 54,142 tokens, so "no edit happened" is a
     truncation artefact and cannot be read as a capability result;
  2. this directory holds only the README - the raw artefacts were never archived
     for this attempt, so it cannot be re-checked at all.

The valid replacement is setup/acceptance/p2_reuse_budget_20261110/.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent


def main():
    assert not (HERE / "result.json").exists(), (
        "raw artefacts appeared here; re-check whether this run is still void")
    readme = (HERE / "README.md").read_text(encoding="utf-8")
    assert "INVALID" in readme or "无效" in readme, "README must mark the run void"
    print(json.dumps({
        "verdict": "P2_OLD_RUN_VOID_NO_ARTEFACTS_AND_BUDGET_TRUNCATED",
        "tokens_reported": 54142,
        "budget_exceeded": True,
        "raw_artefacts_present": False,
        "use_instead": "setup/acceptance/p2_reuse_budget_20261110/",
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
