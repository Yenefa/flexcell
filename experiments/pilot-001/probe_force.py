import os, sys, json, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
with open(os.path.expanduser("~/.config/flexcell/deepseek_api_key")) as fh:
    os.environ["FLEXCELL_PILOT_API_KEY"] = fh.read().strip()
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
