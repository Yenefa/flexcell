#!/usr/bin/env python3
"""Regression gate for a self-evolution proposal.

A proposal may change the PLANNER only. Before it can be accepted, every previously
PASSING verifier under setup/acceptance/ must still pass. Anything that touches an
evaluator, a schema used for grading, a tolerance, or held-out answers is refused
without even running the regressions - no evidence can justify that change.

This is the guard that makes Baseline C different from "let the agent edit code":
the agent may propose, but the gate decides, using independent verifiers.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ACCEPTANCE = ROOT / "setup" / "acceptance"
PROTECTED = ["benchmark/evaluators/", "benchmark/schemas/",
             "benchmark/tests/test_benchmark_skeleton.py",
             "docs/EVALUATION_METRICS.md", "/etc/evobot/sealed/"]


def is_protected(path):
    norm = str(path).replace("\\", "/")
    return any(p.replace("\\", "/") in norm for p in PROTECTED)


def gate(proposal, run_regressions=True):
    """Return (accepted, reason). Never modifies anything itself."""
    files = proposal.get("files") or []
    if not files:
        return False, "proposal changes no files"
    for f in files:
        if is_protected(f):
            return False, "proposal touches protected path: " + str(f)
    if not proposal.get("evidence"):
        return False, "proposal has no measured failure evidence"
    if not proposal.get("expected_effect"):
        return False, "proposal states no falsifiable expected effect"
    if not proposal.get("rollback"):
        return False, "proposal states no rollback"
    digest = hashlib.sha256(json.dumps(proposal, sort_keys=True).encode()).hexdigest()[:12]
    if not run_regressions:
        return True, "structure accepted (regressions skipped by caller), id=" + digest

    verifiers = sorted(ACCEPTANCE.glob("*/verify.py"))
    failed = []
    for v in verifiers:
        proc = subprocess.run([sys.executable, str(v)], capture_output=True,
                              text=True, timeout=180, cwd=str(v.parent))
        if proc.returncode != 0:
            failed.append(v.parent.name + ": " + (proc.stderr or proc.stdout or "").strip()[-120:])
    if failed:
        return False, "regression failed (%d/%d): %s" % (
            len(failed), len(verifiers), "; ".join(failed[:3]))
    return True, "all %d verifiers still pass, id=%s" % (len(verifiers), digest)


if __name__ == "__main__":
    p = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    ok, why = gate(p)
    print(json.dumps({"accepted": ok, "reason": why}, indent=2))
    sys.exit(0 if ok else 1)
