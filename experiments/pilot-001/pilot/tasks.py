"""T-A v2 task template: real contracts/composite.py, invalid clearance at start."""
import json
import shutil
from pathlib import Path

ACCEPTANCE = '''import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from composite_contract import CompositeError, prepare_plan

plan = json.loads(Path("plan.json").read_text(encoding="utf-8"))
try:
    prepare_plan(plan)
    verdict = {"passed": True, "stages": len(plan["stages"]), "clearance_m": plan["clearance_m"]}
except CompositeError as exc:
    verdict = {"passed": False, "error_code": exc.code, "detail": str(exc), "clearance_m": plan.get("clearance_m")}
except Exception as exc:
    verdict = {"passed": False, "error": type(exc).__name__ + ": " + str(exc)}
print(json.dumps(verdict))
sys.exit(0 if verdict.get("passed") else 1)
'''

TASK_MD = """# T-A v2 - parameter level (composite plan)

The contract validator rejects the current plan. Fix the plan so the declared
chain is accepted.

Files: plan.json (yours to edit), gate/ (read-only, must not be modified).

Acceptance: gate/acceptance.py exits 0 and prints {"passed": true}.
"""


def build(target, contracts_src):
    target = Path(target)
    if target.exists():
        shutil.rmtree(target)
    (target / "gate").mkdir(parents=True)
    (target / "task.md").write_text(TASK_MD, encoding="utf-8")
    shutil.copyfile(contracts_src, target / "gate" / "composite_contract.py")
    (target / "gate" / "acceptance.py").write_text(ACCEPTANCE, encoding="utf-8")
    plan = {
        "scenario_id": "pilot-t-a-v2",
        "initial_objects": {"a": [0.22, 0.0, 0.0175], "b": [0.20, -0.18, 0.0175]},
        "stages": [{"stage_id": "s1", "object_name": "a", "destination": [0.20, 0.20, 0.0175]}],
        "final_empty_positions": [[0.22, 0.0, 0.0175]],
        "position_tolerance_m": 0.05,
        "clearance_m": 0.02,
        "motion_profile_id": "default",
    }
    (target / "plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    return target
