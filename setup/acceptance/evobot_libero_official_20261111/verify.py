#!/usr/bin/env python3
"""Verify the first real external-benchmark integration: an OFFICIAL LIBERO task.

WHAT MAKES IT OFFICIAL: the task file is LIBERO's own BDDL, the environment is LIBERO's own env
class over robosuite, the initial state is the published .pruned_init blob, and the success flag
comes from LIBERO's own predicate. Nothing is re-implemented, translated or re-scored.

WHAT IT DOES NOT PROVE: that EvoBot controls this environment. The policy is a deliberate no-op.
The run shows the load-step-grade path works and that an idle robot is reported as failure, which
is the sanity direction. No skill claim is made from it.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLONE = Path("/mnt/c/Users/fuker/Desktop/workspace/ext-bench/LIBERO")


def main():
    meta = json.loads((HERE / "benchmark_meta.json").read_text(encoding="utf-8"))

    commit = subprocess.run(["git", "log", "-1", "--format=%H"], cwd=str(CLONE),
                            capture_output=True, text=True).stdout.strip()
    assert commit == meta["pinned_commit"], ("clone moved", commit)

    lic = (CLONE / "LICENSE").read_text(encoding="utf-8")[:40]
    assert "MIT License" in lic, lic

    import importlib.util
    tm_path = CLONE / "libero" / "libero" / "benchmark" / "libero_suite_task_map.py"
    spec = importlib.util.spec_from_file_location("tm", str(tm_path))
    tm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tm)
    counts = {k: len(v) for k, v in tm.libero_task_map.items()}
    assert counts == meta["suite_task_counts"], (counts, meta["suite_task_counts"])

    bddl = (CLONE / "libero" / "libero" / "bddl_files" / meta["task"]["suite"]
            / (meta["task"]["name"] + ".bddl")).read_text(encoding="utf-8")
    assert "(:goal" in bddl

    run = json.loads((HERE / "run_result.json").read_text(encoding="utf-8"))
    assert run["official_success_with_noop_policy"] is False
    assert run["action_dim"] == meta["action"]["dim"]
    assert "official init state loaded" in run["init_note"], run["init_note"]

    print(json.dumps({
        "verdict": "EVOBOT_EXTERNAL_BENCHMARK_OFFICIAL_LOADED_AND_STEPPED",
        "benchmark": "LIBERO",
        "classification": {"official": True, "adapted": False, "native": False},
        "pinned_commit": commit,
        "license": "MIT",
        "suites": counts,
        "task_run": meta["task"],
        "action_dim": run["action_dim"],
        "success_with_idle_policy": False,
        "proves": "official task loads in the official environment and grades with the official predicate",
        "does_not_prove": "that EvoBot controls this environment",
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
