import json
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
