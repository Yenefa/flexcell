"""Read-only dispatch probes and explicit action terminals (#252).

Source/config checks do not exercise ROS. Their process check is explicitly N/A;
Gazebo callers must supply owned process IDs and readiness commands. No probe
starts, kills, cleans, or adopts another experiment's processes.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

SUCCESS = "SUCCESS"
TYPED_FAILURE = "TYPED_FAILURE"
TIMEOUT = "TIMEOUT"
NO_RESPONSE = "NO_RESPONSE"
CONFIRMED = (SUCCESS, TYPED_FAILURE)


class UnconfirmedAction(RuntimeError):
    def __init__(self, state, detail):
        if state not in (TIMEOUT, NO_RESPONSE):
            raise ValueError(state)
        self.state = state
        super().__init__(detail)


class Unhealthy(RuntimeError):
    def __init__(self, report):
        self.report = report
        super().__init__("health probe failed: " + ", ".join(report["failures"]))


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(root):
    """Code/data identity, excluding generated caches and execution telemetry."""
    root = Path(root)
    out = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if set(rel.parts) & {"__pycache__", ".pytest_cache", "telemetry"}:
            continue
        if path.is_symlink():
            raise ValueError("symlink in candidate workspace: %s" % rel)
        if path.is_file():
            out[rel.as_posix()] = file_sha(path)
    return out


def tree_sha(root):
    payload = json.dumps(inventory(root), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def checked_run(command, *, cwd=None, timeout=60):
    """A missing result and a typed task failure have different meanings."""
    try:
        return subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise UnconfirmedAction(TIMEOUT, "command timed out: %s" % command[0]) from exc
    except OSError as exc:
        raise UnconfirmedAction(NO_RESPONSE, "command unavailable: %s" % command[0]) from exc


def pytest_terminal(result):
    # pytest 1 means completed tests with typed assertion failures; 2..5 are
    # interruption/internal/usage/no-tests errors, not a completed task result.
    if result.returncode not in (0, 1):
        raise UnconfirmedAction(NO_RESPONSE,
                                "pytest produced no task terminal (exit %s)" % result.returncode)
    return SUCCESS if result.returncode == 0 else TYPED_FAILURE


def gate_terminal(ok, payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("code"), str):
        raise UnconfirmedAction(NO_RESPONSE, "gate returned no typed result")
    if payload["code"] == "GATE_FAILED":
        raise UnconfirmedAction(NO_RESPONSE, "gate failed to produce a task result")
    return SUCCESS if ok else TYPED_FAILURE


def probe(source_root, expected_sha, workspace, *, source_files=None,
          required_files=(), protected=None, editable=(), baseline=None,
          dependencies=("pytest", "yaml"), backend="source_gate",
          owned_pids=(), readiness=()):
    checks, failures = {}, []

    def check(name, ok, **data):
        checks[name] = {"status": "PASS" if ok else "FAIL", **data}
        if not ok:
            failures.append(name)

    try:
        got = checked_run(["git", "rev-parse", "HEAD"], cwd=source_root, timeout=5)
        check("source_sha", got.returncode == 0 and got.stdout.strip() == expected_sha,
              expected=expected_sha, observed=got.stdout.strip())
    except UnconfirmedAction:
        check("source_sha", False, expected=expected_sha)
    drift = []
    for rel, sha in (source_files or {}).items():
        path = Path(source_root) / rel
        if not path.is_file() or path.is_symlink() or file_sha(path) != sha:
            drift.append(rel)
    check("source_files", not drift, changed=drift)
    missing = [name for name in dependencies if importlib.util.find_spec(name) is None]
    check("dependencies", not missing, missing=missing)
    root = Path(workspace)
    try:
        current = inventory(root)
        missing = [p for p in required_files if p not in current]
        changed = [p for p, sha in (protected or {}).items() if current.get(p) != sha]
        if baseline is not None:
            changed += [p for p in set(baseline) | set(current)
                        if current.get(p) != baseline.get(p)
                        and not any(p == e or p.startswith(e.rstrip("/") + "/")
                                    for e in editable)]
        check("workspace", root.is_dir() and not root.is_symlink()
              and not missing and not changed, missing=missing, changed=sorted(set(changed)))
    except (ValueError, OSError) as exc:
        check("workspace", False, error=str(exc))
    if backend == "source_gate":
        checks["ros_gazebo"] = {"status": "NOT_APPLICABLE",
                                "reason": "source/config execution; no ROS/Gazebo action dispatched"}
    elif backend == "gazebo":
        # Ownership/readiness are supplied by the actual launcher. Finding an
        # arbitrary gz or ROS process on the machine does not prove readiness.
        alive = bool(owned_pids)
        for pid in owned_pids:
            try:
                os.kill(pid, 0)
            except (OSError, ValueError):
                alive = False
        check("ros_gazebo_processes", alive, owned_pids=list(owned_pids))
        ready = bool(readiness)
        for command in readiness:
            try:
                result = checked_run(command, timeout=10)
                ready = ready and result.returncode == 0 and bool(result.stdout.strip())
            except UnconfirmedAction:
                ready = False
        check("ros_gazebo_readiness", ready)
    else:
        check("backend", False, backend=backend)
    return {"at": time.time(), "backend": backend, "healthy": not failures,
            "checks": checks, "failures": failures}


def require_healthy(report):
    if not report.get("healthy"):
        raise Unhealthy(report)


def safe_probe(*args, **kwargs):
    """Probe errors are unhealthy results, so the archive path still executes."""
    try:
        return probe(*args, **kwargs)
    except Exception as exc:
        return {"at": time.time(), "backend": kwargs.get("backend", "source_gate"),
                "healthy": False, "checks": {}, "failures": ["PROBE_ERROR"],
                "error": "%s: %s" % (type(exc).__name__, exc)}
