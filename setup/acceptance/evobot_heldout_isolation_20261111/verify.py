#!/usr/bin/env python3
"""Acceptance verifier: held-out isolation is ENFORCED, and it can FAIL.

This is the machine check for setup/acceptance/evobot_heldout_isolation_20261111/.
It does not restate the claim - it drives the real enforcement through both states and
records the exit codes, so a reader can re-run it and get the same numbers.

Rungs reached (see docs/PROJECT_STATUS.md ladder):
  Designed, Implemented, Unit Tested, Independently Verified.
  NOT Generalization Tested: this is an isolation mechanism, not a benchmark result.

Run:  sudo -n python3 setup/acceptance/evobot_heldout_isolation_20261111/verify.py
      sudo -n python3 setup/acceptance/evobot_heldout_isolation_20261111/verify.py --current-state
Exit: 0 = enforced and mutation-detected, 1 = a check failed, 2 = environment problem.

WHY --current-state EXISTS (defect found by the Lead 2026-11-11)
The default mode drives the enforcement itself: it calls "apply" before checking, and "restore"
before checking the mutation. That makes it a self-test of the enforcer, which is useful, but it
also means it CANNOT report on the state of the machine. Chmod the tree to 755 by hand and run the
default mode: it silently re-applies the lock and then reports ENFORCED. The state it graded was
one it had just created, not the one it was handed. That is a false green, and it is exactly the
defect class this batch exists to remove.
--current-state checks the live filesystem without touching it: no apply, no restore. If the lock
is missing, it says so and exits non-zero.
"""
import json
import subprocess
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
ISO = WT / "scripts" / "heldout_isolation.py"
LOCKED = ("benchmark/held_out", "benchmark/evaluators", "benchmark/generators")
CONTROL = "benchmark/tasks/train"


def run(cmd, timeout=300):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def iso(action, *args):
    return run(["sudo", "-n", sys.executable, str(ISO), action] + list(args))


def verify_json():
    r = iso("verify", "--json")
    try:
        return r.returncode, json.loads(r.stdout)
    except Exception:
        return r.returncode, {"parse_error": (r.stdout or r.stderr)[-800:]}


def current_state_mode():
    """Grade the filesystem AS IT IS. Never apply, never restore."""
    import os
    import stat
    problems = []
    rows = []
    for rel in LOCKED:
        p = WT / rel
        if not p.is_dir():
            problems.append(rel + ": missing")
            continue
        st = p.stat()
        mode = stat.S_IMODE(st.st_mode)
        group_exec = bool(mode & 0o010)
        other_any = bool(mode & 0o007)
        rows.append({"path": rel, "mode": oct(mode), "uid": st.st_uid, "gid": st.st_gid,
                     "group_can_traverse": group_exec, "other_has_access": other_any})
        if other_any:
            problems.append(rel + ": world-accessible (" + oct(mode) + ")")
        if not group_exec:
            problems.append(rel + ": the evaluator group lost access (" + oct(mode) + ")")
    control = WT / CONTROL
    rows.append({"path": CONTROL, "agent_must_read": True,
                 "readable_by_other": bool(control.stat().st_mode & 0o004)
                 if control.is_dir() else None})
    verdict = ("HELDOUT_ISOLATION_ENFORCED" if not problems
               else "HELDOUT_ISOLATION_NOT_ENFORCED")
    print(json.dumps({"record_kind": "EVOBOT_HELDOUT_ISOLATION_CURRENT_STATE",
                      "checked_without_mutating": True,
                      "paths": rows,
                      "problems": problems,
                      "verdict": verdict}, indent=2))
    return 0 if not problems else 1


def main():
    if "--current-state" in sys.argv:
        return current_state_mode()
    checks = []
    record = {"record_kind": "EVOBOT_HELDOUT_ISOLATION_VERIFICATION",
              "rung": "Independently Verified (isolation mechanism only)"}

    if not ISO.is_file():
        print(json.dumps({"verdict": "MISSING_ENFORCER", "path": str(ISO)}, indent=2))
        return 2

    # ---- 1. the lock is applied and the verifier agrees ------------------------------
    iso("apply")
    rc_enforced, enforced = verify_json()
    checks.append({"check": "verify_in_enforced_state", "exit": rc_enforced,
                   "verdict": enforced.get("verdict"),
                   "ok": rc_enforced == 0
                         and enforced.get("verdict") == "HELDOUT_ISOLATION_ENFORCED"})

    # ---- 2. the agent side is denied (every locked prefix, dir and file) ------------
    agent = enforced.get("agent_blocked", [])
    checks.append({"check": "agent_denied_all_locked_prefixes",
                   "probes": len(agent),
                   "all_denied": all(c.get("ok") for c in agent) and len(agent) >= 6,
                   "ok": all(c.get("ok") for c in agent) and len(agent) >= 6})

    # ---- 3. the evaluator side still grades: BOTH a pass and a fail -----------------
    ev = enforced.get("evaluator_side", [])
    by_name = {c.get("probe"): c for c in ev}
    both = (by_name.get("evaluator:pass", {}).get("observed_passed") is True
            and by_name.get("evaluator:fail", {}).get("observed_passed") is False)
    checks.append({"check": "evaluator_still_grades_both_ways", "observed": both,
                   "detail": ev, "ok": bool(both)})

    # ---- 4. the agent still reads what it is SUPPOSED to read -----------------------
    ctrl = enforced.get("agent_control", [])
    checks.append({"check": "train_split_still_readable_by_agent",
                   "detail": ctrl, "ok": all(c.get("ok") for c in ctrl) and bool(ctrl)})

    # ---- 5. the reconstruction oracle is closed -------------------------------------
    recon = enforced.get("reconstruction", [])
    no_recovery = all(not c.get("recovered_answer") for c in recon) and bool(recon)
    checks.append({"check": "answer_reconstruction_blocked", "detail": recon,
                   "ok": no_recovery and all(c.get("ok") for c in recon)})

    # ---- 6. MUTATION: chmod back to 755, the verifier MUST exit non-zero ------------
    iso("restore")
    rc_mut, mutated = verify_json()
    checks.append({"check": "mutation_755_is_detected",
                   "exit": rc_mut,
                   "verdict": mutated.get("verdict"),
                   "ok": rc_mut != 0
                         and mutated.get("verdict") == "HELDOUT_ISOLATION_NOT_ENFORCED"})

    # ---- 7. re-apply and confirm the gate recovers ----------------------------------
    iso("apply")
    rc_back, restored = verify_json()
    checks.append({"check": "reapply_restores_gate", "exit": rc_back,
                   "verdict": restored.get("verdict"), "ok": rc_back == 0})

    # ---- 8. offline suite still green on the isolation tests ------------------------
    t = run([sys.executable, "-m", "pytest",
             str(WT / "benchmark" / "tests" / "test_heldout_isolation.py"), "-q"], 600)
    checks.append({"check": "offline_isolation_tests_pass", "exit": t.returncode,
                   "tail": t.stdout.strip().splitlines()[-1:] or [""],
                   "ok": t.returncode == 0})

    # ---- 9. residual risks are REPORTED, not smoothed over --------------------------
    risks = restored.get("residual_risks", [])
    open_risks = [r["risk"] for r in risks if not r.get("closed")]
    checks.append({"check": "residual_risks_disclosed", "open": open_risks,
                   "ok": len(open_risks) >= 2})

    ok = all(c["ok"] for c in checks)
    record["checks"] = checks
    record["residual_risks"] = risks
    record["verdict"] = ("EVOBOT_HELDOUT_ISOLATION_ENFORCED_AND_MUTATION_DETECTED"
                         if ok else "EVOBOT_HELDOUT_ISOLATION_INCOMPLETE")
    record["claim_level"] = (
        "Implemented + Unit Tested + Independently Verified by this script. "
        "OS permission isolation, not a kernel namespace. NOT a generalisation result, "
        "and NOT a claim of absolute safety: see residual_risks.")
    print(json.dumps(record, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())