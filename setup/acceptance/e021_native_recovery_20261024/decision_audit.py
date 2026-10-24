#!/usr/bin/env python3
"""Recompute per-decision provenance from the recovered E-021 native episodes.

E-021 stated that every model decision in the archived summaries passed the
routing provenance audit, and that this rested on the runner's own summary
JSONL. Each recovered hybrid episode now carries a per-decision ``policy_trace``
with the candidate proposals, so the claim can be recomputed from native
records instead of trusted.

The audit reports, per arm: which component made each decision, which model
weights and calibration produced the fast proposals, whether every fast
proposal cleared its gate, what the escalations were for, and what the paid arm
cost status was. Anything that contradicts a homogeneous single-fingerprint
deployment is reported as a problem.

    python3 setup/acceptance/e021_native_recovery_20261024/decision_audit.py [--json]

Exit 0 = consistent, 1 = inconsistency found, 2 = input error.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "recovery_manifest.json"

MODEL_SOURCES = ("jev", "llm")


def new_arm() -> dict:
    return {
        "policy": Counter(),
        "episodes": 0,
        "steps": 0,
        "sources": Counter(),
        "escalation_reasons": Counter(),
        "trace_less": 0,
        "fast": {
            "proposals": 0,
            "models": Counter(),
            "model_sha256": Counter(),
            "backends": Counter(),
            "gate_failed": 0,
            "gate_reasons": Counter(),
            "tokens": 0,
            "calibrated": 0,
            "missing_digest": 0,
        },
        "slow": {
            "proposals": 0,
            "backends": Counter(),
            "settled": Counter(),
            "completion_tokens": 0,
            "latency_ms": 0.0,
            "missing_digest": 0,
        },
        "calibration_sha256": Counter(),
        "thresholds": Counter(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit the full audit as JSON")
    args = parser.parse_args()

    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"input error: {exc}", file=sys.stderr)
        return 2

    arms: dict[str, dict] = {}
    problems: list[str] = []
    limitations: list[str] = []

    for info in manifest["episodes"].values():
        if info.get("status") != "PRESENT":
            continue
        batch = info["referenced_by_batches"][0]
        arm = arms.setdefault(batch, new_arm())
        doc = json.loads((HERE / info["archive"]).read_text(encoding="utf-8"))
        policy_id = f"{doc['policy']['name']}/{doc['policy']['version']}"
        arm["policy"][policy_id] += 1
        arm["episodes"] += 1

        for step in doc.get("steps") or []:
            arm["steps"] += 1
            out = step.get("policy_output") or {}
            trace = out.get("policy_trace")
            if not isinstance(trace, dict):
                arm["trace_less"] += 1
                continue
            source = trace.get("source") or "unknown"
            arm["sources"][source] += 1
            if trace.get("threshold") is not None:
                arm["thresholds"][round(float(trace["threshold"]), 4)] += 1
            if trace.get("calibration_sha256"):
                arm["calibration_sha256"][trace["calibration_sha256"]] += 1
            if trace.get("escalated"):
                arm["escalation_reasons"][trace.get("escalation_reason") or "unspecified"] += 1

            for proposal in trace.get("proposals") or []:
                ptrace = proposal.get("policy_trace") or {}
                kind = proposal.get("policy")
                if kind == "jev":
                    fast = arm["fast"]
                    fast["proposals"] += 1
                    fast["models"][ptrace.get("model") or "?"] += 1
                    if ptrace.get("model_sha256"):
                        fast["model_sha256"][ptrace["model_sha256"]] += 1
                    else:
                        fast["missing_digest"] += 1
                    fast["backends"][ptrace.get("backend") or "?"] += 1
                    if ptrace.get("confidence_calibrated"):
                        fast["calibrated"] += 1
                    fast["tokens"] += int(ptrace.get("tokens") or 0)
                    if not proposal.get("gate_ok", False):
                        fast["gate_failed"] += 1
                        fast["gate_reasons"][proposal.get("gate_reason") or "unspecified"] += 1
                elif kind == "llm":
                    slow = arm["slow"]
                    slow["proposals"] += 1
                    slow["backends"][ptrace.get("backend") or "?"] += 1
                    cost = ptrace.get("cost") or {}
                    slow["settled"][cost.get("status") or "no_cost_block"] += 1
                    slow["completion_tokens"] += int(ptrace.get("completion_tokens") or 0)
                    slow["latency_ms"] += float(ptrace.get("backend_latency_ms") or 0.0)
                    if not ptrace.get("model_sha256"):
                        slow["missing_digest"] += 1

    for batch, arm in arms.items():
        pure_fsm = set(arm["policy"]) == {"fsm/1.0"}
        if pure_fsm and (arm["sources"] or arm["fast"]["proposals"] or arm["slow"]["proposals"]):
            problems.append(f"{batch}: pure-FSM arm contains routed model decisions")
        if not pure_fsm and arm["trace_less"]:
            problems.append(f"{batch}: {arm['trace_less']} routed steps have no policy_trace")
        if len(arm["policy"]) > 1:
            problems.append(f"{batch}: mixed policy identities {dict(arm['policy'])}")
        if len(arm["fast"]["model_sha256"]) > 1:
            problems.append(f"{batch}: multiple fast-arm weight digests {dict(arm['fast']['model_sha256'])}")
        if len(arm["calibration_sha256"]) > 1:
            problems.append(f"{batch}: multiple calibration identities")
        if arm["fast"]["missing_digest"]:
            problems.append(f"{batch}: {arm['fast']['missing_digest']} fast proposals lack a weight digest")
        if arm["fast"]["gate_failed"]:
            problems.append(f"{batch}: {arm['fast']['gate_failed']} fast proposals failed their gate")
        # Remote backends do not publish weights, so their provenance stops at
        # call id + cost settlement. That is a documented limit, not a defect.
        if arm["slow"]["proposals"] and arm["slow"]["missing_digest"] == arm["slow"]["proposals"]:
            limitations.append(
                f"{batch}: {arm['slow']['proposals']} paid proposals carry no weight digest — "
                "remote-backend weight identity is not auditable from this archive"
            )

    report = {
        "archive": "setup/acceptance/e021_native_recovery_20261024/",
        "source": "recomputed from recovered native episodes, not from batch summaries",
        "method": (
            "Every step's policy_output.policy_trace is walked. Candidate proposals are "
            "split into the fast arm (policy=jev, local weights) and the paid arm "
            "(policy=llm, remote backend). Gate outcomes, escalation reasons, weight "
            "and calibration digests and token counts are tallied per batch."
        ),
        "arms": {},
        "problems": problems,
        "limitations": limitations,
    }
    for batch, arm in arms.items():
        report["arms"][batch] = {
            "episodes": arm["episodes"],
            "policy": dict(arm["policy"]),
            "steps": arm["steps"],
            "decisions_by_source": dict(arm["sources"]),
            "trace_less_steps": arm["trace_less"],
            "escalation_reasons": dict(arm["escalation_reasons"]),
            "calibration_sha256": dict(arm["calibration_sha256"]),
            "thresholds": {str(k): v for k, v in sorted(arm["thresholds"].items())},
            "fast_arm": {
                "proposals": arm["fast"]["proposals"],
                "models": dict(arm["fast"]["models"]),
                "model_sha256": dict(arm["fast"]["model_sha256"]),
                "backends": dict(arm["fast"]["backends"]),
                "gate_failed": arm["fast"]["gate_failed"],
                "gate_reasons": dict(arm["fast"]["gate_reasons"]),
                "calibrated_proposals": arm["fast"]["calibrated"],
                "tokens": arm["fast"]["tokens"],
            },
            "paid_arm": {
                "proposals": arm["slow"]["proposals"],
                "backends": dict(arm["slow"]["backends"]),
                "cost_status": dict(arm["slow"]["settled"]),
                "completion_tokens": arm["slow"]["completion_tokens"],
                "mean_latency_ms": round(arm["slow"]["latency_ms"] / arm["slow"]["proposals"], 1)
                if arm["slow"]["proposals"]
                else 0.0,
            },
        }

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if not problems else 1

    print("per-decision provenance audit — recomputed from native episodes")
    for batch, arm in report["arms"].items():
        print(f"\n{batch}")
        print(f"  policy / episodes : {arm['policy']}  episodes={arm['episodes']} steps={arm['steps']}")
        if arm["trace_less_steps"] == arm["steps"]:
            print("  routing           : no policy_trace by design (pure FSM arm)")
            continue
        print(f"  decisions         : {arm['decisions_by_source']}")
        print(f"  escalation reasons: {arm['escalation_reasons']}")
        print(f"  thresholds        : {arm['thresholds']}")
        fast = arm["fast_arm"]
        print(f"  fast arm          : {fast['proposals']} proposals, models={fast['models']}, backends={fast['backends']}")
        if fast["model_sha256"]:
            for digest, count in fast["model_sha256"].items():
                print(f"    weight sha256   : {digest}  ({count} proposals)")
        print(f"    gate failures   : {fast['gate_failed']}  calibrated={fast['calibrated_proposals']}/{fast['proposals']}  tokens={fast['tokens']}")
        paid = arm["paid_arm"]
        print(f"  paid arm          : {paid['proposals']} proposals, backends={paid['backends']}")
        print(f"    cost status     : {paid['cost_status']}")
        print(f"    completion tok  : {paid['completion_tokens']}  mean latency {paid['mean_latency_ms']} ms")
        for digest in arm["calibration_sha256"]:
            print(f"  calibration sha256: {digest}")

    if problems:
        print("\nPROBLEMS")
        for p in problems:
            print(f"  - {p}")
    if limitations:
        print("\nLIMITATIONS (not defects)")
        for item in limitations:
            print(f"  - {item}")
    print(f"\nVERDICT: {'CONSISTENT' if not problems else 'INCONSISTENT'}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
