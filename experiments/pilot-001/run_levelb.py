"""Level B runner: load the API key, then drive one T-W5S arm."""
import os, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import subprocess as _sp
_GATE = "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/ci-public-window/scripts/evobot_llm_key.sh"
os.environ["FLEXCELL_PILOT_API_KEY"] = _sp.run(["bash", _GATE], check=True, capture_output=True, text=True).stdout.strip()
import run_pilot
import json, tempfile
manifest = json.loads((HERE / "manifest.json").read_text())
out = Path(sys.argv[1])
arm = sys.argv[2] if len(sys.argv) > 2 else "W5A"
out.mkdir(parents=True, exist_ok=True)
rc = run_pilot.w5s_run(manifest, out, [arm], str(HERE.parents[1]))
print("RC=", rc)
