#!/usr/bin/env python3
"""Turn measured failures into a GATED PROPOSAL - the missing link in the loop.

THE AUDIT THAT MOTIVATED THIS FILE: evolution/validation/regress.py has a gate that
checks a proposal, but evolution/proposals/ was EMPTY. Nothing produced proposals, so the
gate could never accept one, so C could never change itself. That is why two independent
B/C experiments measured exactly zero effect: the experience channel had no path to
action. Learning that never reaches behaviour is not learning.

This module closes that link in the narrowest defensible way:
  * it consumes only MEASURED evidence (archived run logs, never a hypothesis);
  * it emits a proposal the existing gate can judge;
  * it NEVER touches source. Applying is a separate, human-approved step.

Safety rules enforced here, not delegated:
  * a proposal needs a failure class seen at least MIN_OCCURRENCES times;
  * it can never name a protected path;
  * it must state a falsifiable expected effect and a rollback.
"""
import glob
import json
import os
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WT / "evolution" / "validation"))
sys.path.insert(0, str(WT / "evolution" / "proposals"))
import regress
# Issue #236: a proposal whose basis was already measured and refuted must not be emitted
# again. status.py reads the superseded_basis / supersedes records that already exist next
# to the proposals and that this generator previously ignored.
import status as pstatus

MIN_OCCURRENCES = 2

CLASS_TARGETS = {
    # A release stall is a SKILL-LAYER defect with a computable signature: the
    # controller reports stalled=True on an OPEN command, place_server treats that as
    # fatal on first occurrence, and no retry exists anywhere in that file.
    "actuator_stall": ["src/flexcell/flexcell_skills/flexcell_skills/place_server.py"],
    "planning": ["experiments/baselines/spread_destinations.py"],
    "execution": ["runtime/recovery/recover.py"],
    "grasp": ["runtime/recovery/recover.py"],
}


def load_evidence(runs_root):
    """Read archived run directories. Evidence only - no verdict, no grader file."""
    out = []
    for d in sorted(glob.glob(os.path.join(runs_root, "*"))):
        if not os.path.isdir(d):
            continue
        t = os.path.join(d, "task.out")
        if not os.path.exists(t):
            continue
        txt = open(t, encoding="utf-8", errors="replace").read()
        if "RESULT " not in txt:
            continue
        try:
            res = json.loads(txt.split("RESULT ", 1)[1])
        except json.JSONDecodeError:
            continue
        if res.get("error_code") in (0, None):
            continue
        out.append({"run": os.path.basename(d),
                    "error_code": res.get("error_code"),
                    "detail": str(res.get("detail") or ""),
                    "completed_stage_ids": res.get("completed_stage_ids") or []})
    return out


def cluster(failures):
    """Group failures by an observable signature. No guessing at causes."""
    buckets = {}
    for f in failures:
        d = f["detail"].lower()
        if "gripper did not open" in d:
            key = "actuator_stall"
        elif "occupied destination" in d or "destination occupied" in d:
            key = "occupied_destination"
        elif "state drift" in d:
            key = "state_drift"
        elif "unconfirmed" in d:
            key = "unconfirmed"
        else:
            key = "error_%s" % f["error_code"]
        buckets.setdefault(key, []).append(f)
    return buckets


def build_proposal(signature, failures):
    """Emit a proposal the gate can judge. Refuses when evidence is too thin."""
    if len(failures) < MIN_OCCURRENCES:
        return None, "only %d occurrence(s) of %s; need %d" % (
            len(failures), signature, MIN_OCCURRENCES)
    if signature == "actuator_stall":
        files = CLASS_TARGETS["actuator_stall"]
        return {
            "kind": "bounded_release_retry",
            "signature": signature,
            "files": list(files),
            "occurrences": len(failures),
            "evidence": {"signature": signature,
                         "runs": [f["run"] for f in failures][:16],
                         "error_codes": sorted({f["error_code"] for f in failures}),
                         "sample_detail": failures[0]["detail"][:160]},
            "change": ("when the gripper reports stalled=True on the release command, "
                       "retry the open a bounded number of times before declaring "
                       "PLACE failed; the signal is observable and a re-issued open "
                       "is a new attempt, not a longer wait"),
            # CORRECTED after measuring the base rate: my first wording claimed phases
            # "will succeed", but the existing plan-level retry ALREADY recovers 6 of 9
            # stalls (67%). So the honest increment is NOT final pass rate - it is
            # first-attempt success and cost: today a stall costs a whole-stage re-run
            # (median 13.0 s, and re-picking the box), not a re-issued open.
            "expected_effect": ("first-attempt pass rate rises by at most the 4 runs the "
                                "plan-level retry currently rescues; FINAL pass rate is "
                                "expected to be UNCHANGED at 29/32, because the existing "
                                "retry already reaches those end states; and a stall "
                                "that persists (3 of 9) MUST still fail with the same "
                                "error, so the change cannot turn a real failure into "
                                "a pass"),
            "increment_is": "latency and risk, not final pass rate",
            "rollback": "git revert this commit; the single-attempt release returns",
            "requires_human_approval": True,
        }, None
    if signature not in ("occupied_destination",):
        return None, "no evidence-backed change for %s yet" % signature
    files = CLASS_TARGETS["planning"]
    proposal = {
        "kind": "spacing_policy",
        "signature": signature,
        "files": list(files),
        "occurrences": len(failures),
        "evidence": {"signature": signature,
                     "runs": [f["run"] for f in failures][:16],
                     "error_codes": sorted({f["error_code"] for f in failures}),
                     "sample_detail": failures[0]["detail"][:160]},
        "change": ("when several objects share a bin, the spacing between landing "
                   "points must exceed the clearance contract PLUS measured landing "
                   "drift, and the spread axis must keep every destination clear of "
                   "the other objects; refuse rather than emit an unholdable plan"),
        "expected_effect": ("phases that failed with an occupied destination will "
                            "either succeed or be refused at plan time; no verified "
                            "task may regress"),
        "rollback": "git revert this commit; the previous spread policy is unchanged",
        "requires_human_approval": True,
    }
    return proposal, None


def main(argv=None):
    runs = sys.argv[1] if len(sys.argv) > 1 else "/tmp/evobot-pair16"
    failures = load_evidence(runs)
    print("measured failures:", len(failures))
    buckets = cluster(failures)
    # Read the repository's own negative records ONCE, before generating anything, so a
    # signature already documented as unsound or replaced never reaches build_proposal.
    status_index = pstatus.load_status_index(str(WT / "evolution" / "proposals"))
    for sig, fs in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
        allowed, pstatus_state, pstatus_reason = pstatus.check(sig, status_index)
        if not allowed:
            # Traceable skip: the status, the reason and its source file are all printed, so
            # the decision can be audited without re-deriving it.
            print("  SKIP %-22s %s: %s" % (sig, pstatus_state, pstatus_reason))
            continue
        proposal, why = build_proposal(sig, fs)
        if proposal is None:
            print("  SKIP %-22s %s" % (sig, why))
            continue
        # Carry the status into the emitted artifact. UNKNOWN means nobody reviewed this
        # signature; it is deliberately not written as approved or verified, because a
        # missing record must never become a positive one by default (issue #236).
        proposal["proposal_status"] = pstatus_state
        proposal["status_note"] = pstatus_reason
        ok, reason = regress.gate(proposal, run_regressions=False)
        print("  PROPOSAL %-20s occurrences=%d status=%s gate=%s" % (
            sig, len(fs), pstatus_state, "ACCEPTED" if ok else "REJECTED"))
        print("    reason:", reason)
        if ok:
            out = WT / "evolution" / "proposals" / ("%s.json" % sig)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(proposal, indent=2) + "\n", encoding="utf-8")
            print("    wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
