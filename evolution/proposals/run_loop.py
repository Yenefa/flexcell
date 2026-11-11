#!/usr/bin/env python3
"""Run the proposal generator against EVERY archived batch, then gate the result.

This is the loop end to end: measured failures -> clustered signature -> proposal ->
existing regression gate. Applying remains a separate human-approved step.
"""
import glob
import json
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "proposals"))
sys.path.insert(0, os.path.join(WT, "evolution", "validation"))
import generate
import regress
import gate_differential

# The actuator stall is ONLY visible in the episode records: task*.out carries the
# policy wrapper ("native terminal/verification unconfirmed"), never "gripper did not
# open". Reading only the wrapper made this class invisible to the generator - the same
# mistake that hid the root cause for several rounds.
sys.path.insert(0, os.path.join(WT, "runtime", "recovery"))
import execution_root_cause as ERC

ACC = os.path.join(WT, "setup", "acceptance")


def all_failures():
    out = []
    for t in glob.glob(os.path.join(ACC, "evobot*", "**", "task*.out"), recursive=True):
        txt = open(t, encoding="utf-8", errors="replace").read()
        if "RESULT " not in txt:
            continue
        try:
            r = json.loads(txt.split("RESULT ", 1)[1])
        except json.JSONDecodeError:
            continue
        if r.get("error_code") in (0, None):
            continue
        out.append({"run": os.path.relpath(t, ACC),
                    "error_code": r.get("error_code"),
                    "detail": str(r.get("detail") or ""),
                    "completed_stage_ids": r.get("completed_stage_ids") or []})
    # fold in executor-level evidence from episodes
    for ep in glob.glob(os.path.join(ACC, "evobot*", "**", "episodes", "*.json"),
                       recursive=True):
        for f in ERC.episode_failures(ep):
            label = ERC.classify(f["detail"])
            if label == "OTHER":
                continue
            out.append({"run": os.path.relpath(ep, ACC),
                        "error_code": f.get("error_code"),
                        "detail": f["detail"],
                        "completed_stage_ids": []})
    return out


def main():
    failures = all_failures()
    print("measured failures across all archives:", len(failures))
    buckets = generate.cluster(failures)
    written = []
    for sig, fs in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
        proposal, why = generate.build_proposal(sig, fs)
        if proposal is None:
            print("  SKIP  %-22s n=%-3d %s" % (sig, len(fs), why))
            continue
        # WAS: regress.gate(proposal, run_regressions=False) - an all-green gate rejects every
        # proposal forever while 4 verifiers fail for pre-existing reasons, so it was switched
        # off and gated nothing. This gate requires NO NEW failures instead of no failures.
        ok, reason = gate_differential.gate(proposal)
        print("  GATE  %-22s n=%-3d %s" % (sig, len(fs), "ACCEPTED" if ok else "REJECTED"))
        print("        ", reason)
        if ok:
            p = os.path.join(WT, "evolution", "proposals", sig + ".json")
            open(p, "w", encoding="utf-8").write(json.dumps(proposal, indent=2) + "\n")
            written.append(p)
            print("         wrote", p)
    print()
    print("proposals written:", len(written))
    for w in written:
        doc = json.load(open(w, encoding="utf-8"))
        print("  -", os.path.basename(w), "| occurrences:", doc["occurrences"],
              "| files:", doc["files"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
