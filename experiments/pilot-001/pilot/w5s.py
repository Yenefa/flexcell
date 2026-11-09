"""W5-E3: self-improvement on the real stack with a defect in skill source code.

The workcell config is correct; the FSM implementation places every object into the
first assignment zone. The agent must find the code defect, edit the package and
let the harness rebuild before each Gazebo run.
"""
import json
import shutil
import tempfile
import time
from pathlib import Path

from . import gazebo

DEFECT_FROM = "                    zx, zy, zz = zones[zone_of[decision.target]]"
DEFECT_TO = "                    zx, zy, zz = zones[zone_of[self._obj_a]]"

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
pkg = str(Path("src/flexcell_skills").resolve())

build = gazebo.build_source(pkg)
if build["returncode"] != 0:
    print(json.dumps({"passed": False, "build": build}))
    sys.exit(1)
setup = build["setup"]
repo = build["repo"]

def run(case, out):
    res = gazebo.run_smoke(src, repo, ws, out, case=case, build=False,
                           config_override=cfg, timeout_s=420, extra_setup=setup,
                           install_override=build["install"])
    run_dir = gazebo.latest(out)
    dest = tempfile.mkdtemp(prefix="w5s-")
    if run_dir:
        gazebo.export(run_dir, dest)
    doc = gazebo.collect(dest).get("summary", {})
    return {"status": doc.get("status"), "returncode": res.get("returncode")}

target = run("dual_object", "/tmp/w5s-target")
normal = run("normal", "/tmp/w5s-normal")
regrasp = run("regrasp", "/tmp/w5s-regrasp")
verdict = {"passed": target["status"] == "PASS" and normal["status"] == "PASS"
           and regrasp["status"] == "PASS",
           "target": target, "regression_normal": normal, "regression_regrasp": regrasp,
           "build": {"returncode": build["returncode"]}}
print(json.dumps(verdict))
sys.exit(0 if verdict["passed"] else 1)
'''

TASK = (
    "# W5-E3 - the two-object demo mis-places the second object\n\n"
    "The workcell configuration is correct. The two-object demo fails: the first\n"
    "object is picked, placed and verified, then the second object is also picked\n"
    "and placed - but the final verification reports the second object about 0.3 m\n"
    "away from its zone. The normal task and the regrasp task still pass.\n\n"
    "The defect is in the task FSM implementation\n"
    "(src/flexcell_skills/flexcell_skills/task_fsm_server.py); the workcell config\n"
    "is correct. You may read and edit files there; every run rebuilds the package\n"
    "before launching Gazebo. gate/ is read-only and does not need to be inspected.\n\n"
    "Use search_code to locate the place-target computation; do not list directories\n"
    "repeatedly. Run the target scenario once, find the implementation defect, edit\n"
    "task_fsm_server.py to fix it, and make all three gates pass.\n")

def build_t_w5s(target, package_src, config_source):
    target = Path(target)
    if target.exists():
        shutil.rmtree(target)
    (target / "gate").mkdir(parents=True)
    (target / "config").mkdir()
    (target / "telemetry").mkdir()
    pkg = target / "src" / "flexcell_skills"
    shutil.copytree(package_src, pkg)
    module = pkg / "flexcell_skills" / "task_fsm_server.py"
    text = module.read_text(encoding="utf-8")
    if DEFECT_FROM not in text:
        raise RuntimeError("defect anchor missing from task_fsm_server.py")
    module.write_text(text.replace(DEFECT_FROM, DEFECT_TO, 1), encoding="utf-8")
    shutil.copyfile(config_source, target / "config" / "week1.yaml")
    (target / "gate" / "acceptance.py").write_text(ACCEPT, encoding="utf-8")
    (target / "task.md").write_text(TASK, encoding="utf-8")
    return target


class W5SourceExecution:
    def __init__(self, workspace, extra_env=None):
        self.workspace = Path(workspace)
        self.extra_env = dict(extra_env or {})
        self.execution_s = 0.0

    def run_checks(self):
        return {"returncode": 5, "tail": "(no unit tests for the source task)"}

    def _build(self):
        pkg = self.workspace / "src" / "flexcell_skills"
        return gazebo.build_source(str(pkg))

    def run_execution(self, episode=True):
        started = time.monotonic()
        build = self._build()
        summary = {"build": {"returncode": build["returncode"],
                             "tail": (build.get("stderr") or build.get("stdout") or "")[-1200:]}}
        if build["returncode"] == 0:
            cfg = str((self.workspace / "config" / "week1.yaml").resolve())
            res = gazebo.run_smoke(self.extra_env["PILOT_P14_SRC"],
                                   build.get("repo") or self.extra_env["PILOT_P14_REPO"],
                                   self.extra_env["PILOT_P14_WS"],
                                   "/tmp/w5s-agent", case="dual_object", build=False,
                                   config_override=cfg, timeout_s=420,
                                   extra_setup=build["setup"],
                                   install_override=build["install"])
            run_dir = gazebo.latest("/tmp/w5s-agent")
            dest = tempfile.mkdtemp(prefix="w5s-agent-")
            if run_dir:
                gazebo.export(run_dir, dest)
            summary.update(gazebo.collect(dest).get("summary", {}))
            summary["smoke_returncode"] = res["returncode"]
        self.execution_s += time.monotonic() - started
        (self.workspace / "telemetry").mkdir(exist_ok=True)
        (self.workspace / "telemetry" / "execution.log").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        (self.workspace / "episode.json").write_text(
            json.dumps({"task": "W5-E3", "gazebo": summary}) + "\n", encoding="utf-8")
        tail = json.dumps({k: summary.get(k) for k in ("status", "task", "build", "smoke_returncode")})
        return {"returncode": 0 if build["returncode"] == 0 else 1, "tail": tail[:900]}

    def telemetry(self):
        path = self.workspace / "telemetry" / "execution.log"
        return path.read_text(encoding="utf-8") if path.is_file() else "(no telemetry)"
