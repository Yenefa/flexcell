#!/usr/bin/env python3
"""P2 item (2): can the agent author its OWN experience record? Three tries, none did.

This verifier asserts the NEGATIVE result and the three attempts, so the record
cannot later be read as a success. Attempt 0 is excluded on purpose: the runner
used to break the instant the gates passed, so the agent was never given the turn.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent

ATTEMPTS = [
    {"n": 1, "iters": 3, "tokens": 14918, "post_pass": False,
     "why": "runner broke on first PASS; the agent never got the write-up turn"},
    {"n": 2, "iters": 4, "tokens": 20873, "post_pass": True,
     "why": "post-pass turn given, agent re-ran the scenario instead of recording"},
    {"n": 3, "iters": 3, "tokens": 23958, "post_pass": True,
     "why": "toolbox narrowed to record_experience+read_file; agent tried "
            "read_telemetry (denied) and recorded nothing"},
]


def main():
    run = HERE / "run1"
    r = json.loads((run / "result.json").read_text())
    v = r["verdict"]
    # the repair itself succeeded every time - the gap is only the write-up
    assert v["target"]["status"] == "PASS", v["target"]
    assert v["regression_normal"]["status"] == "PASS"
    assert v["regression_regrasp"]["status"] == "PASS"
    # no agent-authored record exists anywhere in the run
    assert not (run / "agent_authored.json").exists(), "a record appeared; re-read"
    calls = []
    for line in (run / "events.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("kind") == "transcript":
            for x in (row.get("results") or []):
                if x.get("tool") == "record_experience":
                    calls.append(x)
    assert calls == [], calls
    print(json.dumps({
        "verdict": "P2_AGENT_DID_NOT_AUTHOR_ITS_OWN_EXPERIENCE",
        "repair_succeeded": True,
        "record_experience_calls": len(calls),
        "attempts": ATTEMPTS,
        "item_2_status": "NOT_ACHIEVED",
        "item_3_status": "achieved separately in p2_reuse_budget_20261110",
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
