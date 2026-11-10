"""Level C-prime: no location hints, but the FIRST turn must run the scenario.

Level C failed by burning the budget on navigation, never reaching evidence.
C-prime keeps the same unguided task text and forces iteration 1 to be
run_execution, so the question becomes: given the real failure output, can the
agent localise and repair the source with no pointer to the file?
"""
import os, sys, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if not os.environ.get("FLEXCELL_PILOT_API_KEY"):
    key_path = os.path.expanduser("~/.config/flexcell/deepseek_api_key")
    if os.path.exists(key_path):
        with open(key_path) as fh:
            os.environ["FLEXCELL_PILOT_API_KEY"] = fh.read().strip()
    else:
        import subprocess as _sp
        out = _sp.run(["wsl", "-d", "Ubuntu-24.04", "--", "bash", "-lc",
                       "cat ~/.config/flexcell/deepseek_api_key"],
                      capture_output=True, text=True)
        os.environ["FLEXCELL_PILOT_API_KEY"] = (out.stdout or "").strip()
from pilot.agent_fc import FCAgent
from pilot.llm import Chat
from pilot import runner, w5s, w5sc

HERE_ABS = str(HERE)
repo_src = str(HERE.parents[1])
env = {"PILOT_P14_REPO": "/home/ros/flexcell-p14",
       "PILOT_P14_WS": "/home/ros/flexcell-p14-ws",
       "PILOT_P14_SRC": repo_src, "PILOT_HOME": HERE_ABS}
os.environ.update(env)
manifest = json.loads((HERE / "manifest.json").read_text())
out = Path(sys.argv[1]); arm = sys.argv[2] if len(sys.argv) > 2 else "W5A"
out.mkdir(parents=True, exist_ok=True)
pkg = Path(repo_src) / "src/flexcell/flexcell_skills"
cfg = pkg / "config/week1.yaml"
chat = Chat()
# deepseek-flash rejects a forced tool_choice in thinking mode
# ("Thinking mode does not support this tool_choice"), so the first action is
# requested in the task text instead. The task still says nothing about WHERE
# the defect is or WHAT the fix is.
TASK_C2 = w5sc.TASK_C + (
    "\nStart by running the scenario once so you see the actual failure, then"
    " locate the defect and fix it. Do not spend turns listing directories.\n")
agent = FCAgent(chat, manifest["arms"][arm]["tools"], TASK_C2)
res = runner.run_one(manifest, arm, agent,
                     w5s.build_t_w5s(out / ("tpl-w5s-" + arm), pkg, cfg),
                     out / ("w5s-" + arm),
                     meta={"task": "T-W5SC2", **chat.metadata()},
                     protected=["gate/acceptance.py"],
                     execution_factory=w5s.W5SourceExecution,
                     extra_env=env)
res["llm"] = chat.summary()
rows = [res]
(out / "w5s-runs.json").write_text(json.dumps({"task": "T-W5SC2", "rows": rows},
                                              indent=2) + "\n", encoding="utf-8")
print("ARM %s success=%s iters=%s tokens=%s" %
      (arm, res["success"], res["iterations"], chat.tokens))
