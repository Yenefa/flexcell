"""Independent judge: runs the acceptance command, never trusts agent claims."""
import json
import subprocess
import sys
from pathlib import Path


class Judge:
    def __init__(self, workspace, acceptance, env=None, timeout=120):
        self.workspace = Path(workspace)
        self.acceptance = acceptance
        self.env = dict(env) if env else None
        self.timeout = timeout

    def evaluate(self):
        proc = subprocess.run(
            [sys.executable, self.acceptance],
            cwd=str(self.workspace),
            capture_output=True,
            text=True,
            timeout=self.timeout,
            env={**__import__("os").environ, **self.env} if self.env else None,
        )
        verdict = {
            "passed": False,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
        }
        for line in reversed(proc.stdout.strip().splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                verdict.update(payload)
                break
        verdict["passed"] = bool(verdict.get("passed")) and proc.returncode == 0
        target = self.workspace / "verdict.json"
        target.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
        return verdict
