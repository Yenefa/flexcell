"""P1.4 stage 2: a task whose execution is a real Gazebo run."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import gazebo

ACCEPT = '''import json
import os
import subprocess
import sys
from pathlib import Path

plan = json.loads(Path("plan.json").read_text(encoding="utf-8"))
pose = plan["place_pose"]
repo = os.environ["PILOT_P14_REPO"]
ws = os.environ["PILOT_P14_WS"]
src = os.environ["PILOT_P14_SRC"]
out = "/tmp/p14-judge"
res = __import__("pilot.gazebo", fromlist=["run_smoke"]).run_smoke(
    src, repo, ws, out, case="normal", build=False, place_pose=pose, timeout_s=420)
import tempfile
G = __import__("pilot.gazebo", fromlist=["collect"])
run_dir = G.latest("/tmp/p14-judge")
dest = tempfile.mkdtemp(prefix="p14-judge-")
if run_dir:
    G.export(run_dir, dest)
summary = G.collect(dest)
doc = summary.get("summary", {})
verdict = {"passed": doc.get("status") == "PASS",
           "status": doc.get("status"),
           "runtime_fingerprint": doc.get("runtime_fingerprint"),
           "place_pose": pose,
           "returncode": res.get("returncode")}
print(json.dumps(verdict))
sys.exit(0 if verdict["passed"] else 1)
'''


class GazeboTaskExecution:
    def __init__(self, workspace, extra_env=None):
        self.workspace = Path(workspace)
        self.execution_s = 0.0
        self.extra_env = dict(extra_env or {})

    def run_checks(self):
        return {"returncode": 5, "tail": "(no unit tests for the Gazebo task)"}

    def run_execution(self, episode=True):
        plan = json.loads((self.workspace / "plan.json").read_text(encoding="utf-8"))
        started = time.monotonic()
        res = gazebo.run_smoke(self.extra_env["PILOT_P14_SRC"],
                               self.extra_env["PILOT_P14_REPO"],
                               self.extra_env["PILOT_P14_WS"],
                               "/tmp/p14-agent", case="normal", build=False,
                               place_pose=plan["place_pose"], timeout_s=420)
        self.execution_s += time.monotonic() - started
        run_dir = gazebo.latest("/tmp/p14-agent")
        import tempfile
        dest = tempfile.mkdtemp(prefix="p14-agent-")
        if run_dir:
            gazebo.export(run_dir, dest)
        summary = gazebo.collect(dest).get("summary", {})
        summary["limits"] = {"max_reach_m": 0.30, "rule": "reach = hypot(x, y) must be strictly below max_reach_m"}
        (self.workspace / "telemetry").mkdir(exist_ok=True)
        (self.workspace / "telemetry" / "execution.log").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        (self.workspace / "episode.json").write_text(
            json.dumps({"task": "T-G1", "gazebo": summary}) + "\n", encoding="utf-8")
        return {"returncode": res["returncode"],
                "tail": json.dumps(summary)[:800]}

    def telemetry(self):
        path = self.workspace / "telemetry" / "execution.log"
        return path.read_text(encoding="utf-8") if path.is_file() else "(no telemetry)"


def build_tg(target):
    target = Path(target)
    if target.exists():
        import shutil
        shutil.rmtree(target)
    (target / "gate").mkdir(parents=True)
    (target / "task.md").write_text(
        "# T-G1 - real Gazebo parameter task\n\n"
        "plan.json holds place_pose = [x, y, z]. The robot fails when the pose is\n"
        "out of reach. The arm reaches strictly less than 0.30 m from the base. Fix plan.json\n"
        "so the real task verifies. gate/ is read-only.\n",
        encoding="utf-8")
    (target / "gate" / "acceptance.py").write_text(ACCEPT, encoding="utf-8")
    (target / "plan.json").write_text(json.dumps(
        {"place_pose": [0.45, 0.0, 0.0175]}, indent=2) + "\n", encoding="utf-8")
    return target


def build_tg2(target):
    target = Path(target)
    if target.exists():
        import shutil
        shutil.rmtree(target)
    (target / "gate").mkdir(parents=True)
    (target / "task.md").write_text(
        "# T-G2 - real Gazebo placement task\n\n"
        "The robot fails because the place pose is too close to the base.\n"
        "Valid poses are 0.12 m to 0.30 m from the base (strictly below 0.30).\n"
        "Fix plan.json so the real task verifies. gate/ is read-only.\n",
        encoding="utf-8")
    (target / "gate" / "acceptance.py").write_text(ACCEPT, encoding="utf-8")
    (target / "plan.json").write_text(json.dumps(
        {"place_pose": [0.05, 0.0, 0.0175]}, indent=2) + "\n", encoding="utf-8")
    return target
