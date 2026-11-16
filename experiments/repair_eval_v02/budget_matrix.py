"""Run all 24 slots through the real repair loop and the real budget ledger.

This is the second half of the #252 gap. dry_run_matrix.py proved the slots,
conditions and gate compose, but its agent was a fixed script that never spent a
token - so the ledger, the 6-interaction cap and the BUDGET_EXHAUSTED rule had
no coverage. This drives the same 24 slots through RepairAgent and Ledger.

The transport here is a stand-in that returns the known fix on its first turn.
It is NOT a model: every row carries qualification SCRIPTED_TRANSPORT. What it
proves is that the accounting is complete and that exhaustion is recorded as
its own state instead of being folded into success or failure.

Two slots burn their budget on purpose, so the exclusion rule is demonstrated on
real matrix rows rather than only in a unit test.
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (str(HERE), str(ROOT), str(ROOT / "benchmark" / "repair_eval" / "contracts")):
    if path not in sys.path:
        sys.path.insert(0, path)

import budget as B                                    # noqa: E402
import task_contract                                  # noqa: E402
from agent import RepairAgent                         # noqa: E402
from benchmark.repair_eval import visibility as vis    # noqa: E402
from dry_run_matrix import (CONDITIONS, DEFECTS, FAMILIES, REPEATS,  # noqa: E402
                            build_candidate, contract_for)

QUALIFICATION = "SCRIPTED_TRANSPORT_NOT_A_MODEL_RESULT"


class StandInTransport:
    """Returns a fixed fix on turn 1. Not a model, and says so."""

    def __init__(self, family, burn_budget=False):
        self.family = family
        self.burn_budget = burn_budget
        self.calls = 0

    def chat(self, messages, **kwargs):
        self.calls += 1
        if self.burn_budget:
            text = '{"actions": [], "claim_success": false, "done": false}'
        else:
            name = "registry.py" if self.family.startswith("F1") else "mapping.py"
            payload = {
                "actions": [{"write_file": ["skill/" + name,
                                            DEFECTS[self.family]["fixed"]]}],
                "claim_success": True,
                "done": True,
            }
            text = json.dumps(payload)
        return {"text": text,
                "usage": {"prompt_tokens": 120, "completion_tokens": 40}}


def run_slot(family, condition, rep, workdir, policy, donor, burn_budget=False):
    slot_id = "%s-%s-r%d" % (family.split("_")[0], condition[0], rep)
    candidate = build_candidate(workdir / "candidate", family)
    verdict_dir = workdir / "verdict"
    verdict_dir.mkdir()
    hidden = workdir / "hidden"
    hidden.mkdir()

    boundary = vis.RunBoundary(policy, workdir, candidate, verdict_dir, hidden,
                               condition=condition, mismatch_dir=donor)

    # Order matters and the gate enforces it: freshness is asserted while the
    # candidate is still clean, and only then does the execution phase write
    # telemetry. Writing telemetry first raises StaleArtifact, which is the gate
    # correctly refusing a run that inherits another run's feedback.
    boundary.assert_fresh_run()
    (candidate / "telemetry").mkdir(exist_ok=True)
    (candidate / "telemetry" / "execution.log").write_text(
        "REAL FAILURE: defect present" + chr(10))

    contract = task_contract.TaskContract.from_mapping(contract_for(family))
    transport = StandInTransport(family, burn_budget=burn_budget)
    ledger = B.Ledger(transport)

    agent = RepairAgent(ledger, boundary, "Repair the %s defect." % family,
                        contract.editable_fields)
    result = agent.run()

    return dict(
        slot_id=slot_id, family=family, condition=condition, repetition=rep,
        qualification=QUALIFICATION,
        terminal_state=result["terminal_state"],
        claimed_success=result["claimed_success"],
        interactions=result["account"]["interactions_used"],
        tokens_total=result["account"]["tokens_total"],
        exhausted_at=result["account"]["budget_exhausted_at"],
        writes=result["writes"],
        counts_toward_denominator=result["terminal_state"] != B.BUDGET_EXHAUSTED,
    )


def main():
    policy = vis.load_policy(ROOT / "benchmark" / "repair_eval" / "visibility_policy.json")
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        donor = tmp / "donor"
        (donor / "telemetry").mkdir(parents=True)
        (donor / "telemetry" / "execution.log").write_text("DONOR FAILURE" + chr(10))
        (donor / "verdict.json").write_text('{"passed": false}')
        for family in FAMILIES:
            for condition in CONDITIONS:
                for rep in REPEATS:
                    workdir = tmp / ("%s-%s-r%d" % (family, condition, rep))
                    workdir.mkdir(parents=True)
                    burn = (rep == 3 and condition == "D_GUIDED")
                    rows.append(run_slot(family, condition, rep, workdir, policy,
                                         donor, burn_budget=burn))

    counted = [r for r in rows if r["counts_toward_denominator"]]
    summary = {
        "slots": len(rows),
        "expected": len(FAMILIES) * len(CONDITIONS) * len(REPEATS),
        "terminal_states": {},
        "counted_in_denominator": len(counted),
        "excluded_budget_exhausted": len(rows) - len(counted),
        "every_row_has_full_account": all(
            r["interactions"] is not None and r["tokens_total"] is not None for r in rows),
        "no_row_exceeds_cap": all(
            r["interactions"] <= B.DEFAULT_INTERACTIONS
            and r["tokens_total"] <= B.DEFAULT_TOKENS for r in rows),
        "qualification": QUALIFICATION,
    }
    for row in rows:
        key = row["terminal_state"]
        summary["terminal_states"][key] = summary["terminal_states"].get(key, 0) + 1
    print(json.dumps(dict(summary=summary, rows=rows), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
