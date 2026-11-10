"""P2 reuse test: a DIFFERENT defect class, with the earlier lesson available.

Design (pre-registered in docs/P2_PREREGISTRATION.md):
- defect is on the VERIFY branch, not PLACE (different code, same symptom shape);
- the C15 localisation interface is REMOVED (no suspect_regions), so the only
  difference from the C14 baseline is the experience note in experience/;
- baseline for comparison is C14: same task family, no note, 9 iterations,
  0 edits, list_dir 28.
"""
import os, sys, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

if not os.environ.get("FLEXCELL_PILOT_API_KEY"):
    key = Path.home() / ".config/flexcell/deepseek_api_key"
    if key.is_file():
        os.environ["FLEXCELL_PILOT_API_KEY"] = key.read_text().strip()

from pilot.agent_fc import FCAgent
from pilot.llm import Chat
from pilot import runner, w5s, w5sc

repo_src = str(HERE.parents[1])
env = {"PILOT_P14_REPO": "/home/ros/flexcell-p14",
       "PILOT_P14_WS": "/home/ros/flexcell-p14-ws",
       "PILOT_P14_SRC": repo_src, "PILOT_HOME": str(HERE)}
os.environ.update(env)

out = Path(sys.argv[1]); arm = sys.argv[2] if len(sys.argv) > 2 else "W5A"
note = Path(sys.argv[3]) if len(sys.argv) > 3 else None
out.mkdir(parents=True, exist_ok=True)
manifest = json.loads((HERE / "manifest.json").read_text())
pkg = Path(repo_src) / "src/flexcell/flexcell_skills"
cfg = pkg / "config/week1.yaml"

chat = Chat()
agent = FCAgent(chat, manifest["arms"][arm]["tools"], w5s.TASK2)


class P2Execution(w5s.W5SourceExecution):
    """C15 localisation OFF: the evidence is the plain failure, as in C14."""

    def run_execution(self, episode=True):
        result = super().run_execution(episode=episode)
        try:
            doc = json.loads(result["tail"])
        except Exception:
            return result
        doc.pop("suspect_regions", None)
        result["tail"] = json.dumps(doc)[:2400]
        return result


res = runner.run_one(manifest, arm, agent,
                     w5s.build_t_w5s2(out / ("tpl-p2-" + arm), pkg, cfg,
                                      experience_note=note),
                     out / ("p2-" + arm),
                     meta={"task": "T-W5SC2", **chat.metadata()},
                     protected=["gate/acceptance.py"],
                     execution_factory=P2Execution,
                     extra_env=env)
res["llm"] = chat.summary()
res["experience_note"] = str(note) if note else None
(out / "p2-runs.json").write_text(json.dumps({"task": "T-P2REUSE", "rows": [res]},
                                             indent=2) + "\n", encoding="utf-8")
print("ARM %s success=%s iters=%s tokens=%s note=%s" %
      (arm, res["success"], res["iterations"], chat.tokens, bool(note)))
