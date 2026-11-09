"""One-arm runner: tool gating, budget, independent judging, metrics row."""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .evidence import collect
from .hash_guard import HashGuard, ProtectedViolation
from .judge import Judge
from .manifest import digest
from .recorder import Recorder
from .toolbox import ToolBox, ToolPermissionError

ACCEPTANCE = {"T-A-v2": "gate/acceptance.py", "T-C-v1": "gate/acceptance.py",
              "T-B-v1": "gate/acceptance.py", "T-A-v3": "gate/acceptance.py", "T-G2": "gate/acceptance.py", "T-G3": "gate/acceptance.py", "T-G4": "gate/acceptance.py", "T-G3C": "gate/acceptance.py", "T-G3W": "gate/acceptance.py", "T-W5": "gate/acceptance.py"}


class Execution:
    """Deterministic execution surface: unit checks + (fake) robot execution."""

    def __init__(self, workspace, extra_env=None):
        self.workspace = Path(workspace)
        self.execution_s = 0.0
        self.extra_env = dict(extra_env) if extra_env else None

    def run_checks(self):
        started = time.monotonic()
        env = dict(os.environ)
        env["PYTHONPATH"] = str(self.workspace) + os.pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "tests"],
            cwd=str(self.workspace), capture_output=True, text=True, timeout=120,
            env={**env, **(self.extra_env or {})})
        self.execution_s += time.monotonic() - started
        return {"returncode": proc.returncode,
                "tail": (proc.stdout or "")[-2000:]}

    def run_execution(self, episode=True):
        started = time.monotonic()
        argv = [sys.executable, "gate/sim.py"] + ([] if episode else ["--no-episode"])
        proc = subprocess.run(argv, cwd=str(self.workspace),
                              capture_output=True, text=True, timeout=180,
                              env={**os.environ, **(self.extra_env or {})})
        self.execution_s += time.monotonic() - started
        return {"returncode": proc.returncode, "tail": (proc.stdout or "")[-2000:]}

    def telemetry(self):
        path = self.workspace / "telemetry" / "execution.log"
        if not path.is_file():
            return "(no telemetry)"
        return path.read_text(encoding="utf-8")[-4000:]


def run_one(manifest, arm, agent, template, out_dir, meta=None, protected=None,
            execution_factory=None, extra_env=None):
    out = Path(out_dir)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    ws = out / "workspace"
    shutil.copytree(template, ws)

    rec = Recorder(out)
    guard = HashGuard(ws, protected if protected is not None else manifest["protected"])
    guard.snapshot()
    execution = execution_factory(ws) if execution_factory else Execution(ws, extra_env)
    if extra_env and hasattr(execution, "extra_env"):
        execution.extra_env = dict(extra_env)
    task_name = (meta or {}).get("task")
    budget = manifest.get("task_budget", {}).get(task_name, manifest["budget"])
    toolbox = ToolBox(arm, manifest["arms"][arm]["tools"], ws, guard,
                      ws / "verdict.json", execution)
    judge = Judge(ws, ACCEPTANCE.get(meta.get("task", "") if meta else "", "gate/acceptance.py"),
                  env=extra_env, timeout=int(budget.get("judge_timeout_s", 120)))

    rec.emit("run_start", arm=arm, task=manifest.get("pilot"), tools=sorted(toolbox.allowed))
    verdict = {"passed": False}
    violation = None
    claim_success = False
    iterations = 0
    first_pass = False
    tokens = 0
    agent_seconds = 0.0

    for it in range(1, int(budget["max_iterations"]) + 1):
        iterations = it
        agent_started = time.monotonic()
        try:
            claim = agent.step(toolbox, it) or {}
        except ProtectedViolation as exc:
            violation = str(exc)
            rec.emit("violation", reason=violation)
            break
        except ToolPermissionError as exc:
            rec.emit("tool_denied", reason=str(exc))
            claim = {}
        finally:
            elapsed = time.monotonic() - agent_started
            agent_seconds += elapsed
            rec.emit("agent_step_s", seconds=round(elapsed, 6))
        tokens += int(claim.get("tokens", 0))
        if tokens > int(budget["max_tokens"]):
            rec.emit("budget_exceeded", tokens=tokens)
            break
        claim_success = bool(claim.get("claim_success", claim_success))
        rec.emit("iteration", index=it, claim_success=claim_success,
                 calls=list(toolbox.calls))

        if not any(c and c[0] == "run_execution" for c in toolbox.calls):
            # execution is optional (A arm); still record an A-side observation
            pass
        verdict = judge.evaluate()
        rec.emit("verdict", index=it, passed=verdict["passed"])
        if verdict["passed"]:
            first_pass = it == 1
            break
        if claim.get("done"):
            break

    if violation is None:
        try:
            guard.verify()
        except ProtectedViolation as exc:
            violation = str(exc)
            rec.emit("violation", reason=violation)

    if violation is None:
        verdict = judge.evaluate()

    fingerprint = {
        "commit": manifest["commit"],
        "manifest_sha256": digest({k: v for k, v in manifest.items() if k != "manifest_sha256"}),
        "arm": arm,
        "workspace_sha256": digest(sorted(
            (p.relative_to(ws).as_posix(), p.stat().st_size)
            for p in ws.rglob("*") if p.is_file())),
    }
    (ws / "fingerprint.json").write_text(json.dumps(fingerprint, indent=2) + "\n", encoding="utf-8")

    evidence = collect(ws, out)
    success = bool(verdict.get("passed")) and violation is None
    result = {
        "arm": arm,
        "meta": meta or {},
        "success": success,
        "first_pass": bool(first_pass and success),
        "iterations": iterations,
        "claim_success": claim_success,
        "false_success": bool(claim_success and not success),
        "violation": violation,
        "cost": {
            "tokens": tokens,
            "agent_s": round(agent_seconds, 4),
            "execution_s": round(execution.execution_s, 4),
        },
        "evidence": evidence,
        "verdict": verdict,
        "run_dir": str(out),
    }
    rec.write_json("result.json", result)
    rec.emit("run_end", success=success, violation=violation)
    return result
