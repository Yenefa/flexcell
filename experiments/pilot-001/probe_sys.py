import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pilot.agent_fc import system_prompt
print(system_prompt(["search_code", "run_execution", "edit_file"]))
