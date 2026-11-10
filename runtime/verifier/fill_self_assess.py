#!/usr/bin/env python3
"""Fill the missing self-assessments, with the RAW reply saved on failure.

WHY THE SECOND TRY EXISTS: the first pass produced 12 of 32 and 20 'no JSON in reply'
errors, with no raw text kept - so the cause was unknown. A harness that discards the
evidence of its own failure cannot be debugged. This version stores every raw reply and
retries, and it records WHY a parse failed instead of raising.
"""
import json
import os
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WT / "experiments" / "pilot-001"))

# MEASURED: with the default 2048-token budget this reasoning model spends the whole
# budget thinking and returns EMPTY content, which then parses as "no JSON" and, worse,
# silently leaves agent_claimed_success at its default False. 8192 returns a reply.
os.environ.setdefault("FLEXCELL_PILOT_MAX_TOKENS", "8192")

from pilot.llm import Chat                       # noqa: E402
import importlib.util                            # noqa: E402

spec = importlib.util.spec_from_file_location(
    "sa", WT / "runtime" / "verifier" / "self_assess.py")
sa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sa)

BATCHES = [("/tmp/evobot-pair16", "recovery_public16"),
           ("/tmp/evobot-pair32", "recovery_public32")]


def main():
    chat = Chat()
    ok = fail = skipped = 0
    for base, pubname in BATCHES:
        for d in sorted(Path(base).glob("HO-*")):
            out = d / "self_assessment.json"
            if out.exists() and out.stat().st_size > 0:
                skipped += 1
                continue
            pub = WT / "benchmark" / "held_out" / pubname / (d.name + ".json")
            obs = d / "observation.json"
            if not pub.exists() or not obs.exists():
                print("SKIP", d.name, "missing spec/obs")
                fail += 1
                continue
            task = json.loads(pub.read_text(encoding="utf-8"))
            plan = json.loads((d / "plan.json").read_text(encoding="utf-8"))
            observation = json.loads(obs.read_text(encoding="utf-8"))
            zones = {z["name"]: z["pose"] for z in task["zones"]}
            user = sa.build_user(task["instruction"], plan, observation, zones)
            raw = ""
            payload = None
            for attempt in (1, 2):
                try:
                    reply = chat.chat([{"role": "system", "content": sa.SYSTEM},
                                       {"role": "user", "content": user}])
                except Exception as exc:                  # noqa: BLE001
                    raw = "CHAT_ERROR: %s" % exc
                    continue
                if isinstance(reply, dict):
                    raw = reply.get("content") or ""
                elif isinstance(reply, tuple):
                    raw = reply[0] or ""
                else:
                    raw = str(reply)
                try:
                    verdict = sa.parse(raw)
                    payload = {"task_id": task["task_id"],
                               "success": bool(verdict.get("success")),
                               "because": str(verdict.get("because", ""))[:400],
                               "raw": raw,
                               "source": "agent_self_assessment",
                               "attempt": attempt}
                    break
                except Exception:                          # noqa: BLE001
                    continue
            if payload is None:
                # keep the evidence of failure rather than throwing it away
                (d / "self_assess_failed.json").write_text(json.dumps(
                    {"task_id": d.name, "raw": raw[:2000],
                     "why": "no parseable JSON in reply"}, indent=2) + "\n",
                    encoding="utf-8")
                print("FAIL", d.name, "| raw starts:", repr(raw[:80]))
                fail += 1
            else:
                out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
                ok += 1
    print()
    print("written:", ok, "already present:", skipped, "failed:", fail)
    return 0


if __name__ == "__main__":
    sys.exit(main())
