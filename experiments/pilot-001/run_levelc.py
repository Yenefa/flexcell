"""Level C runner: same harness, less-guided task text."""
import os, sys, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
with open(os.path.expanduser("~/.config/flexcell/deepseek_api_key")) as fh:
    os.environ["FLEXCELL_PILOT_API_KEY"] = fh.read().strip()
import run_pilot
from pilot import w5sc
w5sc.install()
manifest = json.loads((HERE / "manifest.json").read_text())
out = Path(sys.argv[1])
arm = sys.argv[2] if len(sys.argv) > 2 else "W5A"
out.mkdir(parents=True, exist_ok=True)
print("LEVEL C TASK TEXT:")
print(w5sc.TASK_C)
rc = run_pilot.w5s_run(manifest, out, [arm], str(HERE.parents[1]))
print("RC=", rc)
