"""Build P2 failure reports from the archived runs and check what they support."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pilot import experience

ROOT = Path("/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp")
ACC = ROOT / "setup/acceptance"
OUT = ROOT / "docs/experience"
OUT.mkdir(parents=True, exist_ok=True)

RUNS = {
    # negative runs: these are what a lesson has to be derived FROM
    "levelc_prime": ACC / "w5_levelcprime_20261110",
    "c14_inventory": ACC / "c14_tool_inventory_20261110",
    # positive runs under the changed interface
    "c15_run_b": ACC / "w5_levelc_evidence_20261110/run_b_regions_visible",
    "c15_run_c1": ACC / "w5_levelc_evidence_20261110/run_c1",
}

reports = {}
for name, d in RUNS.items():
    if not (d / "result.json").is_file():
        print("MISSING", name, d)
        continue
    rep = experience.failure_report(d)
    rep["run_key"] = name
    reports[name] = rep
    (OUT / ("report_%s.json" % name)).write_text(
        json.dumps(rep, indent=2) + "\n", encoding="utf-8")

print(json.dumps({k: {"success": v["outcome"]["success"],
                       "iters": v["cost"]["iterations"],
                       "edited": v["behaviour"]["edited_source"],
                       "list_dir": v["behaviour"]["by_tool"].get("list_dir", 0)}
                  for k, v in reports.items()}, indent=2))

# The lesson is stated ONLY as strongly as the four runs support. The negative
# runs show traversal-without-narrowing; the positive runs show the same task
# solved once the evidence carried a location. That is an interface effect, and
# it is the only claim recorded.
neg = [reports[k] for k in ("levelc_prime", "c14_inventory") if k in reports]
pos = [reports[k] for k in ("c15_run_b", "c15_run_c1") if k in reports]
if neg and pos:
    assert all(r["behaviour"]["edited_source"] == 0 for r in neg)
    assert all(r["behaviour"]["edited_source"] == 1 for r in pos)
    rec = experience.experience_record(
        pos[0],
        defect_class="stage-transition / target-object selection (place target)",
        lesson=("When the failure evidence carries the code regions involved, the agent "
                "edits them without directory traversal: list_dir fell from 12-28 to 0 "
                "and the same defect was repaired in 4-5 iterations instead of never. "
                "Naming the file in the task text achieves the same thing, so the cost "
                "being removed is LOCALISATION, not reasoning."),
        evidence=[RUNS["c15_run_b"] / "result.json", RUNS["c15_run_b"] / "events.jsonl",
                  RUNS["c15_run_c1"] / "result.json", RUNS["c15_run_c1"] / "events.jsonl"])
    (OUT / "experience_place_target.json").write_text(
        json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    print("experience record written")
else:
    print("not enough runs to state a lesson; nothing written")
