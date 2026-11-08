"""Frozen experiment manifest: load, validate, hash."""
import hashlib
import json
from pathlib import Path

REQUIRED = ("pilot", "commit", "arms", "budget", "protected", "tasks")


class ManifestError(ValueError):
    pass


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def load(path):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED if k not in doc]
    if missing:
        raise ManifestError("missing manifest keys: %s" % missing)
    if set(doc["arms"]) != {"A", "C", "B"}:
        raise ManifestError("arms must be exactly A, C, B")
    return doc


def seal(doc):
    """Return the sealed copy (adds a digest) and refuse if already sealed wrong."""
    sealed = dict(doc)
    sealed["manifest_sha256"] = digest({k: v for k, v in doc.items() if k != "manifest_sha256"})
    return sealed


def verify_seal(doc):
    claimed = doc.get("manifest_sha256")
    if not claimed:
        raise ManifestError("manifest is not sealed")
    actual = digest({k: v for k, v in doc.items() if k != "manifest_sha256"})
    if claimed != actual:
        raise ManifestError("manifest digest mismatch: %s != %s" % (claimed, actual))
    return True
