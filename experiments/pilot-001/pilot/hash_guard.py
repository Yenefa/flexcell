"""Protected-file hash guard: snapshot, re-check, detect tampering."""
import hashlib
from pathlib import Path


class ProtectedViolation(RuntimeError):
    pass


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class HashGuard:
    def __init__(self, root, protected):
        self.root = Path(root)
        self.protected = list(protected)
        self._snapshot = {}

    def snapshot(self):
        self._snapshot = {}
        for rel in self.protected:
            path = self.root / rel
            if not path.is_file():
                raise ProtectedViolation("protected file missing: %s" % rel)
            self._snapshot[rel] = file_hash(path)
        return dict(self._snapshot)

    def is_protected(self, rel):
        norm = str(Path(rel))
        return any(norm == p or norm.startswith(p.rstrip("/") + "/") for p in self.protected)

    def verify(self):
        if not self._snapshot:
            raise ProtectedViolation("guard was not snapshotted")
        changed = []
        for rel, expected in self._snapshot.items():
            path = self.root / rel
            actual = file_hash(path) if path.is_file() else None
            if actual != expected:
                changed.append({"path": rel, "expected": expected, "actual": actual})
        if changed:
            raise ProtectedViolation("protected files changed: %s" % changed)
        return True
