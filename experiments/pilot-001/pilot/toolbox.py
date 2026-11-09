"""Per-arm tool permissions; protected paths are write-refused."""
from pathlib import Path

from .hash_guard import ProtectedViolation


class ToolPermissionError(PermissionError):
    pass


class ToolBox:
    """Tools visible to an agent, gated by the arm's allowed set."""

    def __init__(self, arm, allowed, workspace, guard, judge_verdict_path, execution):
        self.arm = arm
        self.allowed = set(allowed)
        self.workspace = Path(workspace)
        self.guard = guard
        self.judge_verdict_path = Path(judge_verdict_path)
        self.execution = execution
        self.calls = []

    def _need(self, name):
        if name not in self.allowed:
            raise ToolPermissionError("tool %r not permitted in arm %s" % (name, self.arm))

    def _inside(self, rel):
        path = (self.workspace / rel).resolve()
        if not str(path).startswith(str(self.workspace.resolve())):
            raise ToolPermissionError("path escapes workspace: %s" % rel)
        return path

    # ---- tools ----
    def read_file(self, rel, start=None, count=None):
        self._need("read_file")
        self.calls.append(("read_file", rel))
        path = self._inside(rel)
        if path.is_dir():
            return "directory %s:\n%s" % (rel, "\n".join(sorted(p.name for p in path.iterdir())))
        text = path.read_text(encoding="utf-8", errors="replace")
        if start is None and count is None:
            return text
        lines = text.splitlines()
        first = max(1, int(start or 1))
        last = len(lines) if count is None else min(len(lines), first + int(count) - 1)
        numbered = ["%5d| %s" % (no, lines[no - 1]) for no in range(first, last + 1)]
        return "lines %d-%d of %d\n%s" % (first, last, len(lines), "\n".join(numbered))

    def list_dir(self, rel="."):
        self._need("list_dir")
        self.calls.append(("list_dir", rel))
        path = self._inside(rel)
        if not path.is_dir():
            raise NotADirectoryError("%s is not a directory" % rel)
        return "\n".join(sorted(p.name + ("/" if p.is_dir() else "") for p in path.iterdir()))

    def write_file(self, rel, content):
        self._need("write_file")
        if self.guard.is_protected(rel):
            self.calls.append(("write_file", rel, "REFUSED_PROTECTED"))
            raise ProtectedViolation("refused to write protected path: %s" % rel)
        path = self._inside(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        self.calls.append(("write_file", rel))
        return True

    def edit_file(self, rel, old, new):
        self._need("edit_file")
        if self.guard.is_protected(rel):
            self.calls.append(("edit_file", rel, "REFUSED_PROTECTED"))
            raise ProtectedViolation("refused to edit protected path: %s" % rel)
        path = self._inside(rel)
        text = path.read_text(encoding="utf-8")
        count = text.count(old)
        if count != 1:
            raise ValueError("edit_file needs exactly one match, found %d" % count)
        path.write_text(text.replace(old, new), encoding="utf-8")
        self.calls.append(("edit_file", rel))
        return True

    def run_checks(self):
        self._need("run_checks")
        self.calls.append(("run_checks",))
        return self.execution.run_checks()

    def run_execution(self, episode=True):
        self._need("run_execution")
        self.calls.append(("run_execution", bool(episode)))
        return self.execution.run_execution(episode=episode)
    def search_code(self, pattern, path=".", max_hits=60):
        """Regex search inside workspace text files; returns path:line: text."""
        import re
        self._need("search_code")
        root = (self.workspace / path).resolve()
        if not str(root).startswith(str(self.workspace.resolve())):
            raise ToolPermissionError("path escapes workspace: %s" % path)
        try:
            rx = re.compile(pattern)
        except re.error as exc:
            return "ERROR: bad regex: %s" % exc
        hits = []
        for file in sorted(root.rglob("*")):
            if not file.is_file() or "__pycache__" in str(file) or file.suffix not in (".py", ".yaml", ".yml", ".md", ".txt", ".json"):
                continue
            try:
                for no, line in enumerate(file.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    if rx.search(line):
                        hits.append("%s:%d: %s" % (file.relative_to(self.workspace.resolve()), no, line.strip()[:160]))
                        if len(hits) >= max_hits:
                            return "\n".join(hits)
            except OSError:
                continue
        return "\n".join(hits) if hits else "(no matches)"


    def read_telemetry(self):
        self._need("read_telemetry")
        self.calls.append(("read_telemetry",))
        return self.execution.telemetry()

    def read_diagnosis(self):
        self._need("read_diagnosis")
        self.calls.append(("read_diagnosis",))
        from .diagnosis import derive
        return derive(self.judge_verdict_path)

    def read_verification(self):
        self._need("read_verification")
        self.calls.append(("read_verification",))
        if not self.judge_verdict_path.is_file():
            return None
        return self.judge_verdict_path.read_text(encoding="utf-8")
