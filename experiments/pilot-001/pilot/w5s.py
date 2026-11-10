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
        # C15: the failure evidence carries its own location. Derived from the
        # failure itself (failing stage/object), NOT from a hand-written answer:
        # it names the code REGIONS that compute a place target, not the bug and
        # not the fix.
        regions = self._suspect_regions(summary)
        task = summary.get("task") or {}
        # Keep the detail short and put the regions FIRST: in the first C15 run
        # the long trace detail pushed suspect_regions past the truncation limit,
        # so the agent never saw the localisation this experiment is about.
        tail_doc = {
            "suspect_regions": regions,
            "status": summary.get("status"),
            "error_code": task.get("error_code"),
            "detail": str(task.get("detail") or "")[:220],
            "build_returncode": (summary.get("build") or {}).get("returncode"),
            "smoke_returncode": summary.get("smoke_returncode"),
        }
        tail = json.dumps(tail_doc)
        return {"returncode": 0 if build["returncode"] == 0 else 1, "tail": tail[:2400]}

    def _suspect_regions(self, summary, limit=5):
        """File:line of code that computes a place target, from the failure text."""
        task = summary.get("task") or {}
        detail = str(task.get("detail") or "")
        source = (self.workspace / "src" / "flexcell_skills" / "flexcell_skills"
                  / "task_fsm_server.py")
        if not source.is_file():
            return []
        lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
        hits = []
        for no, line in enumerate(lines, 1):
            stripped = line.strip()
            if "zones[" in stripped and "=" in stripped and "zx" in stripped:
                hits.append("src/flexcell_skills/flexcell_skills/task_fsm_server.py:%d: %s"
                            % (no, stripped[:90]))
        return hits[:limit]

    def telemetry(self):
        path = self.workspace / "telemetry" / "execution.log"
        return path.read_text(encoding="utf-8") if path.is_file() else "(no telemetry)"

# ---------------------------------------------------------------------------
# P2 second task: a DIFFERENT defect class in the same file. PLACE is left
# correct; VERIFY is made to check the object against the OTHER object's zone,
# so the symptom (VERIFY_B mismatched after a successful PLACE_B) looks the same
# but the defect lives in a different branch. This is what makes the reuse test
# about a transferable lesson rather than about one memorised line.
# ---------------------------------------------------------------------------
DEFECT2_FROM = ("                    zx, zy, zz = zones[zone_of[decision.target]]\n"
                "                    zone_pose = PoseStamped()\n"
                "                    zone_pose.header.frame_id = 'world'\n"
                "                    zone_pose.pose.position.x = zx\n"
                "                    zone_pose.pose.position.y = zy\n"
                "                    zone_pose.pose.position.z = zz\n"
                "                    zone_pose.pose.orientation.w = 1.0\n"
                "                    vg = VerifyObject.Goal()")
DEFECT2_TO = DEFECT2_FROM.replace("zones[zone_of[decision.target]]",
                                  "zones[zone_of[self._obj_a]]", 1)

TASK2 = (
    "# W5-E3 - the two-object demo fails at final verification\n\n"
    "The workcell configuration is correct. The two-object demo fails: both\n"
    "objects are picked and placed, but the final verification reports the\n"
    "second object away from where it was just put. The normal task and the\n"
    "regrasp task still pass.\n\n"
    "The defect is in the task FSM implementation\n"
    "(src/flexcell_skills/flexcell_skills/task_fsm_server.py); the workcell config\n"
    "is correct. You may read and edit files there; every run rebuilds the package\n"
    "before launching Gazebo. gate/ is read-only and does not need to be inspected.\n\n"
    "A previous investigation left a note in the experience/ directory. Read it if\n"
    "you think it helps. Run the target scenario once, find the implementation\n"
    "defect, edit task_fsm_server.py to fix it, and make all three gates pass.\n")


def build_t_w5s2(target, package_src, config_source, experience_note=None):
    """Same skeleton as build_t_w5s, but injects the VERIFY-side defect."""
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
    if DEFECT2_FROM not in text:
        raise RuntimeError("verify-side defect anchor missing")
    module.write_text(text.replace(DEFECT2_FROM, DEFECT2_TO, 1), encoding="utf-8")
    shutil.copyfile(config_source, target / "config" / "week1.yaml")
    (target / "gate" / "acceptance.py").write_text(ACCEPT, encoding="utf-8")
    (target / "task.md").write_text(TASK2, encoding="utf-8")
    if experience_note is not None:
        (target / "experience").mkdir()
        shutil.copyfile(experience_note,
                        target / "experience" / "experience_place_target.json")
    return target
