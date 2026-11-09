#!/usr/bin/env python3
"""C10: mechanism check on the MTC episodes of C8 and C9."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
C8 = ROOT / "setup" / "acceptance" / "c8_strict_dual_20261109"
C9 = ROOT / "setup" / "acceptance" / "c9_strict_dual_n9_20261109"
HERE = Path(__file__).parent

CASES = [("C8", "mtc-b"), ("C8", "mtc-c"), ("C8", "mtc-f"),
         ("C9", "mtc-h"), ("C9", "mtc-i"), ("C9", "mtc-k"),
         ("C9", "mtc-m"), ("C9", "mtc-p"), ("C9", "mtc-q")]

def main():
    fails, passes = [], []
    for phase, run in CASES:
        base = C8 if phase == "C8" else C9
        doc = json.loads((base / run / "episode.json").read_text())
        steps = doc.get("steps", [])
        to = sum(1 for s in steps if "planning reply timed out" in str(s.get("executor_result", {}).get("detail", "")))
        busy = sum(1 for s in steps if "planner busy" in str(s.get("executor_result", {}).get("detail", "")))
        (fails if doc["final_state"]["error_code"] != 0 else passes).append((run, to, busy))
    assert len(fails) == 3 and len(passes) == 6
    assert all(to >= 1 and busy >= 1 for _, to, busy in fails), fails
    assert all(to == 0 and busy == 0 for _, to, busy in passes), passes
    print(json.dumps({"verdict": "C10_TIMEOUT_ASSOCIATION", "failures": fails, "passes": passes}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
