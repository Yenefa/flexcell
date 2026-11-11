"""Level C-prime with a 3x budget: is the failure cost or capability?

The three Level C failures all ended at the 40k token ceiling, so they cannot tell
us whether the agent would have edited given more room. This run keeps the task,
the model and the tools identical and only raises the budget (150k tokens / 40
iterations), making the proposition falsifiable:

  H: localisation cost is the binding constraint -> with more room the agent still
     never edits, because traversal does not converge on its own.
  H0: the earlier failures were merely truncation -> with more room it edits.
"""
import os, sys, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

if not os.environ.get("FLEXCELL_PILOT_API_KEY"):
    import subprocess as _sp
    _GATE = "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/ci-public-window/scripts/evobot_llm_key.sh"
    os.environ["FLEXCELL_PILOT_API_KEY"] = _sp.run(["bash", _GATE], check=True, capture_output=True, text=True).stdout.strip()

from pilot.agent_fc import FCAgent
from pilot.llm import Chat
from pilot import runner, w5s, w5sc

repo_src = str(HERE.parents[1])
env = {"PILOT_P14_REPO": "/home/ros/flexcell-p14",
       "PILOT_P14_WS": "/home/ros/flexcell-p14-ws",
       "PILOT_P14_SRC": repo_src, "PILOT_HOME": str(HERE)}
os.environ.update(env)

out = Path(sys.argv[1]); arm = sys.argv[2] if len(sys.argv) > 2 else "W5A"
out.mkdir(parents=True, exist_ok=True)
manifest = json.loads((HERE / "manifest.json").read_text())
pkg = Path(repo_src) / "src/flexcell/flexcell_skills"
cfg = pkg / "config/week1.yaml"

TASK_C2 = w5sc.TASK_C + (
    "\nStart by running the scenario once so you see the actual failure, then"
    " locate the defect and fix it. Do not spend turns listing directories.\n")

chat = Chat()
agent = FCAgent(chat, manifest["arms"][arm]["tools"], TASK_C2)
res = runner.run_one(manifest, arm, agent,
                     w5s.build_t_w5s(out / ("tpl-c2b-" + arm), pkg, cfg),
                     out / ("c2b-" + arm),
                     meta={"task": "T-W5SC2-BUDGET", **chat.metadata()},
                     protected=["gate/acceptance.py"],
                     execution_factory=w5s.W5SourceExecution,
                     extra_env=env)
res["llm"] = chat.summary()
(out / "c2b-runs.json").write_text(json.dumps({"task": "T-W5SC2-BUDGET",
                                               "rows": [res]}, indent=2) + "\n",
                                 encoding="utf-8")
print("ARM %s success=%s iters=%s tokens=%s" %
      (arm, res["success"], res["iterations"], chat.tokens))
