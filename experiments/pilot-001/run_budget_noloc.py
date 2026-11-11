"""3x budget, localisation OFF: is the Level C failure cost or capability?

The three Level C failures all ended at the 40k token ceiling, so they cannot say
whether the agent would have edited given room. This run keeps the task, model and
tools identical AND removes suspect_regions (the C15 localisation), while raising
the budget to 150k tokens / 40 iterations. Falsifiable:

  H  : localisation cost binds -> traversal does not converge even with 3.75x room,
       so the run still never edits.
  H0 : earlier failures were merely truncation -> with room it edits.
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


class NoLocExecution(w5s.W5SourceExecution):
    """C15 localisation removed: the evidence is the plain failure, as in C14."""

    def run_execution(self, episode=True):
        result = super().run_execution(episode=episode)
        try:
            doc = json.loads(result["tail"])
        except Exception:
            return result
        doc.pop("suspect_regions", None)
        result["tail"] = json.dumps(doc)[:2400]
        return result


chat = Chat()
agent = FCAgent(chat, manifest["arms"][arm]["tools"], TASK_C2)
res = runner.run_one(manifest, arm, agent,
                     w5s.build_t_w5s(out / ("tpl-bnl-" + arm), pkg, cfg),
                     out / ("bnl-" + arm),
                     meta={"task": "T-W5SC2-BUDGET", **chat.metadata()},
                     protected=["gate/acceptance.py"],
                     execution_factory=NoLocExecution,
                     extra_env=env)
res["llm"] = chat.summary()
(out / "bnl-runs.json").write_text(json.dumps({"task": "T-W5SC2-BUDGET",
                                              "rows": [res]}, indent=2) + "\n",
                                encoding="utf-8")
print("ARM %s success=%s iters=%s tokens=%s" %
      (arm, res["success"], res["iterations"], chat.tokens))
