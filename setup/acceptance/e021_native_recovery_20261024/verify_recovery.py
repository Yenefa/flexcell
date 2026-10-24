#!/usr/bin/env python3
"""Independently re-verify the recovered E-021 native episodes.

Standard library only. No ROS, no pytest, no network, no model service. Every
path is resolved relative to this file, so a fresh checkout needs nothing but
this directory and its two neighbours (the frozen inventory and the archived
batches) to reproduce the result.

    python3 setup/acceptance/e021_native_recovery_20261024/verify_recovery.py

Exit codes: 0 = every claim in recovery_manifest.json verified and the recovered
reference set equals the frozen inventory's; 1 = a mismatch; 2 = input error.

What this script does NOT establish: that the episodes ran, that the reported
outcomes are physically correct, or that the model decisions were faithful.
Those need model replay and physical acceptance, which are separate statuses.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE
FROZEN = HERE.parent / "fixed_smoke_window_20261024"
TAU_SWEEP = HERE.parent / "tau_sweep_desktop_20261005"
MANIFEST = HERE / "recovery_manifest.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="print a machine-readable report")
    args = parser.parse_args()

    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - input error path
        print(f"input error: cannot read manifest: {exc}", file=sys.stderr)
        return 2

    problems: list[str] = []
    checks: dict[str, object] = {}

    # 1. Batch bytes already archived under tau_sweep must still match.
    batch_report = {}
    for name, entry in manifest["batches"].items():
        path = TAU_SWEEP / name
        if not path.is_file():
            problems.append(f"archived batch not found: {name}")
            batch_report[name] = {"present": False}
            continue
        digest = sha256_file(path)
        good = digest == entry["sha256"]
        if not good:
            problems.append(f"archived batch sha mismatch: {name}")
        batch_report[name] = {"present": True, "sha256": digest, "matches": good}
    checks["batches"] = batch_report

    # 2. Every recovered episode byte must match the recorded digest and size.
    episode_dir = ARCHIVE / "episodes"
    on_disk = {p.name for p in episode_dir.glob("*.json")} if episode_dir.is_dir() else set()
    expected_files = {
        Path(v["archive"]).name: v
        for v in manifest["episodes"].values()
        if v.get("status") == "PRESENT"
    }
    bad_digest, bad_size, malformed = [], [], []
    provenance = {"steps": 0, "routed": 0, "trace_less": 0, "fast": 0, "fast_with_digest": 0, "paid": 0}
    for name, entry in expected_files.items():
        path = episode_dir / name
        if not path.is_file():
            problems.append(f"episode missing from archive: {name}")
            continue
        if path.stat().st_size != entry["size_bytes"]:
            bad_size.append(name)
        if sha256_file(path) != entry["sha256"]:
            bad_digest.append(name)
            continue
        # Cheap provenance tally: who decided, and does each fast proposal name
        # its weights? Interpretation lives in decision_audit.py.
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            malformed.append(name)
            continue
        for step in doc.get("steps") or []:
            provenance["steps"] += 1
            trace = (step.get("policy_output") or {}).get("policy_trace")
            if not isinstance(trace, dict):
                provenance["trace_less"] += 1
                continue
            provenance["routed"] += 1
            for proposal in trace.get("proposals") or []:
                kind = proposal.get("policy")
                inner = proposal.get("policy_trace") or {}
                if kind == "jev":
                    provenance["fast"] += 1
                    if inner.get("model_sha256"):
                        provenance["fast_with_digest"] += 1
                elif kind == "llm":
                    provenance["paid"] += 1
    if malformed:
        problems.append(f"{len(malformed)} episodes are not valid JSON")
    extra = sorted(on_disk - set(expected_files))
    absent = sorted(set(expected_files) - on_disk)
    if bad_digest:
        problems.append(f"{len(bad_digest)} episode sha mismatches")
    if bad_size:
        problems.append(f"{len(bad_size)} episode size mismatches")
    if extra:
        problems.append(f"{len(extra)} unlisted files in episodes/")
    if absent:
        problems.append(f"{len(absent)} listed episodes absent")
    checks["episodes"] = {
        "listed_present": len(expected_files),
        "on_disk": len(on_disk),
        "sha_mismatch": len(bad_digest),
        "size_mismatch": len(bad_size),
        "unlisted": extra[:5],
        "absent": absent[:5],
    }

    # 3. Recompute batch summaries from the archived bytes, then compare with the
    #    frozen inventory. This is the summary-recompute tier, nothing higher.
    summary = {}
    frozen_refs: set[str] = set()
    try:
        inventory = json.loads((FROZEN / "historical_inventory.json").read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - input error path
        print(f"input error: cannot read frozen inventory: {exc}", file=sys.stderr)
        return 2

    for name in manifest["batches"]:
        path = TAU_SWEEP / name
        if not path.is_file():
            continue
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        outcomes: dict[str, int] = {}
        dual_object = 0
        for row in rows:
            outcome = row.get("outcome") or row.get("status") or "UNKNOWN"
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
            text = json.dumps(row.get("client_output") or {}, ensure_ascii=False)
            if "object_a" in text and "object_b" in text:
                dual_object += 1
        for item in inventory[name]["inventory"]:
            frozen_refs.add(item["original"])
        expect = inventory[name]
        agrees = (len(rows) == expect["rows"] and outcomes == expect["outcomes"]
                  and dual_object == expect["dual_object_result_fields"])
        if not agrees:
            problems.append(f"summary recompute disagrees with frozen inventory: {name}")
        summary[name] = {
            "rows": len(rows),
            "outcomes": outcomes,
            "dual_object_rows": dual_object,
            "agrees_with_frozen_inventory": agrees,
        }
    checks["summary_recompute"] = summary

    # 4. The recovered reference set must be exactly the frozen reference set.
    recovered_refs = {k for k, v in manifest["episodes"].items() if v.get("status") == "PRESENT"}
    same_set = recovered_refs == frozen_refs
    if not same_set:
        problems.append("recovered reference set differs from frozen inventory")
    checks["reference_set"] = {
        "frozen": len(frozen_refs),
        "recovered": len(recovered_refs),
        "identical": same_set,
    }

    # 5. Report what the recovered bytes can and cannot support.
    present = [v for v in manifest["episodes"].values() if v.get("status") == "PRESENT"]
    if provenance["fast"] == 0:
        source_tier = "NOT_RUN"
    elif provenance["fast_with_digest"] == provenance["fast"]:
        source_tier = "PASS"
    else:
        source_tier = "PARTIAL"
    checks["evidence_tiers"] = {
        "byte_recovery": "PASS" if not problems else "REVIEW",
        "summary_recompute": "PASS" if not problems else "REVIEW",
        "model_source_audit": source_tier,
        "model_replay": "NOT_RUN",
        "physical_acceptance": "NOT_RUN",
    }
    checks["provenance_tally"] = provenance
    checks["replay_limits"] = {
        "initial_world_state_present": sum(1 for v in present if v.get("initial_world_state_recorded")),
        "note": (
            "No recovered episode records initial_world_state, so physics cannot be "
            "re-executed from this archive. Recorded observations, goals, policy "
            "configuration and FSM traces support offline decision replay only."
        ),
    }

    passed = not problems
    if args.json:
        print(json.dumps({"verified": passed, "problems": problems, "checks": checks}, indent=2, ensure_ascii=False))
    else:
        print("recovery verification — e021_native_recovery_20261024")
        print(f"  batches archived      : {sum(1 for v in batch_report.values() if v.get('matches'))}/{len(batch_report)} byte-identical")
        matched = len(expected_files) - len(set(bad_digest) | set(bad_size) | set(absent))
        print(f"  episodes verified     : {matched}/{len(expected_files)} sha+size match ({len(on_disk)} files on disk)")
        print(f"  reference set         : {len(recovered_refs)} recovered vs {len(frozen_refs)} frozen -> {'identical' if same_set else 'DIFFERS'}")
        for name, info in summary.items():
            print(f"  summary {name}: {info['outcomes']} dual_object_rows={info['dual_object_rows']} agrees={info['agrees_with_frozen_inventory']}")
        tiers = checks["evidence_tiers"]
        print("  evidence tiers        : " + ", ".join(f"{k}={v}" for k, v in tiers.items()))
        prov = checks["provenance_tally"]
        print(f"  provenance tally      : {prov['routed']} routed of {prov['steps']} steps, "
              f"{prov['fast']} fast proposals ({prov['fast_with_digest']} with weight digest), {prov['paid']} paid")
        print(f"  initial_world_state   : {checks['replay_limits']['initial_world_state_present']}/{len(present)} episodes record it")
        if problems:
            print("\nPROBLEMS")
            for p in problems:
                print(f"  - {p}")
        print(f"\nVERDICT: {'VERIFIED' if passed else 'FAILED'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
