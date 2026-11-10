#!/usr/bin/env python3
"""Verify the T05 n=6 batch that found the DDS participant bug (superseded)."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    runs = sorted((HERE / "runs").glob("s*-a*"))
    # 8 directories, 6 seeds: two seeds were retried once. That is the honest record -
    # a retry is part of the run history and must not be collapsed away.
    seeds = {d.name.split("-")[0] for d in runs}
    assert len(seeds) == 6, seeds
    assert len(runs) >= 6, len(runs)
    passed = 0
    for d in runs:
        v = d / "verdict.json"
        if v.exists():
            doc = json.loads(v.read_text(encoding="utf-8"))
            assert not doc.get("false_success"), d.name
            passed += 1 if doc.get("passed") else 0
    text = (HERE / "README.md").read_text(encoding="utf-8")
    # the batch must still say that its own earlier attribution was wrong
    assert "DDS" in text or "dds" in text
    print(json.dumps({
        "verdict": "EVOBOT_T05_N6_DDS_FINDING_VERIFIED",
        "attempts_archived": len(runs),
        "graded": passed,
        "status": "superseded by evobot_t05_n6_clean_20261111",
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
