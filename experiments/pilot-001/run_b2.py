"""B2 re-run: LLMAgent arm B2 with read_diagnosis actually wired, plus arm B as control."""
import os, sys, json, subprocess as sp
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
_GATE = '/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/ci-public-window/scripts/evobot_llm_key.sh'
os.environ['FLEXCELL_PILOT_API_KEY'] = sp.run(['bash', _GATE], check=True, capture_output=True, text=True).stdout.strip()
import run_pilot
manifest = json.loads((HERE / 'manifest.json').read_text())
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
arms = sys.argv[2].split(',') if len(sys.argv) > 2 else ['B2']
task = sys.argv[3] if len(sys.argv) > 3 else 'ta3'
repo_src = str(HERE.parents[1])
fn = {'ta3': run_pilot.ta3_run, 'tb': run_pilot.tb_run, 'tc': run_pilot.tc_run}[task]
rc = fn(manifest, out, arms, repo_src)
print('RC=', rc)