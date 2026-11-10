#!/usr/bin/env python3
"""Verify held-out isolation is ENFORCED, by testing it rather than describing it."""
import json
import subprocess
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
PUB = WT / "benchmark" / "held_out" / "public"


def main():
    files = sorted(PUB.glob("*.json"))
    assert len(files) >= 36, len(files)
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        for banned in ("expected_goal", "constraints", "template_id", "random_seed"):
            assert banned not in d, (f.name, banned)
        assert d["task_id"].startswith("HO-"), f.name

    # unprivileged uid must not be able to read the sealed answers
    probe = subprocess.run(
        ["sudo", "-n", "setpriv", "--reuid=1001", "--regid=1001", "--clear-groups",
         "sh", "-c", "cat /etc/evobot/sealed/*.json >/dev/null 2>&1"],
        capture_output=True, text=True)
    assert probe.returncode != 0, "sealed answers were readable by the agent uid"

    # the privileged side must still be able to grade
    count = subprocess.run(["sudo", "-n", "sh", "-c",
                            "ls /etc/evobot/sealed/*.json | wc -l"],
                           capture_output=True, text=True)
    assert int(count.stdout.strip()) >= 36

    print(json.dumps({
        "verdict": "EVOBOT_HELDOUT_ISOLATION_ENFORCED",
        "public_tasks": len(files),
        "public_tasks_with_answers": 0,
        "agent_uid_read_blocked": True,
        "sealed_answers": int(count.stdout.strip()),
        "isolation_kind": "OS permissions; not a kernel namespace",
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
