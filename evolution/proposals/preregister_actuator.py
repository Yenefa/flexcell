#!/usr/bin/env python3
"""PRE-REGISTER the acceptance test for the actuator retry BEFORE it is applied.

WHY: an improvement measured after the fact can always be described as a success. The only
defence is to write down, in advance and from existing evidence, exactly what will count as
support and what will count as a refutation, then apply that test unchanged.

This script writes the registered prediction and can later score a batch against it. It
does NOT apply the change and does NOT read the grader: it compares first-attempt and final
pass counts plus per-run stall persistence, all from archived evidence.
"""
import glob
import json
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REG = os.path.join(WT, "evolution", "proposals", "actuator_stall_preregistration.json")
BATCHES = ["/tmp/evobot-pair16", "/tmp/evobot-pair32"]


def stall_episodes(run_dir):
    eps = sorted(glob.glob(os.path.join(run_dir, "sim", "episodes", "*.json")),
                 key=os.path.getmtime)
    out = []
    for ep in eps:
        try:
            doc = json.load(open(ep, encoding="utf-8"))
        except Exception:
            continue
        hit = False
        for st in doc.get("steps") or []:
            det = str((st.get("executor_result") or {}).get("detail") or "")
            if "did not open" in det:
                hit = True
                break
        out.append(hit)
    return out


def baseline():
    b_pass = r_pass = n = 0
    absorbed = persistent = 0
    for base in BATCHES:
        for d in sorted(glob.glob(os.path.join(base, "HO-*"))):
            b = os.path.join(d, "verdict_after1.json")
            r = os.path.join(d, "verdict.json")
            if not (os.path.exists(b) and os.path.exists(r)):
                continue
            bd = json.load(open(b, encoding="utf-8"))
            rd = json.load(open(r, encoding="utf-8"))
            n += 1
            b_pass += 1 if bd.get("passed") else 0
            r_pass += 1 if rd.get("passed") else 0
            eps = stall_episodes(d)
            if any(eps):
                first = eps.index(True)
                if any(not s for s in eps[first:]):
                    absorbed += 1
                else:
                    persistent += 1
    return {"n": n, "b_pass": b_pass, "r_pass": r_pass,
            "stalls_absorbed": absorbed, "stalls_persistent": persistent}


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--score":
        if not os.path.exists(REG):
            print("no pre-registration on disk")
            return 1
        reg = json.load(open(REG, encoding="utf-8"))
        now = baseline()
        print("registered :", json.dumps(reg["baseline"]))
        print("measured   :", json.dumps(now))
        print("criteria   :", json.dumps(reg["success_criteria"], indent=2))
        return 0
    base = baseline()
    total_stalls = base["stalls_absorbed"] + base["stalls_persistent"]
    reg = {
        "record_kind": "EVOBOT_PREREGISTRATION",
        "proposal": "actuator_stall",
        "registered_before_change": True,
        "baseline": base,
        "prediction": {
            "final_pass_rate": "UNCHANGED at %d/%d" % (base["r_pass"], base["n"]),
            "first_attempt_pass_rate": "may rise by at most %d" % base["stalls_absorbed"],
            "persistent_stalls_still_fail": base["stalls_persistent"],
        },
        "success_criteria": [
            "final pass count must NOT fall below %d/%d" % (base["r_pass"], base["n"]),
            "final pass count is expected to stay EQUAL; a rise needs separate proof, "
            "not silent acceptance",
            "every run whose stall persisted across attempts must STILL fail",
            "false success rate must remain 0",
        ],
        "refutation_criteria": [
            "any persistent-stall run passes -> the retry converts real failures into "
            "passes and MUST be reverted",
            "final pass count drops -> regression, MUST be reverted",
            "false success becomes non-zero -> MUST be reverted",
        ],
        "notes": ("Written before any source change. The existing plan-level retry already "
                  "recovers %d of %d stall runs, so the honest increment of a skill-layer "
                  "retry is latency and risk, not final pass rate."
                  % (base["stalls_absorbed"], total_stalls)),
    }
    open(REG, "w", encoding="utf-8").write(json.dumps(reg, indent=2) + "\n")
    print(json.dumps(reg, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
