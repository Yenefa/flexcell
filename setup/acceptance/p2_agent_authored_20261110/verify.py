#!/usr/bin/env python3
"""P2 item (2): can the agent author its OWN experience record? Four attempts, none did.

Asserts the NEGATIVE result and the attempt log, so this cannot later be read as a
success. Attempt 1 is excluded from the behavioural claim on purpose: the runner
used to break the instant the gates passed, so the agent never got the turn.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent

ATTEMPTS = [
    {"n": 1, "iters": 3, "tokens": 14918, "framing": "no write-up turn",
     "why": "harness bug: runner broke on first PASS, agent never got the turn"},
    {"n": 2, "iters": 4, "tokens": 20873, "framing": "post-pass turn",
     "why": "agent re-ran the scenario instead of recording"},
    {"n": 3, "itess": None, "iters": 3, "tokens": 23958,
     "framing": "post-pass + toolbox narrowed",
     "why": "agent tried read_telemetry (denied); recorded nothing"},
    {"n": 4, "iters": 4, "tokens": 44488,
     "framing": "record declared a DELIVERABLE + 3 retry turns",
     "why": "all three retries ended with the agent trying DISALLOWED tools "
            "(run_execution, run_checks, list_dir, read_file) and never calling "
            "record_experience"},
]


def main():
    run = HERE / "run1"
    r = json.loads((run / "result.json").read_text())
    v = r["verdict"]
    # the repair succeeded every time - the gap is only the write-up
    assert v["target"]["status"] == "PASS", v["target"]
    assert v["regression_normal"]["status"] == "PASS"
    assert v["regression_regrasp"]["status"] == "PASS"
    assert not (run / "agent_authored.json").exists(), "a record appeared; re-read"
    calls = []
    post = []
    for line in (run / "events.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("kind") == "post_pass":
            post.append(row)
        if row.get("kind") == "transcript":
            for x in (row.get("results") or []):
                if x.get("tool") == "record_experience":
                    calls.append(x)
    assert calls == [], calls
    # attempt 4 really did retry and really did exhaust
    assert any(str(p.get("attempt")) == "exhausted" for p in post), post
    denied = sum(1 for line in (run / "events.jsonl").read_text().splitlines()
                 if line.strip() and
                 "ToolPermissionError" in str(json.loads(line)))
    print(json.dumps({
        "verdict": "P2_AGENT_DID_NOT_AUTHOR_ITS_OWN_EXPERIENCE",
        "repair_succeeded": True,
        "record_experience_calls": len(calls),
        "attempts": len(ATTEMPTS),
        "retry_turns_taken": len(post),
        "item_2_status": "NOT_ACHIEVED",
        "item_3_status": "achieved in p2_reuse_budget_20261110",
        "attempts_detail": ATTEMPTS,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
