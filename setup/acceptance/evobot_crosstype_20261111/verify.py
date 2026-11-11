#!/usr/bin/env python3
"""Verify the cross-type test without privilege.

WHY NO ROOT: the first version read the required order from /etc/evobot/sealed, so it passed
under sudo and failed when the evidence index ran it as an ordinary user. A verifier that only
works with root cannot belong to an evidence chain anyone can re-run.

The required order does not need to be fetched: the evaluator already writes it into the
verdict's "order" clause evidence (required, observed, matched, out_of_order). Reading that is
also the more honest source, since it is what a reviewer would inspect.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]
RUNS = HERE / "runs_T14_ordered_pair"


def read(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return {}


def order_clause(verdict):
    for c in verdict.get("clauses", []):
        if c.get("clause") == "order":
            return c
    return {}


def classify(seq, required):
    seq = list(seq)
    if not required:
        return "no-requirement"
    if seq[:len(required)] == required:
        return "in-order"
    if len(seq) < len(required) and seq == required[:len(seq)]:
        return "INCOMPLETE"
    return "WRONG-ORDER"


def main():
    runs = sorted(RUNS.glob("HO-*"))
    assert len(runs) == 16, len(runs)

    v = WT / "experiments" / "baselines" / "validate_batch.py"
    rc = subprocess.run([sys.executable, str(v), str(RUNS)], capture_output=True, text=True)
    assert rc.returncode == 0, rc.stdout[:600]

    plan_ok = exec_ok = wr = incomplete = b_pass = r_pass = 0
    for d in runs:
        v1 = read(d / "verdict_after1.json")
        oc = order_clause(v1)
        required = (oc.get("evidence") or {}).get("required") or []
        assert len(required) == 2, (d.name, required)
        plan = read(d / "plan.json")
        planned = [s.get("object_name") for s in plan.get("stages", [])]
        obs = read(d / "observation_after1.json")
        seq = obs.get("move_sequence") or []
        ps, es = classify(planned, required), classify(seq, required)
        plan_ok += 1 if ps == "in-order" else 0
        exec_ok += 1 if es == "in-order" else 0
        incomplete += 1 if es == "INCOMPLETE" else 0
        wr += 1 if es == "WRONG-ORDER" else 0
        assert bool(oc.get("ok")) == (es == "in-order"), (d.name, oc.get("ok"), es)
        b_pass += 1 if v1.get("passed") else 0
        r_pass += 1 if read(d / "verdict.json").get("passed") else 0

    assert plan_ok == 16, plan_ok
    assert wr == 0, "an instance reordered the work, so the claim must be weakened"
    assert incomplete == 2, incomplete
    assert exec_ok == 14, exec_ok
    assert b_pass == 14 and r_pass == 16, (b_pass, r_pass)

    print(json.dumps({
        "verdict": "EVOBOT_CROSSTYPE_ORDER_CONSTRAINT",
        "new_template": "T14_ordered_pair (constrains WHEN, not just WHERE)",
        "seeds": "9300/9400, zero overlap with earlier sets",
        "planning_in_order": "16/16 = 100% (80.6-100%)",
        "execution_in_order": "14/16 = 87.5%",
        "wrong_order": 0,
        "incomplete": 2,
        "arm_B": "14/16",
        "arm_R": "16/16",
        "required_order_source": "the verdict own order clause (no privileged read)",
        "incomplete_cause": "the run stopped before the later move; both recovered",
        "evaluator_touched": False,
        "skill_layer_touched": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
