#!/usr/bin/env python3
"""Re-collect self-assessments with the corrected prompt, WITHOUT destroying the old ones.

The previous assessment is the evidence of the defect, so it is preserved as
self_assessment_v1.json and the corrected one is self_assessment_v2.json. Overwriting the
old file would erase the very evidence that justified the fix.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("FLEXCELL_PILOT_MAX_TOKENS", "16384")
WT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WT / "experiments" / "pilot-001"))

spec = importlib.util.spec_from_file_location(
    "sa", WT / "runtime" / "verifier" / "self_assess.py")
sa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sa)
from pilot.llm import Chat                        # noqa: E402

BATCHES = [("/tmp/evobot-pair16", "recovery_public16"),
           ("/tmp/evobot-pair32", "recovery_public32")]


def main():
    chat = Chat()
    ok = fail = skip = 0
    for base, pubname in BATCHES:
        for d in sorted(Path(base).glob("HO-*")):
            old = d / "self_assessment.json"
            keep = d / "self_assessment_v1.json"
            if old.exists() and not keep.exists():
                old.rename(keep)
            out = d / "self_assessment_v4.json"
            if out.exists():
                skip += 1
                continue
            pub = WT / "benchmark" / "held_out" / pubname / (d.name + ".json")
            obs = d / "observation.json"
            plan = d / "plan.json"
            if not (pub.exists() and obs.exists() and plan.exists()):
                print("SKIP", d.name)
                fail += 1
                continue
            task = json.loads(pub.read_text(encoding="utf-8"))
            user = sa.build_user(task["instruction"],
                                 json.loads(plan.read_text(encoding="utf-8")),
                                 json.loads(obs.read_text(encoding="utf-8")),
                                 {z["name"]: z["pose"] for z in task["zones"]})
            payload = None
            raw = ""
            for _ in (1, 2):
                try:
                    r = chat.chat([{"role": "system", "content": sa.SYSTEM},
                                   {"role": "user", "content": user}])
                except Exception as exc:                   # noqa: BLE001
                    raw = "CHAT_ERROR: %s" % exc
                    continue
                raw = r.get("content") if isinstance(r, dict) else str(r)
                try:
                    v = sa.parse(raw)
                except Exception:                          # noqa: BLE001
                    continue
                payload = {"task_id": task["task_id"], "success": bool(v.get("success")),
                           "because": str(v.get("because", ""))[:400], "raw": raw,
                           "source": "agent_self_assessment",
                           "prompt_version": "v4_robot_frame_stated"}
                break
            if payload is None:
                (d / "self_assess_v4_failed.json").write_text(
                    json.dumps({"raw": raw[:600]}, indent=2) + "\n", encoding="utf-8")
                print("FAIL", d.name)
                fail += 1
            else:
                out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
                ok += 1
    print()
    print("v4 written:", ok, "skipped:", skip, "failed:", fail)
    return 0


if __name__ == "__main__":
    sys.exit(main())
