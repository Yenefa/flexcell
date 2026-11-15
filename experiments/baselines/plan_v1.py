"""Legacy experiment CLI; reusable planning remains in runtime.planner."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from runtime.planner.agent_planner import build_prompt, plan


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) < 2:
        print("usage: plan_v1.py <observation.json> <out.plan.json> [--dry]",
              file=sys.stderr)
        return 2
    obs = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    out = Path(argv[1])
    if "--dry" in argv:
        system, user = build_prompt(obs)
        print(user)
        return 0
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "experiments" / "pilot-001"))
    from pilot.llm import Chat
    chat = Chat()
    agent_plan, problems, raw, usage = plan(obs, chat)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"agent_plan": agent_plan, "problems": problems,
                               "raw_reply": raw, "usage": usage, **chat.metadata()}, indent=2) + "\n",
                   encoding="utf-8")
    print(json.dumps({"problems": problems,
                      "moves": None if agent_plan is None else agent_plan["moves"]},
                     indent=2))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
