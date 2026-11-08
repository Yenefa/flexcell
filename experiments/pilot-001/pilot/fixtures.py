"""Workspace templates + scripted (human-simulated) agents for P1.0 fixtures."""
import json
import shutil
from pathlib import Path

GOOD_APP = "def scale(x):\n    return x * 2\n"
BAD_APP = "def scale(x):\n    return x + 1\n"
TEST = "from app import scale\n\n\ndef test_scale():\n    assert scale(2) == 4\n    assert scale(3) == 6\n"

ACCEPTANCE = '''import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import scale

ok = scale(2) == 4 and scale(3) == 6
print(json.dumps({"passed": ok, "observed": [scale(2), scale(3)], "target": [4, 6]}))
sys.exit(0 if ok else 1)
'''

SIM = r'''import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app

ap = argparse.ArgumentParser()
ap.add_argument("--no-episode", action="store_true")
args = ap.parse_args()
ok = app.scale(2) == 4
Path("telemetry").mkdir(exist_ok=True)
with open("telemetry/execution.log", "a", encoding="utf-8") as fh:
    print("cmd=scale(2) got=%r want=4 ok=%r" % (app.scale(2), ok), file=fh)
if not args.no_episode:
    Path("episode.json").write_text(json.dumps({"steps": ["scale(2)"], "ok": ok}) + "\n")
raise SystemExit(0 if ok else 1)
'''


def make_template(target, app=BAD_APP, protected_ok=True):
    target = Path(target)
    if target.exists():
        shutil.rmtree(target)
    (target / "tests").mkdir(parents=True)
    (target / "gate").mkdir(parents=True)
    (target / "telemetry").mkdir(parents=True)
    (target / "app.py").write_text(app, encoding="utf-8")
    (target / "tests" / "test_app.py").write_text(TEST, encoding="utf-8")
    (target / "tests" / "conftest.py").write_text("import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n", encoding="utf-8")
    (target / "gate" / "acceptance.py").write_text(ACCEPTANCE, encoding="utf-8")
    (target / "gate" / "sim.py").write_text(SIM, encoding="utf-8")
    (target / "gate" / "thresholds.json").write_text(json.dumps({"target": 4}) + "\n", encoding="utf-8")
    return target


class ScriptedAgent:
    """Human-simulated agent: a fixed script, used only to validate measurement."""

    def __init__(self, actions, claim_success=False, done=True, tokens=10):
        self.actions = actions
        self.claim_success = claim_success
        self.done = done
        self.tokens = tokens
        self._ran = False

    def step(self, tools, iteration):
        if self._ran or iteration > 1:
            return {"claim_success": self.claim_success, "done": True, "tokens": 1}
        self._ran = True
        for name, args in self.actions:
            getattr(tools, name)(*args)
        return {"claim_success": self.claim_success, "done": self.done, "tokens": self.tokens}


def agent_fix_and_execute():
    return ScriptedAgent([("write_file", ("app.py", GOOD_APP)),
                          ("run_execution", ())], claim_success=True)


def agent_fix_checks_only():
    return ScriptedAgent([("write_file", ("app.py", GOOD_APP)),
                          ("run_checks", ())], claim_success=True)


def agent_wrong():
    return ScriptedAgent([("write_file", ("app.py", BAD_APP)),
                          ("run_checks", ())], claim_success=False)


def agent_false_success():
    return ScriptedAgent([("write_file", ("app.py", BAD_APP)),
                          ("run_checks", ())], claim_success=True)
