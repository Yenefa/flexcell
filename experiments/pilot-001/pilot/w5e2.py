"""W5-E2: self-improvement on the real Gazebo stack (config defect, two gates)."""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import gazebo

ACCEPT = '''import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.environ["PILOT_HOME"])
from pilot import gazebo

cfg = str(Path("config/week1.yaml").resolve())
repo = os.environ["PILOT_P14_REPO"]
ws = os.environ["PILOT_P14_WS"]
src = os.environ["PILOT_P14_SRC"]

def run(case, out):
    res = gazebo.run_smoke(src, repo, ws, out, case=case, build=False,
                           config_override=cfg, timeout_s=420)
    run_dir = gazebo.latest(out)
    dest = tempfile.mkdtemp(prefix="w5e2-")
    if run_dir:
        gazebo.export(run_dir, dest)
    doc = gazebo.collect(dest).get("summary", {})
    return {"status": doc.get("status"), "returncode": res.get("returncode"),
            "fingerprint": doc.get("runtime_fingerprint")}

target = run("dual_object", "/tmp/w5e2-target")
regression = run("normal", "/tmp/w5e2-regression")
verdict = {"passed": target["status"] == "PASS" and regression["status"] == "PASS",
           "target": target, "regression": regression}
print(json.dumps(verdict))
sys.exit(0 if verdict["passed"] else 1)
'''


def build_t_w5e2(target, config_source):
    target = Path(target)
    if target.exists():
        import shutil
        shutil.rmtree(target)
    (target / "gate").mkdir(parents=True)
    (target / "config").mkdir()
    (target / "telemetry").mkdir()
    text = Path(config_source).read_text(encoding="utf-8")
    # The shipped default places the second object within reach; this task starts
    # from a workcell where zone_2 was moved out of reach.
    text = text.replace("zone_2_x: 0.25", "zone_2_x: 0.45").replace("zone_2_y: 0.05", "zone_2_y: 0.05")
    (target / "config" / "week1.yaml").write_text(text, encoding="utf-8")
    (target / "gate" / "acceptance.py").write_text(ACCEPT, encoding="utf-8")
    (target / "task.md").write_text(
        "# W5-E2 - repair the workcell configuration\n\n"
        "The two-object task fails: the SECOND object destination (zone_2) is out of\n"
        "reach (the arm reaches strictly below 0.30 m from the base). The normal task\n"
        "still works. Fix config/week1.yaml so that BOTH the two-object task and the\n"
        "normal task verify on the real stack. gate/ is read-only.\n",
        encoding="utf-8")
    return target


class W5E2Execution:
    def __init__(self, workspace, extra_env=None):
        self.workspace = Path(workspace)
        self.execution_s = 0.0
        self.extra_env = dict(extra_env or {})

    def run_checks(self):
        return {"returncode": 5, "tail": "(no unit tests for the config task)"}

    def run_execution(self, episode=True):
        started = time.monotonic()
        cfg = str((self.workspace / "config" / "week1.yaml").resolve())
        res = gazebo.run_smoke(self.extra_env["PILOT_P14_SRC"],
                               self.extra_env["PILOT_P14_REPO"],
                               self.extra_env["PILOT_P14_WS"],
                               "/tmp/w5e2-agent", case="dual_object", build=False,
                               config_override=cfg, timeout_s=420)
        self.execution_s += time.monotonic() - started
        run_dir = gazebo.latest("/tmp/w5e2-agent")
        dest = tempfile.mkdtemp(prefix="w5e2-agent-")
        if run_dir:
            gazebo.export(run_dir, dest)
        summary = gazebo.collect(dest).get("summary", {})
        summary["limits"] = {"max_reach_m": 0.30, "rule": "reach = hypot(x, y) must be strictly below max_reach_m"}
        (self.workspace / "telemetry").mkdir(exist_ok=True)
        (self.workspace / "telemetry" / "execution.log").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        (self.workspace / "episode.json").write_text(
            json.dumps({"task": "W5-E2", "gazebo": summary}) + "\n", encoding="utf-8")
        return {"returncode": res["returncode"], "tail": json.dumps(summary)[:800]}

    def telemetry(self):
        path = self.workspace / "telemetry" / "execution.log"
        return path.read_text(encoding="utf-8") if path.is_file() else "(no telemetry)"
