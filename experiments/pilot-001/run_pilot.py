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

from pilot import fixtures, gazebo, gazebo_task, runner, tasks
from pilot.manifest import load

TASK_W5E2B = ("The two-object task fails: the second object destination (zone_2) "
              "is out of reach; the normal task still works. The defect is a single "
              "value in config/week1.yaml. gate/ is read-only and does not need to be "
              "inspected. Fix config/week1.yaml so BOTH tasks verify.")

TASK_W5E2 = ("The two-object task fails because the second object destination "
             "(zone_2) is out of reach; the normal task still works. Fix "
             "config/week1.yaml so that BOTH the two-object task and the normal task "
             "verify on the real stack. gate/ is read-only.")

TASK_W5 = ("The workcell aborts on a recoverable grasp failure (error 30) even "
           "though one recovery attempt is available. Fix skill/recovery.py so the "
           "target scenario reaches DONE, without breaking existing behaviour. "
           "gate/ and tests/test_regression.py are read-only. Use run_execution to "
           "see the failure and run_checks for the regression suite.")

TASK_TG3C = ("The regrasp task fails. Diagnose the cause from the execution "
             "telemetry and fix plan.json. Do not modify gate/.")
TASK_TG3W = (TASK_TG3C + "\n\nPrior experience (transferred from an earlier task): PLACE "
             "failures with ERR_MOTION_FAILED were caused by an unreachable "
             "destination; 0.20 <= hypot(x, y) < 0.30 worked.")

TASK_TG4 = ("The two-object task fails while placing the SECOND object because "
            "zone_2 is out of reach (arm reaches strictly below 0.30 m). The first "
            "object already succeeds. Use run_execution to see the failure, then fix "
            "plan.json. Do not modify gate/.")

TASK_TG3 = ("The robot fails during the regrasp scenario because the place pose is out "
            "of reach (arm reaches strictly below 0.30 m). Use run_execution to see the "
            "failure, then fix plan.json. Do not modify gate/.")

TASK_TG2 = ("The real robot fails because the place pose is too close to the base. "
            "Valid poses are 0.12 m to 0.30 m from the base. Use run_execution to see "
            "the failure, then fix plan.json. Do not modify gate/.")

TASK_TG1 = ("The real robot fails because place_pose is out of reach. Use run_execution "
            "to see the failure. IMPORTANT: after a failed execution you MUST include a "
            "write_file action for plan.json in the SAME reply. Do not modify gate/.")

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


def w5e2b_run(manifest, out, arms, repo_src):
    from pilot.agent_fc import FCAgent
    from pilot.llm import Chat
    from pilot import w5e2
    env = {"PILOT_P14_REPO": "/home/ros/flexcell-p14",
           "PILOT_P14_WS": "/home/ros/flexcell-p14-ws",
           "PILOT_P14_SRC": repo_src, "PILOT_HOME": str(HERE)}
    os.environ.update(env)
    config_src = Path(repo_src) / "src/flexcell/flexcell_skills/config/week1.yaml"
    rows = []
    for arm in arms:
        chat = Chat()
        agent = FCAgent(chat, manifest["arms"][arm]["tools"], TASK_W5E2B)
        res = runner.run_one(manifest, arm, agent,
                             w5e2.build_t_w5e2b(out / ("tpl-w5e2b-" + arm), config_src),
                             out / ("w5e2b-" + arm),
                             meta={"task": "T-W5E2B", **chat.metadata()},
                             protected=["gate/acceptance.py"],
                             execution_factory=w5e2.W5E2Execution,
                             extra_env=env)
        res["llm"] = {"calls": chat.calls, "tokens": chat.tokens}
        rows.append(res)
        print("ARM %s success=%s false_success=%s iters=%s tokens=%s" %
              (arm, res["success"], res["false_success"], res["iterations"], chat.tokens))
    (out / "w5e2b-runs.json").write_text(json.dumps({"task": "T-W5E2B", "rows": rows}, indent=2) + "\n", encoding="utf-8")
    return 0

def w5e2_run(manifest, out, arms, repo_src):
    from pilot.agent_fc import FCAgent
    from pilot.llm import Chat
    from pilot import w5e2
    env = {"PILOT_P14_REPO": "/home/ros/flexcell-p14",
           "PILOT_P14_WS": "/home/ros/flexcell-p14-ws",
           "PILOT_P14_SRC": repo_src,
           "PILOT_HOME": str(HERE)}
    os.environ.update({"PILOT_P14_REPO": env["PILOT_P14_REPO"],
                       "PILOT_P14_WS": env["PILOT_P14_WS"],
                       "PILOT_P14_SRC": env["PILOT_P14_SRC"],
                       "PILOT_HOME": env["PILOT_HOME"]})
    config_src = Path(repo_src) / "src/flexcell/flexcell_skills/config/week1.yaml"
    rows = []
    for arm in arms:
        chat = Chat()
        agent = FCAgent(chat, manifest["arms"][arm]["tools"], TASK_W5E2)
        res = runner.run_one(manifest, arm, agent,
                             w5e2.build_t_w5e2(out / ("tpl-w5e2-" + arm), config_src),
                             out / ("w5e2-" + arm),
                             meta={"task": "T-W5E2", **chat.metadata()},
                             protected=["gate/acceptance.py"],
                             execution_factory=w5e2.W5E2Execution,
                             extra_env=env)
        res["llm"] = {"calls": chat.calls, "tokens": chat.tokens}
        rows.append(res)
        print("ARM %s success=%s false_success=%s iters=%s tokens=%s" %
              (arm, res["success"], res["false_success"], res["iterations"], chat.tokens))
    (out / "w5e2-runs.json").write_text(json.dumps({"task": "T-W5E2", "rows": rows}, indent=2) + "\n", encoding="utf-8")
    return 0

def w5_run(manifest, out, arms, repo_src):
    from pilot.agent_fc import FCAgent
    from pilot.llm import Chat
    from pilot import w5
    rows = []
    for arm in arms:
        chat = Chat()
        agent = FCAgent(chat, manifest["arms"][arm]["tools"], TASK_W5)
        res = runner.run_one(manifest, arm, agent,
                             w5.build_t_w5(out / ("tpl-w5-" + arm)),
                             out / ("w5-" + arm),
                             meta={"task": "T-W5", **chat.metadata()},
                             protected=["gate/sim.py", "gate/acceptance.py", "gate/run_regression.py", "tests/test_regression.py"],
                             execution_factory=w5.W5Execution)
        res["llm"] = {"calls": chat.calls, "tokens": chat.tokens}
        rows.append(res)
        print("ARM %s success=%s false_success=%s iters=%s tokens=%s" %
              (arm, res["success"], res["false_success"], res["iterations"], chat.tokens))
    (out / "w5-runs.json").write_text(json.dumps({"task": "T-W5", "rows": rows}, indent=2) + "\n", encoding="utf-8")
    return 0

def tg3_transfer_run(manifest, out, arms, repo_src, warm):
    from pilot.agent_fc import FCAgent
    from pilot.llm import Chat
    env = {"PILOT_P14_REPO": "/home/ros/flexcell-p14",
           "PILOT_P14_WS": "/home/ros/flexcell-p14-ws",
           "PILOT_P14_SRC": repo_src, "PYTHONPATH": str(HERE)}
    task_id = "T-G3W" if warm else "T-G3C"
    prompt = TASK_TG3W if warm else TASK_TG3C
    rows = []
    for arm in arms:
        chat = Chat()
        agent = FCAgent(chat, manifest["arms"][arm]["tools"], prompt)
        res = runner.run_one(manifest, arm, agent,
                             gazebo_task.build_tg3_transfer(out / ("tpl-" + task_id + "-" + arm), warm=warm),
                             out / (task_id + "-" + arm),
                             meta={"task": task_id, **chat.metadata()},
                             protected=[],
                             execution_factory=gazebo_task.GazeboTaskExecution,
                             extra_env=env)
        res["llm"] = {"calls": chat.calls, "tokens": chat.tokens}
        rows.append(res)
        print("ARM %s success=%s iters=%s tokens=%s" % (arm, res["success"], res["iterations"], chat.tokens))
    (out / (task_id + "-runs.json")).write_text(json.dumps({"task": task_id, "rows": rows}, indent=2) + "\n", encoding="utf-8")
    return 0

def tg4_run(manifest, out, arms, repo_src):
    from pilot.agent_fc import FCAgent
    from pilot.llm import Chat
    env = {"PILOT_P14_REPO": "/home/ros/flexcell-p14",
           "PILOT_P14_WS": "/home/ros/flexcell-p14-ws",
           "PILOT_P14_SRC": repo_src,
           "PYTHONPATH": str(HERE)}
    rows = []
    for arm in arms:
        chat = Chat()
        agent = FCAgent(chat, manifest["arms"][arm]["tools"], TASK_TG4)
        res = runner.run_one(manifest, arm, agent,
                             gazebo_task.build_tg4(out / ("tpl-tg4-" + arm)),
                             out / ("tg4-" + arm),
                             meta={"task": "T-G4", **chat.metadata()},
                             protected=[],
                             execution_factory=gazebo_task.GazeboTaskExecution,
                             extra_env=env)
        res["llm"] = {"calls": chat.calls, "tokens": chat.tokens}
        rows.append(res)
        print("ARM %s success=%s false_success=%s iters=%s tokens=%s" %
              (arm, res["success"], res["false_success"], res["iterations"], chat.tokens))
    (out / "p1.4-tg4-runs.json").write_text(json.dumps({"task": "T-G4", "rows": rows}, indent=2) + "\n", encoding="utf-8")
    return 0

def tg3_run(manifest, out, arms, repo_src):
    from pilot.agent_fc import FCAgent
    from pilot.llm import Chat
    env = {"PILOT_P14_REPO": "/home/ros/flexcell-p14",
           "PILOT_P14_WS": "/home/ros/flexcell-p14-ws",
           "PILOT_P14_SRC": repo_src,
           "PYTHONPATH": str(HERE)}
    rows = []
    for arm in arms:
        chat = Chat()
        agent = FCAgent(chat, manifest["arms"][arm]["tools"], TASK_TG3)
        res = runner.run_one(manifest, arm, agent,
                             gazebo_task.build_tg3(out / ("tpl-tg3-" + arm)),
                             out / ("tg3-" + arm),
                             meta={"task": "T-G3", **chat.metadata()},
                             protected=[],
                             execution_factory=gazebo_task.GazeboTaskExecution,
                             extra_env=env)
        res["llm"] = {"calls": chat.calls, "tokens": chat.tokens}
        rows.append(res)
        print("ARM %s success=%s false_success=%s iters=%s tokens=%s" %
              (arm, res["success"], res["false_success"], res["iterations"], chat.tokens))
    (out / "p1.4-tg3-runs.json").write_text(json.dumps({"task": "T-G3", "rows": rows}, indent=2) + "\n", encoding="utf-8")
    return 0

def tg2_run(manifest, out, arms, repo_src):
    from pilot.agent_llm import LLMAgent
    from pilot.agent_fc import FCAgent
    from pilot.llm import Chat
    env = {"PILOT_P14_REPO": "/home/ros/flexcell-p14",
           "PILOT_P14_WS": "/home/ros/flexcell-p14-ws",
           "PILOT_P14_SRC": repo_src,
           "PYTHONPATH": str(HERE)}
    rows = []
    for arm in arms:
        chat = Chat()
        tools = manifest["arms"][arm]["tools"]
        agent = FCAgent(chat, tools, TASK_TG2)
        res = runner.run_one(manifest, arm, agent,
                             gazebo_task.build_tg2(out / ("tpl-tg2-" + arm)),
                             out / ("tg2-" + arm),
                             meta={"task": "T-G2", **chat.metadata()},
                             protected=[],
                             execution_factory=gazebo_task.GazeboTaskExecution,
                             extra_env=env)
        res["llm"] = {"calls": chat.calls, "tokens": chat.tokens}
        rows.append(res)
        print("ARM %s success=%s false_success=%s iters=%s tokens=%s" %
              (arm, res["success"], res["false_success"], res["iterations"], chat.tokens))
    (out / "p1.4-tg2-runs.json").write_text(json.dumps({"task": "T-G2", "rows": rows}, indent=2) + "\n", encoding="utf-8")
    return 0

def tg_run(manifest, out, arms, repo_src, agent_kind="json"):
    from pilot.agent_llm import LLMAgent
    from pilot.agent_fc import FCAgent
    from pilot.llm import Chat
    env = {"PILOT_P14_REPO": "/home/ros/flexcell-p14",
           "PILOT_P14_WS": "/home/ros/flexcell-p14-ws",
           "PILOT_P14_SRC": repo_src,
           "PYTHONPATH": str(HERE)}
    rows = []
    for arm in arms:
        chat = Chat()
        tools = manifest["arms"][arm]["tools"]
        agent = (FCAgent(chat, tools, TASK_TG1)
                 if agent_kind == "fc" else
                 LLMAgent(chat, manifest["arms"][arm]["tools"], TASK_TG1))
        res = runner.run_one(manifest, arm, agent,
                             gazebo_task.build_tg(out / ("tpl-tg1-" + arm)),
                             out / ("tg1-" + arm),
                             meta={"task": "T-G1", **chat.metadata()},
                             protected=[],
                             execution_factory=gazebo_task.GazeboTaskExecution,
                             extra_env=env)
        res["llm"] = {"calls": chat.calls, "tokens": chat.tokens}
        rows.append(res)
        print("ARM %s success=%s false_success=%s iters=%s tokens=%s" %
              (arm, res["success"], res["false_success"], res["iterations"], chat.tokens))
    (out / "p1.4-tg1-runs.json").write_text(json.dumps({"task": "T-G1", "rows": rows}, indent=2) + "\n", encoding="utf-8")
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
    ap.add_argument("--agent", choices=["json", "fc"], default="json")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    manifest = load(a.manifest)
    arms = [x.strip() for x in a.arms.split(",") if x.strip()]
    if a.llm and a.task == "T-W5E2B":
        return w5e2b_run(manifest, out, arms, a.repo_src)
    if a.llm and a.task == "T-W5E2":
        return w5e2_run(manifest, out, arms, a.repo_src)
    if a.llm and a.task == "T-W5":
        return w5_run(manifest, out, arms, a.repo_src)
    if a.llm and a.task in ("T-G3C", "T-G3W"):
        return tg3_transfer_run(manifest, out, arms, a.repo_src, warm=(a.task == "T-G3W"))
    if a.llm and a.task == "T-G4":
        return tg4_run(manifest, out, arms, a.repo_src)
    if a.llm and a.task == "T-G3":
        return tg3_run(manifest, out, arms, a.repo_src)
    if a.llm and a.task == "T-G2":
        return tg2_run(manifest, out, arms, a.repo_src)
    if a.llm and a.task == "T-G1":
        return tg_run(manifest, out, arms, a.repo_src, a.agent)
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
