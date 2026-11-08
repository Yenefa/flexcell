#!/usr/bin/env python3
"""B1-A: logic-level replay of the hybrid router over the archived E-021 episodes.

This re-derives the routing decision from the recorded proposal confidences and
threshold using the CURRENT HybridRouter rule, then compares it with what the
trace says was selected. It does NOT replay the models: the original local
weights (clef-flash-q8_0) and the paid endpoint are not available, so model
replay stays BLOCKED (see docs/B1_E021_FOLLOWUP_PROTOCOL.md).

Exit 0 means every recorded decision is explained by the current rule.
"""
import json
import sys
from collections import Counter
from pathlib import Path

EPISODES = Path(__file__).resolve().parent.parent / "e021_native_recovery_20261024" / "episodes"


def expected_source(trace):
    props = trace.get("proposals") or []
    threshold = float(trace.get("threshold"))
    require_cal = bool(trace.get("fast_calibration_required", True))
    fast = None
    slow = None
    for p in props:
        if p.get("skipped"):
            continue
        pt = p.get("policy_trace") or {}
        name = pt.get("source") or p.get("policy")
        if fast is None and name == "jev":
            fast = p
        elif slow is None and name == "llm":
            slow = p
    if fast is not None and not fast.get("fallback") and fast.get("gate_ok"):
        calibrated = bool((fast.get("policy_trace") or {}).get("confidence_calibrated"))
        if float(fast["confidence"]) >= threshold and (calibrated or not require_cal):
            return "jev", False
    if slow is not None and not slow.get("fallback") and slow.get("gate_ok"):
        return "llm", True
    return "fsm", trace.get("failure") != "bootstrap"


def main():
    files = sorted(EPISODES.glob("*.json"))
    if len(files) != 60:
        print("expected 60 episodes, found", len(files))
        return 2
    total = matched = 0
    mismatches = []
    sources = Counter()
    fast_props = paid_props = 0
    for path in files:
        doc = json.loads(path.read_text(encoding="utf-8"))
        for step in doc.get("steps", []):
            trace = (step.get("policy_output") or {}).get("policy_trace") or {}
            recorded = trace.get("source")
            if recorded is None:
                continue
            total += 1
            sources[recorded] += 1
            fast_props += sum(1 for p in trace.get("proposals") or []
                              if (p.get("policy_trace") or {}).get("source") == "jev")
            paid_props += sum(1 for p in trace.get("proposals") or []
                              if (p.get("policy_trace") or {}).get("source") == "llm")
            want, want_escalated = expected_source(trace)
            if want == recorded:
                matched += 1
            else:
                mismatches.append({"episode": path.name, "seq": step.get("seq"),
                                   "recorded": recorded, "expected": want,
                                   "threshold": trace.get("threshold"),
                                   "proposals": len(trace.get("proposals") or [])})
            escalated = bool(trace.get("escalated"))
            if want_escalated != escalated and recorded in ("llm", "fsm"):
                mismatches.append({"episode": path.name, "seq": step.get("seq"),
                                   "kind": "escalated_flag", "recorded": recorded})
    summary = {"episodes": len(files), "decisions": total, "matched": matched,
               "mismatched": len(mismatches), "by_source": dict(sources),
               "fast_proposals": fast_props, "paid_proposals": paid_props,
               "mismatches": mismatches[:20]}
    out = Path(__file__).parent / "router_replay.json"
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
