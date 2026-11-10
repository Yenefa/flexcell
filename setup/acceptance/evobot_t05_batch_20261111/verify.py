#!/usr/bin/env python3
"""Verify the superseded T05 batch, and that its own defects are documented.

A superseded batch stays auditable. This one recorded a 1/3 "execution" rate that was
later traced to DDS participant exhaustion, so the verifier checks BOTH the archived
verdicts and that the correction exists in the repository.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]


def main():
    summary = (HERE / "summary.txt").read_text(encoding="utf-8")
    assert "PASS among executed" in summary
    verdicts = sorted((HERE / "runs").glob("*/verdict.json"))
    assert verdicts, "no archived verdicts"
    for v in verdicts:
        json.loads(v.read_text(encoding="utf-8"))   # must all parse
    # the correction must still be present, or this record becomes misleading
    corrected = (WT / "setup" / "acceptance" / "evobot_t05_n6_20261111" / "README.md")
    assert corrected.exists()
    text = corrected.read_text(encoding="utf-8").lower()
    assert "dds" in text and "participant" in text
    print(json.dumps({
        "verdict": "EVOBOT_T05_BATCH_SUPERSEDED_AND_CORRECTED",
        "archived_verdicts": len(verdicts),
        "correction_retained": True,
        "status": "superseded by evobot_t05_n6_clean_20261111",
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
