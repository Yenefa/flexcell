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

TC_ACCEPTANCE = '''import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from composite_contract import CompositeError, prepare_plan

plan = json.loads(Path("plan.json").read_text(encoding="utf-8"))
robot = json.loads(Path(os.environ["PILOT_ROBOT"]).read_text(encoding="utf-8"))
verdict = {"passed": False}
try:
    prepare_plan(plan)
except CompositeError as exc:
    verdict = {"passed": False, "error_code": exc.code, "detail": str(exc), "stage": "contract"}
else:
    dest = plan["stages"][0]["destination"]
    reach = (dest[0] ** 2 + dest[1] ** 2) ** 0.5
    if reach > robot["max_reach_m"] + 1e-9:
        verdict = {"passed": False, "error_code": 71,
                   "detail": "destination unreachable: %.3f m > max_reach %.3f m" % (reach, robot["max_reach_m"]),
                   "stage": "execution"}
    else:
        verdict = {"passed": True, "reach_m": round(reach, 4), "stage": "verified"}
print(json.dumps(verdict))
sys.exit(0 if verdict["passed"] else 1)
'''

TC_SIM = r'''import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from composite_contract import CompositeError, prepare_plan

plan = json.loads(Path("plan.json").read_text(encoding="utf-8"))
robot = json.loads(Path(os.environ["PILOT_ROBOT"]).read_text(encoding="utf-8"))
Path("telemetry").mkdir(exist_ok=True)
log = open("telemetry/execution.log", "a", encoding="utf-8")
log.write("robot max_reach_m=%.3f\n" % robot["max_reach_m"])
ok = True
try:
    prepare_plan(plan)
    log.write("contract: accepted\n")
except CompositeError as exc:
    ok = False
    log.write("contract: REJECTED code=%s %s\n" % (exc.code, exc))
else:
    dest = plan["stages"][0]["destination"]
    reach = (dest[0] ** 2 + dest[1] ** 2) ** 0.5
    log.write("stage s1 destination=(%.3f, %.3f) reach=%.3f\n" % (dest[0], dest[1], reach))
    if reach > robot["max_reach_m"] + 1e-9:
        ok = False
        log.write("EXECUTION_ERROR code=71 unreachable: reach %.3f > max %.3f\n" % (reach, robot["max_reach_m"]))
    else:
        log.write("stage s1: moved and verified ok\n")
log.close()
Path("episode.json").write_text(json.dumps({"task": "T-C-v1", "ok": ok}) + "\n", encoding="utf-8")
raise SystemExit(0 if ok else 1)
'''


class TCExecution:
    """Execution surface for T-C v1; reads hidden robot model from the runner env."""

    def __init__(self, workspace):
        self.workspace = Path(workspace)
        self.execution_s = 0.0
        self.extra_env = None

    def _env(self):
        import os
        env = dict(os.environ)
        if self.extra_env:
            env.update(self.extra_env)
        return env

    def run_checks(self):
        import subprocess
        import time
        started = time.monotonic()
        env = dict(__import__("os").environ)
        env["PYTHONPATH"] = str(self.workspace) + __import__("os").pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.run([__import__("sys").executable, "-m", "pytest", "-q", "tests"],
                              cwd=str(self.workspace), capture_output=True, text=True, timeout=60, env=self._env())
        self.execution_s += time.monotonic() - started
        return {"returncode": proc.returncode, "tail": (proc.stdout or "")[-800:]}

    def run_execution(self, episode=True):
        import subprocess
        import time
        started = time.monotonic()
        proc = subprocess.run([__import__("sys").executable, "gate/sim.py"],
                              cwd=str(self.workspace), capture_output=True, text=True, timeout=120, env=self._env())
        self.execution_s += time.monotonic() - started
        return {"returncode": proc.returncode, "tail": ((proc.stdout or "") + (proc.stderr or ""))[-800:]}

    def telemetry(self):
        path = self.workspace / "telemetry" / "execution.log"
        if not path.is_file():
            return "(no telemetry)"
        return path.read_text(encoding="utf-8")[-3000:]


def build_tc(target, contracts_src):
    target = Path(target)
    if target.exists():
        shutil.rmtree(target)
    (target / "gate").mkdir(parents=True)
    (target / "task.md").write_text(
        "# T-C v1 - execution-visible failure\n\n"
        "The plan in plan.json is rejected when executed on the robot.\n"
        "Fix plan.json so the task verifies. gate/ is read-only.\n",
        encoding="utf-8")
    shutil.copyfile(contracts_src, target / "gate" / "composite_contract.py")
    (target / "gate" / "acceptance.py").write_text(TC_ACCEPTANCE, encoding="utf-8")
    (target / "gate" / "sim.py").write_text(TC_SIM, encoding="utf-8")
    plan = {
        "scenario_id": "pilot-t-c-v1",
        "initial_objects": {"a": [0.22, 0.0, 0.0175], "b": [0.20, -0.18, 0.0175]},
        "stages": [{"stage_id": "s1", "object_name": "a",
                    "destination": [0.34, 0.0, 0.0175]}],
        "final_empty_positions": [[0.22, 0.0, 0.0175]],
        "position_tolerance_m": 0.02,
        "clearance_m": 0.06,
        "motion_profile_id": "default",
    }
    (target / "plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    return target
