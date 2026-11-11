import os, sys, json, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import subprocess as _sp
_GATE = "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/ci-public-window/scripts/evobot_llm_key.sh"
os.environ["FLEXCELL_PILOT_API_KEY"] = _sp.run(["bash", _GATE], check=True, capture_output=True, text=True).stdout.strip()
from pilot.llm import Chat
c = Chat()
tools = [{"type": "function", "function": {"name": "run_execution",
          "description": "Run the scenario.", "parameters": {"type": "object", "properties": {}}}}]
try:
    r = c.chat([{"role": "user", "content": "Run the scenario."}], tools=tools,
               tool_choice={"type": "function", "function": {"name": "run_execution"}})
    print("OK", r)
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read().decode()[:400])
