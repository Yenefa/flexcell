"""W5-E1: a controlled self-improvement loop on a failing recovery implementation."""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

SKILL = '''"""Recovery decision used by the workcell executor."""


def next_action(outcome, error_code, budget):
    """Return the next step after a skill result.

    Allowed actions (the executor accepts only these):
      "DONE"    - task finished successfully
      "OBSERVE" - re-observe before retrying a recoverable failure
      "RETRY"   - retry the failed skill
      "ABORT"   - give up (non-recoverable, or budget exhausted)

    outcome: 0 = SUCCEEDED, 1 = FAILED. error_code: 30 = grasp failed.
    budget: remaining recovery attempts.
    """
    if outcome == 0:
        return "DONE"
    return "ABORT"
'''

SIM = '''import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skill.recovery import next_action

RECOVERABLE = {22, 23, 30}
trace = []
budget = 1
outcome, error_code = 1, 30
for step in range(4):
    action = next_action(outcome, error_code, budget)
    trace.append([action, outcome, error_code, budget])
    if action == "DONE":
        break
    if action == "ABORT":
        break
    if action in ("OBSERVE", "RETRY"):
        budget = max(0, budget - 1)
        outcome, error_code = 0, 0
result = {"trace": trace, "success": trace[-1][0] == "DONE" if trace else False}
print(json.dumps(result))
sys.exit(0 if result["success"] else 1)
'''

TEST_TARGET = '''import json
import subprocess
import sys


def test_recoverable_failure_is_recovered():
    proc = subprocess.run([sys.executable, "gate/sim.py"], capture_output=True, text=True)
    doc = json.loads(proc.stdout)
    assert doc["success"] is True
    assert doc["trace"][0][0] == "OBSERVE"
'''

TEST_REGRESSION = '''import subprocess
import sys

from skill.recovery import next_action


def test_success_is_done():
    assert next_action(0, 0, 1) == "DONE"


def test_non_recoverable_error_aborts():
    assert next_action(1, 999, 1) == "ABORT"


def test_budget_exhausted_aborts_after_recovery_attempt():
    # one recovery allowed: after using it, a second failure must abort
    assert next_action(1, 30, 0) == "ABORT"
'''


RUNNER = '''import importlib.util
import sys
import traceback
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
spec = importlib.util.spec_from_file_location("w5_regression", root / "tests" / "test_regression.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
failures = []
for name in sorted(dir(module)):
    if name.startswith("test_"):
        try:
            getattr(module, name)()
        except Exception:
            failures.append((name, traceback.format_exc()))
for name, tb in failures:
    print("FAIL", name)
    print(tb)
print("REGRESSION", "FAIL" if failures else "PASS", len(failures), "failure(s)")
sys.exit(1 if failures else 0)
'''

ACCEPT = '''import json
import subprocess
import sys
from pathlib import Path

sim = json.loads(subprocess.run([sys.executable, "gate/sim.py"], capture_output=True, text=True).stdout)
target_ok = sim["success"] is True and sim["trace"][0][0] == "OBSERVE"
regression = subprocess.run([sys.executable, "gate/run_regression.py"], capture_output=True, text=True)
verdict = {"passed": bool(target_ok and regression.returncode == 0),
           "target": target_ok,
           "regression_rc": regression.returncode,
           "trace": sim["trace"]}
print(json.dumps(verdict))
sys.exit(0 if verdict["passed"] else 1)
'''


def build_t_w5(target):
    target = Path(target)
    if target.exists():
        shutil.rmtree(target)
    (target / "skill").mkdir(parents=True)
    (target / "gate").mkdir()
    (target / "tests").mkdir()
    (target / "skill" / "__init__.py").write_text("", encoding="utf-8")
    (target / "skill" / "recovery.py").write_text(SKILL, encoding="utf-8")
    (target / "gate" / "sim.py").write_text(SIM, encoding="utf-8")
    (target / "gate" / "run_regression.py").write_text(RUNNER, encoding="utf-8")
    (target / "gate" / "acceptance.py").write_text(ACCEPT, encoding="utf-8")
    (target / "tests" / "test_target.py").write_text(TEST_TARGET, encoding="utf-8")
    (target / "tests" / "test_regression.py").write_text(TEST_REGRESSION, encoding="utf-8")
    (target / "task.md").write_text(
        "# W5-E1 - improve the recovery implementation\n\n"
        "The workcell aborts on a recoverable grasp failure (error 30) even though a\n"
        "recovery attempt is available. The executor accepts only the actions\n"
        "DONE, OBSERVE, RETRY and ABORT (see the docstring). Fix skill/recovery.py so\n"
        "the target scenario\n"
        "reaches DONE, without breaking existing behaviour (tests/test_regression.py).\n"
        "gate/ and tests/test_regression.py are read-only.\n",
        encoding="utf-8")
    return target


class W5Execution:
    def __init__(self, workspace, extra_env=None):
        self.workspace = Path(workspace)
        self.execution_s = 0.0
        self.extra_env = dict(extra_env or {})

    def run_checks(self):
        started = time.monotonic()
        proc = subprocess.run([sys.executable, "gate/run_regression.py"],
                              cwd=str(self.workspace), capture_output=True, text=True, timeout=120)
        self.execution_s += time.monotonic() - started
        return {"returncode": proc.returncode, "tail": (proc.stdout or "")[-2000:]}

    def run_execution(self, episode=True):
        started = time.monotonic()
        proc = subprocess.run([sys.executable, "gate/sim.py"], cwd=str(self.workspace),
                              capture_output=True, text=True, timeout=120)
        self.execution_s += time.monotonic() - started
        telemetry = self.workspace / "telemetry"
        telemetry.mkdir(exist_ok=True)
        doc = {"returncode": proc.returncode, "stdout": (proc.stdout or "")[-2000:],
               "stderr": (proc.stderr or "")[-1000:]}
        (telemetry / "execution.log").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        (self.workspace / "verdict.json").write_text(
            json.dumps({"passed": proc.returncode == 0, "returncode": proc.returncode}) + "\n",
            encoding="utf-8")
        return {"returncode": proc.returncode, "tail": (proc.stdout or "")[-1000:]}

    def telemetry(self):
        path = self.workspace / "telemetry" / "execution.log"
        return path.read_text(encoding="utf-8") if path.is_file() else "(no telemetry)"
