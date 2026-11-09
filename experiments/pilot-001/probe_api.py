import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
with open(os.path.expanduser("~/.config/flexcell/deepseek_api_key")) as fh:
    os.environ["FLEXCELL_PILOT_API_KEY"] = fh.read().strip()
from pilot.llm import Chat
c = Chat()
tools = [{"type": "function", "function": {
    "name": "emit",
    "description": "Emit the answer.",
    "parameters": {"type": "object",
                   "properties": {"text": {"type": "string"}},
                   "required": ["text"]}}}]
try:
    r = c.chat([{'role': 'user', 'content': 'Call emit with text=OK'}], tools=tools)
    print('RESP:', str(r)[:300])
except Exception as e:
    print('ERR:', type(e).__name__, str(e)[:280])
print('META:', c.summary())
