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

def run(case, out):
    res = gazebo.run_smoke(src, repo, ws, out, case=case, build=False,
                           config_override=cfg, timeout_s=420)
    run_dir = gazebo.latest(out)
    dest = tempfile.mkdtemp(prefix="w5e2c-")
    if run_dir:
        gazebo.export(run_dir, dest)
    doc = gazebo.collect(dest).get("summary", {})
    return {"status": doc.get("status"), "returncode": res.get("returncode")}

target = run("dual_object", "/tmp/w5e2c-target")
reg_normal = run("normal", "/tmp/w5e2c-normal")
reg_regrasp = run("regrasp", "/tmp/w5e2c-regrasp")
verdict = {"passed": all(x["status"] == "PASS" for x in (target, reg_normal, reg_regrasp)),
           "target": target, "regression_normal": reg_normal, "regression_regrasp": reg_regrasp}
print(json.dumps(verdict))
sys.exit(0 if verdict["passed"] else 1)
