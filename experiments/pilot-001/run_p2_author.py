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

# Fourth hypothesis: telling the agent to write up AFTER finishing did not work three
# times. So make the write-up part of the DELIVERABLE itself, stated in the task from
# the start, and have the harness refuse to treat the run as complete until a record
# exists. Same information, different framing: a required output rather than a
# follow-up chore.
TASK_AUTHOR = (w5s.TASK + "\nThe task is NOT complete until you have called\n"
               "record_experience once. Deliverables: (1) the three gates pass, and\n"
               "(2) an experience record with the DEFECT CLASS (not the line), the\n"
               "SYMPTOM observed, the transferable LESSON, and the EVIDENCE path.\n"
               "A record citing evidence that does not exist is refused.\n")

tools = list(manifest["arms"][arm]["tools"])
if "record_experience" not in tools:
    tools.append("record_experience")

chat = Chat()
agent = FCAgent(chat, tools, TASK_AUTHOR)


def ask_for_record(agent, toolbox, rec, iteration):
    """Extra turns until a record exists (max 3), because the task declares the
    record a deliverable. If it never appears, the run is reported as not meeting
    its deliverables rather than quietly passing on gates alone.
    """
    for attempt in range(1, 4):
        has = (toolbox.workspace / "experience" / "agent_authored.json").exists()
        if has:
            rec.emit("post_pass", attempt=attempt, recorded=True)
            return
        prompt = ("Deliverable 2 is still missing: no experience record exists. "
                  "Call record_experience now with defect_class, symptom, lesson and "
                  "an evidence_path that exists in this workspace.")
        agent.history.append({"role": "user", "content": prompt})
        saved = set(toolbox.allowed)
        toolbox.allowed = {"record_experience", "read_file"}
        try:
            claim = agent.step(toolbox, iteration + attempt) or {}
        finally:
            toolbox.allowed = saved
        rec.emit("post_pass", attempt=attempt,
                 calls=[list(c) for c in toolbox.calls if c],
                 tokens=claim.get("tokens"))
        if claim.get("results"):
            rec.emit("transcript", index=iteration + 100 + attempt,
                     assistant=claim.get("assistant_text", ""),
                     results=claim.get("results", []))
    rec.emit("post_pass", attempt="exhausted",
             recorded=(toolbox.workspace / "experience" / "agent_authored.json").exists())

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
