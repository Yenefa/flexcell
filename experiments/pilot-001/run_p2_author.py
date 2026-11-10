"""P2 item (2): can the agent author its own experience record?

Until now every experience record was written by me. This run asks the agent to
produce one itself, at the end of a real repair, through a dedicated tool whose
schema forces the three things the sprint requires:

  defect_class  - what KIND of defect this was (not which line),
  symptom       - what was observable,
  lesson        - the transferable rule,
  evidence_path - the file it is basing the claim on.

The record is then validated mechanically: the evidence path must exist and the
run must have succeeded. A fabricated record is rejected, not stored.
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
from pilot import runner, w5s

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

TASK_AUTHOR = (w5s.TASK + "\nAfter the gates pass, write the lesson you learned with\n"
               "record_experience: state the DEFECT CLASS (not the line), the SYMPTOM\n"
               "you observed, the transferable LESSON, and the EVIDENCE path. A record\n"
               "that cites evidence which does not exist will be rejected.\n")

tools = list(manifest["arms"][arm]["tools"])
if "record_experience" not in tools:
    tools.append("record_experience")

chat = Chat()
agent = FCAgent(chat, tools, TASK_AUTHOR)


def ask_for_record(agent, toolbox, rec, iteration):
    """One extra agent turn AFTER the gates pass: write the lesson down.

    The runner breaks the moment the verdict flips, so without this hook the agent
    never gets the opportunity - an earlier run "succeeded" with zero
    record_experience calls purely because the loop had already exited.
    """
    prompt = ("Writing-up phase. The repair is done and verified; do not run the "
              "scenario again. Call record_experience exactly once with the DEFECT "
              "CLASS (not a line number), the SYMPTOM you observed, the transferable "
              "LESSON, and the EVIDENCE path you are basing it on (for example "
              "\"telemetry/execution.log\"). A record citing evidence that does not "
              "exist is refused.")
    # Third hypothesis: in a normal turn the agent re-runs the scenario instead of
    # writing up (two runs showed exactly that). So narrow the toolbox for the
    # write-up phase: only the recorder and a read remains. This is a phase change,
    # not a hint - the agent still has to derive every field itself.
    saved = set(toolbox.allowed)
    toolbox.allowed = {"record_experience", "read_file"}
    agent.history.append({"role": "user", "content": prompt})
    try:
        claim = agent.step(toolbox, iteration + 1) or {}
    finally:
        toolbox.allowed = saved
    rec.emit("post_pass", calls=[list(c) for c in toolbox.calls if c],
             tokens=claim.get("tokens"))
    if claim.get("results"):
        rec.emit("transcript", index=iteration + 100,
                 assistant=claim.get("assistant_text", ""),
                 results=claim.get("results", []))


res = runner.run_one(manifest, arm, agent,
                     w5s.build_t_w5s(out / ("tpl-auth-" + arm), pkg, cfg),
                     out / ("auth-" + arm),
                     meta={"task": "T-W5SC2-BUDGET", **chat.metadata()},
                     protected=["gate/acceptance.py"],
                     execution_factory=w5s.W5SourceExecution,
                     extra_env=env,
                     post_pass=ask_for_record)
res["llm"] = chat.summary()
(out / "author-runs.json").write_text(json.dumps({"task": "T-P2AUTHOR", "rows": [res]},
                                               indent=2) + "\n", encoding="utf-8")
print("ARM %s success=%s iters=%s tokens=%s" %
      (arm, res["success"], res["iterations"], chat.tokens))
