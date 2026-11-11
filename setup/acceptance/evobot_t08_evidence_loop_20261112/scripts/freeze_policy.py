#!/usr/bin/env python3
"""Record the exact policy/driver fingerprint that arm U will be measured with.

WHY A SEPARATE FREEZE STEP
    Arm U is the first-ever unseen measurement. Its value depends entirely on the
    policy not being adjusted after seeing a U result, so the fingerprint must be
    taken BEFORE U and must be checkable afterwards. This script writes the
    digests; verify_freeze.py re-reads them after U and fails loudly on any
    difference.

WHAT IS COVERED
    Everything whose change could alter a U verdict:
      - the policy module (push_recover.py) and the frozen push contract
      - the push server that executes the goals
      - the evaluator and the three evidence modules that judge the run
      - sim_profile.py, which generates the world
      - every script in this directory that participates in a trial
      - the three task specs of the unseen arm
      - git HEAD (recorded from the Windows side; git cannot read this worktree
        from inside WSL because .git holds a Windows absolute path)
"""
import hashlib
import json
import sys
from pathlib import Path

WT = Path("/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp")
HERE = WT / "setup/acceptance/evobot_t08_evidence_loop_20261112"

COVERED = [
    WT / "src/flexcell/flexcell_skills/flexcell_skills/contracts/push_recover.py",
    WT / "src/flexcell/flexcell_skills/flexcell_skills/contracts/push.py",
    WT / "src/flexcell/flexcell_skills/flexcell_skills/push_server.py",
    WT / "benchmark/evaluators/evaluate.py",
    WT / "benchmark/evidence/recorder.py",
    WT / "benchmark/evidence/verify.py",
    WT / "benchmark/evidence/schema.py",
    Path("/home/ros/flexcell-p14/scripts/sim_profile.py"),
    HERE / "scripts/run_evidence_push.py",
    HERE / "scripts/build_trial_evidence.py",
    HERE / "scripts/inject_contact_evidence.py",
    HERE / "scripts/run_batch.sh",
    HERE / "scripts/aggregate_results.py",
    WT / "benchmark/tasks/t08_unseen/T08-push-seed3000.json",
    WT / "benchmark/tasks/t08_unseen/T08-push-seed3001.json",
    WT / "benchmark/tasks/t08_unseen/T08-push-seed3002.json",
]


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv):
    out = Path(argv[1]) if len(argv) > 1 else HERE / "evidence" / "policy_freeze.json"
    files = {}
    missing = []
    for path in COVERED:
        if not path.is_file():
            missing.append(str(path))
            continue
        files[str(path)] = sha256(path)
    head_file = HERE / "evidence" / "git_head.txt"
    payload = {
        "purpose": ("fingerprint of everything that can change a T08 verdict, "
                    "taken BEFORE arm U (first-ever unseen measurement)"),
        "git_head": (head_file.read_text(encoding="utf-8").strip()
                     if head_file.is_file() else "UNKNOWN"),
        "files": files,
        "missing": missing,
        "contact_height_m": 0.0200,
        "ceiling_guard_m": 0.140,
        "unseen_trials_per_task": 1,
        "max_attempts_closed_loop": 3,
    }
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print("freeze written to %s" % out)
    for path, digest in sorted(files.items()):
        print("  %s  %s" % (digest, path))
    if missing:
        print("MISSING: %s" % missing, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
