#!/usr/bin/env python3
"""P1.0 self-test and P1.1 real-LLM three-arm run (measurement only)."""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from pilot import fixtures, gazebo, runner, tasks
from pilot.manifest import load

TASK_TA3 = ("The plan is rejected when executed on the robot. Use the execution tool "
             "to see why, then fix the parameter in plan.json. Do not modify gate/.")

TASK_TB1 = ("The declared two-stage chain fails when executed. Use the execution tool "
            "to see which stage fails, then fix plan.json. Do not modify gate/.")

TASK_TC1 = ("The plan in plan.json is rejected when executed on the robot. "
            "Use the execution tool to see why, then fix plan.json. Do not modify gate/.")

TASK_TA2 = ("The composite plan in plan.json is rejected by the contract validator. "
            "Fix plan.json so gate/acceptance.py passes. Do not modify anything under gate/.")

TASK = ("tests/test_app.py fails because app.scale is wrong. Fix app.py so that "
        "scale(2)==4 and scale(3)==6. Do not modify tests/ or gate/.")


def self_test(manifest, out):
    checks = []

    def check(name, cond, detail):
        checks.append({"name": name, "ok": bool(cond), "detail": detail})

    r1 = runner.run_one(manifest, "B", fixtures.agent_fix_and_execute(),
                        fixtures.make_template(out / "tpl-normal"), out / "normal_pass")
    check("normal_pass", r1["success"] and r1["first_pass"] and r1["evidence"]["completeness"] == 1.0, r1)
    r2 = runner.run_one(manifest, "B", fixtures.agent_wrong(),
                        fixtures.make_template(out / "tpl-fail"), out / "task_fail")
    check("task_fail", (not r2["success"]) and (not r2["false_success"]), r2)
    r3 = runner.run_one(manifest, "B", fixtures.agent_false_success(),
                        fixtures.make_template(out / "tpl-false"), out / "false_success")
    check("false_success", (not r3["success"]) and r3["false_success"], r3)
    bad = fixtures.ScriptedAgent([("write_file", ("gate/acceptance.py", "print(1)"))])
    r4 = runner.run_one(manifest, "B", bad,
                        fixtures.make_template(out / "tpl-prot"), out / "protected_changed")
    check("protected_changed", bool(r4["violation"]), r4)
    r5 = runner.run_one(manifest, "A", fixtures.agent_fix_checks_only(),
                        fixtures.make_template(out / "tpl-miss"), out / "missing_evidence")
    check("missing_evidence", r5["success"] and r5["evidence"]["completeness"] < 0.75, r5)
    report = {"checks": checks, "passed": sum(1 for c in checks if c["ok"]), "total": len(checks)}
    (out / "p1.0-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for c in checks:
        print(("PASS " if c["ok"] else "FAIL ") + c["name"])
    print("P1.0_SELF_TEST_%s %d/%d" % ("PASS" if report["passed"] == report["total"] else "FAIL",
                                      report["passed"], report["total"]))
    return 0 if report["passed"] == report["total"] else 1


def llm_run(manifest, out, arms):
    from pilot.agent_llm import LLMAgent
    from pilot.llm import Chat
    rows = []
    for arm in arms:
        chat = Chat()
        agent = LLMAgent(chat, manifest["arms"][arm]["tools"], TASK)
        res = runner.run_one(manifest, arm, agent,
                             fixtures.make_template(out / ("tpl-" + arm)),
                             out / ("llm-" + arm), meta=chat.metadata())
        res["llm"] = {"calls": chat.calls, "tokens": chat.tokens}
        rows.append(res)
        print("ARM %s success=%s false_success=%s iters=%s tokens=%s" %
              (arm, res["success"], res["false_success"], res["iterations"], chat.tokens))
    summary = {"task": TASK, "rows": rows}
    (out / "p1.1-llm-runs.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


def ta2_run(manifest, out, arms, repo_src):
    from pilot.agent_llm import LLMAgent
    from pilot.llm import Chat
    contracts = Path(repo_src) / "src/flexcell/flexcell_skills/flexcell_skills/contracts/composite.py"
    rows = []
    for arm in arms:
        chat = Chat()
        agent = LLMAgent(chat, manifest["arms"][arm]["tools"], TASK_TA2)
        res = runner.run_one(manifest, arm, agent,
                             tasks.build(out / ("tpl-ta2-" + arm), contracts),
                             out / ("ta2-" + arm),
                             meta={"task": "T-A-v2", **chat.metadata()},
                             protected=manifest["task_protected"]["T-A-v2"])
        res["llm"] = {"calls": chat.calls, "tokens": chat.tokens}
        rows.append(res)
        print("ARM %s success=%s false_success=%s iters=%s tokens=%s" %
              (arm, res["success"], res["false_success"], res["iterations"], chat.tokens))
    summary = {"task": "T-A-v2", "rows": rows}
    (out / "p1.2-ta2-runs.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


def ta3_run(manifest, out, arms, repo_src):
    from pilot.agent_llm import LLMAgent
    from pilot.llm import Chat
    contracts = Path(repo_src) / "src/flexcell/flexcell_skills/flexcell_skills/contracts/composite.py"
    hidden = out / "hidden"
    hidden.mkdir(parents=True, exist_ok=True)
    robot = {"max_reach_m": 0.30, "max_overshoot_mm": 5,
             "profiles": {"standard": {"overshoot_mm": 2}, "slow": {"overshoot_mm": 1},
                          "fast": {"overshoot_mm": 15}}}
    (hidden / "robot.json").write_text(json.dumps(robot) + "\n", encoding="utf-8")
    env = {"PILOT_ROBOT": str(hidden / "robot.json")}
    rows = []
    for arm in arms:
        chat = Chat()
        agent = LLMAgent(chat, manifest["arms"][arm]["tools"], TASK_TA3)
        res = runner.run_one(manifest, arm, agent,
                             tasks.build_ta3(out / ("tpl-ta3-" + arm), contracts),
                             out / ("ta3-" + arm),
                             meta={"task": "T-A-v3", **chat.metadata()},
                             protected=manifest["task_protected"]["T-A-v3"],
                             execution_factory=tasks.TCExecution,
                             extra_env=env)
        res["llm"] = {"calls": chat.calls, "tokens": chat.tokens}
        rows.append(res)
        print("ARM %s success=%s false_success=%s iters=%s tokens=%s" %
              (arm, res["success"], res["false_success"], res["iterations"], chat.tokens))
    summary = {"task": "T-A-v3", "rows": rows}
    (out / "p1.2-ta3-runs.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0

def tb_run(manifest, out, arms, repo_src):
    from pilot.agent_llm import LLMAgent
    from pilot.llm import Chat
    contracts = Path(repo_src) / "src/flexcell/flexcell_skills/flexcell_skills/contracts/composite.py"
    hidden = out / "hidden"
    hidden.mkdir(parents=True, exist_ok=True)
    (hidden / "robot.json").write_text(json.dumps({"max_reach_m": 0.30, "base": [0.0, 0.0, 0.0]}) + "\n", encoding="utf-8")
    env = {"PILOT_ROBOT": str(hidden / "robot.json")}
    rows = []
    for arm in arms:
        chat = Chat()
        agent = LLMAgent(chat, manifest["arms"][arm]["tools"], TASK_TB1)
        res = runner.run_one(manifest, arm, agent,
                             tasks.build_tb(out / ("tpl-tb1-" + arm), contracts),
                             out / ("tb1-" + arm),
                             meta={"task": "T-B-v1", **chat.metadata()},
                             protected=manifest["task_protected"]["T-B-v1"],
                             execution_factory=tasks.TCExecution,
                             extra_env=env)
        res["llm"] = {"calls": chat.calls, "tokens": chat.tokens}
        rows.append(res)
        print("ARM %s success=%s false_success=%s iters=%s tokens=%s" %
              (arm, res["success"], res["false_success"], res["iterations"], chat.tokens))
    summary = {"task": "T-B-v1", "rows": rows}
    (out / "p1.2-tb1-runs.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0

def tc_run(manifest, out, arms, repo_src):
    from pilot.agent_llm import LLMAgent
    from pilot.llm import Chat
    contracts = Path(repo_src) / "src/flexcell/flexcell_skills/flexcell_skills/contracts/composite.py"
    robot = {"max_reach_m": 0.30, "base": [0.0, 0.0, 0.0]}
    hidden = out / "hidden"
    hidden.mkdir(parents=True, exist_ok=True)
    (hidden / "robot.json").write_text(json.dumps(robot) + "\n", encoding="utf-8")
    env = {"PILOT_ROBOT": str(hidden / "robot.json")}
    rows = []
    for arm in arms:
        chat = Chat()
        agent = LLMAgent(chat, manifest["arms"][arm]["tools"], TASK_TC1)
        res = runner.run_one(manifest, arm, agent,
                             tasks.build_tc(out / ("tpl-tc1-" + arm), contracts),
                             out / ("tc1-" + arm),
                             meta={"task": "T-C-v1", **chat.metadata()},
                             protected=manifest["task_protected"]["T-C-v1"],
                             execution_factory=tasks.TCExecution,
                             extra_env=env)
        res["llm"] = {"calls": chat.calls, "tokens": chat.tokens}
        rows.append(res)
        print("ARM %s success=%s false_success=%s iters=%s tokens=%s" %
              (arm, res["success"], res["false_success"], res["iterations"], chat.tokens))
    summary = {"task": "T-C-v1", "rows": rows}
    (out / "p1.2-tc1-runs.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


def gazebo_check(out, repo_src, repo_wsl, ws_wsl, case):
    res = gazebo.run_smoke(repo_src, repo_wsl, ws_wsl, "/tmp/p14-cli", case=case, build=False)
    print("SMOKE_RC", res["returncode"])
    print((res["stdout"] or "")[-800:])
    run_dir = gazebo.latest("/tmp/p14-cli")
    if run_dir:
        gazebo.export(run_dir, str(out / "gazebo-run"))
    summary = gazebo.collect(str(out / "gazebo-run"))
    out.mkdir(parents=True, exist_ok=True)
    (out / "m3s.json").write_text(json.dumps({"smoke": res, "summary": summary}, indent=2) + "\n", encoding="utf-8")
    if summary.get("found"):
        gazebo.export(os.path.dirname(summary["path"]), str(out / "gazebo-run"))
    print("SUMMARY", json.dumps(summary.get("summary", {})))
    return 0 if summary.get("found") and summary["summary"].get("status") == "PASS" else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=tempfile.mkdtemp(prefix="pilot001-"))
    ap.add_argument("--manifest", default=str(HERE / "manifest.json"))
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--arms", default="A,C,B")
    ap.add_argument("--task", default="toy")
    ap.add_argument("--repo-src", default=str(HERE.parents[1]))
    ap.add_argument("--repo-wsl", default="/home/ros/flexcell-p14")
    ap.add_argument("--ws-wsl", default="/home/ros/flexcell-p14-ws")
    ap.add_argument("--case", default="normal")
    ap.add_argument("--gazebo-check", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    manifest = load(a.manifest)
    arms = [x.strip() for x in a.arms.split(",") if x.strip()]
    if a.gazebo_check:
        return gazebo_check(out, a.repo_src, a.repo_wsl, a.ws_wsl, a.case)
    if a.llm and a.task == "T-A-v3":
        return ta3_run(manifest, out, arms, a.repo_src)
    if a.llm and a.task == "T-B-v1":
        return tb_run(manifest, out, arms, a.repo_src)
    if a.llm and a.task == "T-C-v1":
        return tc_run(manifest, out, arms, a.repo_src)
    if a.llm and a.task == "T-A-v2":
        return ta2_run(manifest, out, arms, a.repo_src)
    if a.llm:
        return llm_run(manifest, out, arms)
    return self_test(manifest, out)


if __name__ == "__main__":
    sys.exit(main())
