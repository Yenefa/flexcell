"""Versioned visibility boundary for repair-eval runs (issue #249, parent #248).

WHY
---
The W5 pilot tool layer (experiments/pilot-001/pilot/toolbox.py) authorises by
tool *name* and confines paths with a startswith check.  The W5 execution surface
writes the judge's verdict into the candidate workspace
(experiments/pilot-001/pilot/w5.py:178), and toolbox.read_file will read anything
under that workspace.  A "no feedback" condition could therefore read
verdict.json: the condition label was enforced socially, never structurally.

This module replaces that arrangement for the v0.2 repair-eval path with one
versioned gate:

* separate roots per run -- the *candidate* working copy, the *verdict* of the
  independent judge, the *hidden* material, and optionally the *mismatch* run
  used by the mismatched-feedback condition.  All are resolved once and may not
  overlap;
* a versioned policy (visibility_policy.json) mapping a condition
  (A_STATIC / B_REAL_FEEDBACK / C_MISMATCHED_FEEDBACK / D_GUIDED) to the
  categories it may see.  The loader refuses a document that would let A see
  feedback, diagnosis, verification or hidden answers;
* one path gate used by every read / list / search / write.  It refuses absolute
  paths, ".." traversal, symlink aliases (lexically inside, really outside),
  sealed roots, reserved names and -- best effort -- cross-root hard links, then
  records the attempt for post-hoc counting;
* assert_fresh_run that fails closed when a candidate copy still carries the
  previous round's verdict / telemetry / experience.

WHAT IT IS NOT
--------------
This is a path gate, not a runtime sandbox.  It does not stop a process that
opens the verdict directory by its own path (same-user shell, root, code that
bypasses the tools).  Limitations are listed in docs/repair_eval/VISIBILITY.md.

The module is import-pure: Python standard library only, no ROS, no network, no
model calls, no subprocess.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Mapping, Optional, Sequence

__all__ = [
    "SCHEMA_VERSION",
    "CONDITIONS",
    "CATEGORIES",
    "DEFAULT_CONDITION",
    "POLICY_FILENAME",
    "POLICY_PATH",
    "REASON_CODES",
    "BoundaryError",
    "PolicyError",
    "AccessDenied",
    "StaleArtifact",
    "MaterialUnavailable",
    "ConditionAccess",
    "Policy",
    "load_policy",
    "load_default_policy",
    "RunBoundary",
    "ToolFacade",
    "FeedbackPacket",
    "collect_feedback",
    "visibility_matrix",
    "assert_fresh_run",
    "run_demo",
    "main",
]

SCHEMA_VERSION = "repair-eval-visibility/1"
CONDITIONS = ("A_STATIC", "B_REAL_FEEDBACK", "C_MISMATCHED_FEEDBACK", "D_GUIDED")
CATEGORIES = (
    "static_input",
    "candidate_source",
    "execution_feedback",
    "diagnosis",
    "verification",
    "hidden_answer",
)
FEEDBACK_SOURCES = ("none", "own_run", "mismatch_run")
DEFAULT_CONDITION = "A_STATIC"
POLICY_FILENAME = "visibility_policy.json"
POLICY_PATH = Path(__file__).resolve().with_name(POLICY_FILENAME)

# Categories an agent file tool may address directly.  Names reserved for sealed
# material are refused in these categories even when the file is absent locally.
AGENT_FILE_CATEGORIES = ("static_input", "candidate_source", "execution_feedback")

TEXT_SUFFIXES = (".py", ".yaml", ".yml", ".md", ".txt", ".json", ".toml", ".cfg", ".ini")
SKIP_DIRS = frozenset({".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"})

# Reason codes are stable strings: run records and the paper tables cite them.
POLICY_DENIED = "policy_denied"
RESERVED_NAME = "reserved_name"
ABSOLUTE_PATH = "absolute_path"
PARENT_TRAVERSAL = "parent_traversal"
SYMLINK_ALIAS = "symlink_alias"
OUTSIDE_ROOT = "outside_root"
VERDICT_MATERIAL = "verdict_material"
HIDDEN_MATERIAL = "hidden_material"
HARDLINK_ALIAS = "hardlink_alias"
HARDLINK_UNVERIFIED = "hardlink_unverified"
SEALED_MATERIAL = "sealed_material"
PROTECTED_WRITE = "protected_write"
STALE_ARTIFACT = "stale_artifact"
ROOT_OVERLAP = "root_overlap"
MISSING_MATERIAL = "missing_material"

REASON_CODES = (
    POLICY_DENIED,
    RESERVED_NAME,
    ABSOLUTE_PATH,
    PARENT_TRAVERSAL,
    SYMLINK_ALIAS,
    OUTSIDE_ROOT,
    VERDICT_MATERIAL,
    HIDDEN_MATERIAL,
    HARDLINK_ALIAS,
    SEALED_MATERIAL,
    PROTECTED_WRITE,
    STALE_ARTIFACT,
    ROOT_OVERLAP,
    MISSING_MATERIAL,
)

MAX_ATTEMPTS = 10000
HARDLINK_SCAN_LIMIT = 400
MAX_HASH_BYTES = 1024 * 1024


# --------------------------------------------------------------------------- errors
class BoundaryError(RuntimeError):
    """Base class for every refusal raised by this module."""


class PolicyError(BoundaryError):
    """The policy document or the run configuration is unusable.  Fail closed."""


class AccessDenied(BoundaryError):
    """A path or category read/write was refused by the gate.

    reason is one of REASON_CODES; condition, category and path are the exact
    request that was refused, so a run record can explain the refusal without
    replaying it.
    """

    def __init__(self, reason, operation, path, category=None, condition=None, detail=None):
        self.reason = reason
        self.operation = operation
        self.path = str(path)
        self.category = category
        self.condition = condition
        self.detail = detail
        message = "%s refused %s path %r (reason=%s" % (
            operation, category or "unspecified", str(path), reason)
        if condition:
            message += ", condition=%s" % condition
        message += ")"
        if detail:
            message += ": " + detail
        super().__init__(message)

    def as_dict(self):
        return {
            "reason": self.reason,
            "operation": self.operation,
            "path": self.path,
            "category": self.category,
            "condition": self.condition,
            "detail": self.detail,
        }


class StaleArtifact(BoundaryError):
    """The candidate copy still carries material produced by a previous round."""

    def __init__(self, artifacts, candidate):
        self.artifacts = list(artifacts)
        self.candidate = str(candidate)
        rendered = ", ".join(item["path"] for item in self.artifacts) or "(none reported)"
        super().__init__(
            "candidate copy %s carries %d artifact(s) from an earlier round: %s; "
            "a new run must not inherit previous feedback" % (
                self.candidate, len(self.artifacts), rendered))

    def as_dict(self):
        return {
            "reason": STALE_ARTIFACT,
            "candidate": self.candidate,
            "artifacts": list(self.artifacts),
        }


class MaterialUnavailable(BoundaryError):
    """The read was permitted, but the permitted source holds no such file."""

    def __init__(self, path, category, root):
        self.path = str(path)
        self.category = category
        self.root = str(root)
        super().__init__("%s material %r is absent under %s" % (category, str(path), str(root)))

    def as_dict(self):
        return {
            "reason": MISSING_MATERIAL,
            "path": self.path,
            "category": self.category,
            "root": self.root,
        }


# ---------------------------------------------------------------------- path helpers
def _within(root: Path, path: Path) -> bool:
    """True when path is root or lives below it (both already resolved)."""
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _posix_rel(rel) -> str:
    """Normalise a request to an a/b/c string; never resolves anything."""
    text = str(rel).replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return "" if text in ("", ".") else text


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalise_prefix(prefix: str) -> str:
    """Directory prefixes end in exactly one slash; file entries end in none."""
    value = _posix_rel(prefix)
    if value.endswith("/"):
        return value.rstrip("/") + "/"
    return value


def _split_parts(raw: str) -> list:
    return [part for part in re.split(r"[\\/]+", raw) if part not in ("", ".")]


# -------------------------------------------------------------------------- policy
@dataclass(frozen=True)
class ConditionAccess:
    """What one experimental condition may see, and where its feedback comes from."""

    name: str
    visible: Mapping[str, bool]
    feedback_source: str
    guidance: Optional[str] = None

    @property
    def visible_categories(self) -> frozenset:
        return frozenset(category for category, on in self.visible.items() if on)

    def allows(self, category: str) -> bool:
        return bool(self.visible.get(category, False))

    def as_dict(self):
        return {
            "name": self.name,
            "visible": dict(sorted(self.visible.items())),
            "feedback_source": self.feedback_source,
            "guidance": self.guidance,
            "guidance_sha256": _sha256_text(self.guidance) if self.guidance else None,
        }


@dataclass(frozen=True)
class Policy:
    """A loaded, validated visibility policy."""

    schema_version: str
    policy_id: str
    conditions: Mapping[str, ConditionAccess]
    reserved_names: tuple
    static_prefixes: tuple
    sealed_prefixes: tuple
    paths: Mapping[str, str]
    freshness_forbidden: tuple
    freshness_max_depth: int
    protected_writes: tuple
    guidance_max_chars: int
    diagnosis: Mapping[str, object]
    model_interface: Mapping[str, str]
    raw: Mapping[str, object]

    def condition(self, name: str) -> ConditionAccess:
        try:
            return self.conditions[name]
        except KeyError:
            raise PolicyError(
                "unknown condition %r; this policy defines %s"
                % (name, ", ".join(sorted(self.conditions)))) from None

    def allows(self, condition: str, category: str) -> bool:
        return self.condition(condition).allows(category)

    def visible_categories(self, condition: str) -> frozenset:
        return self.condition(condition).visible_categories

    def guidance_for(self, condition: str) -> Optional[str]:
        return self.condition(condition).guidance

    def fingerprint(self) -> str:
        """Stable digest of the policy document, recorded with every run."""
        canonical = json.dumps(self.raw, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


TOP_LEVEL_KEYS = frozenset({
    "schema_version", "policy_id", "comment", "reserved_names", "static_prefixes",
    "sealed_prefixes", "paths", "freshness", "protected_writes", "guidance_max_chars",
    "diagnosis", "conditions", "model_interface",
})
CONDITION_REQUIRED_KEYS = frozenset({"visible", "feedback_source"})
CONDITION_OPTIONAL_KEYS = frozenset({"guidance", "comment"})


def _require_keys(doc, keys, where):
    if not isinstance(doc, dict):
        raise PolicyError("%s must be a JSON object" % where)
    missing = sorted(set(keys) - set(doc))
    unexpected = sorted(set(doc) - set(keys))
    if missing or unexpected:
        raise PolicyError("%s has missing=%s unexpected=%s keys" % (where, missing, unexpected))
    return doc


def _require_optional_keys(doc, required, optional, where):
    if not isinstance(doc, dict):
        raise PolicyError("%s must be a JSON object" % where)
    missing = sorted(set(required) - set(doc))
    unexpected = sorted(set(doc) - set(required) - set(optional))
    if missing or unexpected:
        raise PolicyError("%s has missing=%s unexpected=%s keys" % (where, missing, unexpected))
    return doc


def _require_int(value, where, minimum=1, maximum=None):
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise PolicyError("%s must be an integer >= %d" % (where, minimum))
    if maximum is not None and value > maximum:
        raise PolicyError("%s must be an integer <= %d" % (where, maximum))
    return value


def _require_string(value, where):
    if not isinstance(value, str) or not value.strip():
        raise PolicyError("%s must be a non-empty string" % where)
    return value


def _require_string_list(value, where, allow_empty=False):
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise PolicyError("%s must be a list of non-empty strings" % where)
    if not value and not allow_empty:
        raise PolicyError("%s must not be empty" % where)
    return tuple(value)


def _require_relative(value, where):
    text = _require_string(value, where)
    if text.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", text):
        raise PolicyError("%s must be a relative path, got %r" % (where, text))
    if ".." in _split_parts(text):
        raise PolicyError("%s must not contain '..', got %r" % (where, text))
    return _posix_rel(text)


def _parse_conditions(doc, guidance_max_chars):
    if not isinstance(doc, dict):
        raise PolicyError("conditions must be a JSON object")
    missing = [name for name in CONDITIONS if name not in doc]
    unexpected = sorted(set(doc) - set(CONDITIONS))
    if missing or unexpected:
        raise PolicyError(
            "conditions must be exactly %s (missing=%s unexpected=%s)"
            % (list(CONDITIONS), missing, unexpected))
    parsed = {}
    for name in CONDITIONS:
        where = "conditions.%s" % name
        body = _require_optional_keys(
            doc[name],
            required=CONDITION_REQUIRED_KEYS,
            optional=CONDITION_OPTIONAL_KEYS,
            where=where,
        )
        visible = body["visible"]
        if not isinstance(visible, dict):
            raise PolicyError("%s.visible must be a JSON object" % where)
        if sorted(visible) != sorted(CATEGORIES):
            raise PolicyError(
                "%s.visible must declare exactly %s" % (where, list(CATEGORIES)))
        flags = {}
        for category in CATEGORIES:
            if not isinstance(visible[category], bool):
                raise PolicyError("%s.visible.%s must be true/false" % (where, category))
            flags[category] = visible[category]
        source = body["feedback_source"]
        if source not in FEEDBACK_SOURCES:
            raise PolicyError("%s.feedback_source must be one of %s" % (where, list(FEEDBACK_SOURCES)))
        if (source != "none") != flags["execution_feedback"]:
            raise PolicyError(
                "%s: feedback_source %r disagrees with execution_feedback=%s"
                % (where, source, flags["execution_feedback"]))
        guidance = body.get("guidance")
        if guidance is not None:
            _require_string(guidance, where + ".guidance")
            if len(guidance) > guidance_max_chars:
                raise PolicyError(
                    "%s.guidance is %d chars, over guidance_max_chars=%d"
                    % (where, len(guidance), guidance_max_chars))
            if not flags["execution_feedback"] or source != "own_run":
                raise PolicyError(
                    "%s.guidance may only extend the run's own real feedback" % where)
        parsed[name] = ConditionAccess(
            name=name,
            visible=dict(flags),
            feedback_source=source,
            guidance=guidance,
        )
    return parsed


def _check_invariants(conditions):
    """Refuse documents whose condition table contradicts the experiment design."""
    static = conditions["A_STATIC"]
    leaked = [category for category in ("execution_feedback", "diagnosis", "verification", "hidden_answer")
              if static.visible[category]]
    if leaked:
        raise PolicyError(
            "A_STATIC must not expose %s: the no-feedback condition cannot see any "
            "feedback, diagnosis, verdict or hidden answer" % ", ".join(leaked))
    guided = [name for name, condition in conditions.items() if condition.guidance is not None]
    if len(guided) > 1:
        raise PolicyError(
            "at most one condition may carry guidance; found %s -- otherwise two "
            "conditions would deliver the same intervention" % ", ".join(sorted(guided)))
    for name, condition in conditions.items():
        if condition.visible["hidden_answer"]:
            raise PolicyError(
                "condition %s exposes hidden_answer; hidden material is never agent visible" % name)


def load_policy(path=POLICY_PATH) -> Policy:
    """Load and validate a visibility policy document.

    Every refusal here is a PolicyError: a policy that cannot prove the
    no-feedback condition is sealed must not be used to run an experiment.
    """
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PolicyError("cannot read policy %s: %s" % (path, exc)) from exc
    except json.JSONDecodeError as exc:
        raise PolicyError("policy %s is not valid JSON: %s" % (path, exc)) from exc
    _require_keys(raw, TOP_LEVEL_KEYS, "policy")
    schema = raw["schema_version"]
    if schema != SCHEMA_VERSION:
        raise PolicyError(
            "unsupported schema_version %r; this build understands %r"
            % (schema, SCHEMA_VERSION))
    policy_id = _require_string(raw["policy_id"], "policy_id")
    guidance_max_chars = _require_int(raw["guidance_max_chars"], "guidance_max_chars", 1, 10000)

    reserved_names = _require_string_list(raw["reserved_names"], "reserved_names")
    for name in reserved_names:
        if "/" in name or "\\" in name:
            raise PolicyError("reserved_names entries must be file names, got %r" % name)

    static_prefixes = _require_string_list(raw["static_prefixes"], "static_prefixes")
    static_prefixes = tuple(_normalise_prefix(prefix) for prefix in static_prefixes)

    sealed_prefixes = _require_string_list(raw["sealed_prefixes"], "sealed_prefixes")
    sealed_prefixes = tuple(_normalise_prefix(prefix) for prefix in sealed_prefixes)
    for prefix in sealed_prefixes:
        if prefix.strip("/") in ("", "."):
            raise PolicyError(
                "sealed_prefixes must name a path inside the candidate, got %r" % prefix)
    for sealed in sealed_prefixes:
        for static in static_prefixes:
            left, right = sealed.rstrip("/"), static.rstrip("/")
            if left == right or left.startswith(right + "/") or right.startswith(left + "/"):
                raise PolicyError(
                    "sealed_prefixes and static_prefixes overlap at %r/%r: a path is "
                    "either a static input or sealed, never both" % (sealed, static))

    paths_doc = _require_keys(raw["paths"], {"telemetry", "telemetry_prefix", "verdict"}, "paths")
    paths = {
        "telemetry": _require_relative(paths_doc["telemetry"], "paths.telemetry"),
        "telemetry_prefix": _require_relative(paths_doc["telemetry_prefix"], "paths.telemetry_prefix"),
        "verdict": _require_relative(paths_doc["verdict"], "paths.verdict"),
    }
    if not paths["telemetry_prefix"].endswith("/"):
        paths["telemetry_prefix"] += "/"
    if not paths["telemetry"].startswith(paths["telemetry_prefix"]):
        raise PolicyError("paths.telemetry must live under paths.telemetry_prefix")

    freshness_doc = _require_keys(raw["freshness"], {"forbidden", "max_depth"}, "freshness")
    freshness_forbidden = _require_string_list(freshness_doc["forbidden"], "freshness.forbidden")
    freshness_max_depth = _require_int(freshness_doc["max_depth"], "freshness.max_depth", 1, 32)
    forbidden_bare = {entry.rstrip("/") for entry in freshness_forbidden}
    for name in reserved_names:
        if name not in forbidden_bare:
            raise PolicyError(
                "freshness.forbidden must cover the reserved name %r" % name)

    protected_writes = _require_string_list(raw["protected_writes"], "protected_writes")
    for prefix in sealed_prefixes:
        bare = prefix.rstrip("/")
        if not any(entry.rstrip("/") == bare or entry.rstrip("/").startswith(bare + "/")
                   for entry in protected_writes):
            raise PolicyError(
                "sealed path %r must also be listed in protected_writes: sealed material "
                "that stays writable is still tamperable" % prefix)

    diagnosis_doc = _require_keys(
        raw["diagnosis"], {"projection", "truncate_chars", "max_tail_lines"}, "diagnosis")
    diagnosis = {
        "projection": _require_string_list(diagnosis_doc["projection"], "diagnosis.projection"),
        "truncate_chars": _require_int(diagnosis_doc["truncate_chars"], "diagnosis.truncate_chars", 16, 8000),
        "max_tail_lines": _require_int(diagnosis_doc["max_tail_lines"], "diagnosis.max_tail_lines", 1, 200),
    }

    interface = raw["model_interface"]
    if not isinstance(interface, dict) or not interface:
        raise PolicyError("model_interface must be a non-empty JSON object")
    for key, value in interface.items():
        _require_string(value, "model_interface.%s" % key)

    conditions = _parse_conditions(raw["conditions"], guidance_max_chars)
    _check_invariants(conditions)

    return Policy(
        schema_version=schema,
        policy_id=policy_id,
        conditions=conditions,
        reserved_names=reserved_names,
        static_prefixes=static_prefixes,
        sealed_prefixes=sealed_prefixes,
        paths=paths,
        freshness_forbidden=freshness_forbidden,
        freshness_max_depth=freshness_max_depth,
        protected_writes=protected_writes,
        guidance_max_chars=guidance_max_chars,
        diagnosis=diagnosis,
        model_interface=dict(interface),
        raw=raw,
    )


def load_default_policy() -> Policy:
    """Load the shipped POLICY_PATH document."""
    return load_policy(POLICY_PATH)


def visibility_matrix(policy: Policy) -> dict:
    """Condition -> sorted visible categories.  Used by records, tests and the demo."""
    return {name: sorted(policy.visible_categories(name)) for name in CONDITIONS}


# ------------------------------------------------------------------------ boundary
class RunBoundary:
    """The gate between one condition and one run's directories.

    run_root holds candidate_dir, verdict_dir and hidden_dir; they must be
    disjoint.  mismatch_dir is a frozen copy of another finished run and is only
    reachable through the mismatched-feedback condition.

    condition defaults to the most restrictive condition (A_STATIC): a caller that
    forgets to say which condition it is running never gets feedback.
    """

    def __init__(self, policy, run_root, candidate_dir, verdict_dir, hidden_dir,
                 condition=DEFAULT_CONDITION, mismatch_dir=None):
        if not isinstance(policy, Policy):
            raise PolicyError("RunBoundary needs a loaded Policy, got %r" % type(policy).__name__)
        self.policy = policy
        self.condition = self.policy.condition(condition).name
        self.run_root = Path(run_root).resolve()
        self.candidate = Path(candidate_dir).resolve()
        self.verdict = Path(verdict_dir).resolve()
        self.hidden = Path(hidden_dir).resolve()
        self.mismatch = Path(mismatch_dir).resolve() if mismatch_dir is not None else None
        self.attempts = []
        self.attempts_dropped = 0
        self._validate_roots()

    # -- construction checks -------------------------------------------------
    def _validate_roots(self):
        labelled = (
            ("run_root", self.run_root),
            ("candidate", self.candidate),
            ("verdict", self.verdict),
            ("hidden", self.hidden),
        )
        for label, path in labelled:
            if not path.is_dir():
                raise PolicyError("%s is not a directory: %s" % (label, path))
        for label, path in labelled[1:]:
            if not _within(self.run_root, path):
                raise PolicyError("%s must live inside run_root: %s" % (label, path))
        self._require_disjoint(("candidate", self.candidate), ("verdict", self.verdict))
        self._require_disjoint(("candidate", self.candidate), ("hidden", self.hidden))
        self._require_disjoint(("verdict", self.verdict), ("hidden", self.hidden))
        if self.mismatch is not None:
            if not self.mismatch.is_dir():
                raise PolicyError("mismatch is not a directory: %s" % self.mismatch)
            self._require_disjoint(("candidate", self.candidate), ("mismatch", self.mismatch))
            self._require_disjoint(("verdict", self.verdict), ("mismatch", self.mismatch))
            self._require_disjoint(("hidden", self.hidden), ("mismatch", self.mismatch))

    @staticmethod
    def _require_disjoint(left, right):
        (left_label, left_path), (right_label, right_path) = left, right
        if _within(left_path, right_path) or _within(right_path, left_path):
            raise PolicyError(
                "roots overlap (%s=%s, %s=%s): the candidate copy, the verdict and the "
                "hidden material must not contain each other" % (
                    left_label, left_path, right_label, right_path))

    # -- introspection -------------------------------------------------------
    def visible_categories(self) -> frozenset:
        return self.policy.visible_categories(self.condition)

    def access(self) -> ConditionAccess:
        return self.policy.condition(self.condition)

    def describe(self) -> dict:
        access = self.access()
        return {
            "policy_id": self.policy.policy_id,
            "policy_fingerprint": self.policy.fingerprint(),
            "schema_version": self.policy.schema_version,
            "condition": self.condition,
            "visible_categories": sorted(self.visible_categories()),
            "feedback_source": access.feedback_source,
            "guidance_sha256": _sha256_text(access.guidance) if access.guidance else None,
            "model_interface": dict(self.policy.model_interface),
            "roots": {
                "run_root": str(self.run_root),
                "candidate": str(self.candidate),
                "verdict": str(self.verdict),
                "hidden": str(self.hidden),
                "mismatch": str(self.mismatch) if self.mismatch else None,
            },
        }

    def denials(self) -> list:
        return [entry for entry in self.attempts if entry["decision"] == "deny"]

    def denial_reasons(self) -> list:
        return sorted({entry["reason"] for entry in self.denials() if entry.get("reason")})

    # -- attempt log ---------------------------------------------------------
    def _record(self, operation, rel, category, decision, *, reason=None,
                root=None, resolved=None, detail=None):
        entry = {
            "seq": len(self.attempts) + 1,
            "condition": self.condition,
            "operation": operation,
            "category": category,
            "path": rel,
            "decision": decision,
        }
        if reason:
            entry["reason"] = reason
        if root:
            entry["root"] = root
        if resolved is not None:
            entry["resolved"] = str(resolved)
        if detail:
            entry["detail"] = detail
        if len(self.attempts) < MAX_ATTEMPTS:
            self.attempts.append(entry)
        else:
            self.attempts_dropped += 1
        return entry

    def _deny(self, operation, rel, category, reason, detail=None):
        self._record(operation, rel, category, "deny", reason=reason, detail=detail)
        return AccessDenied(
            reason=reason,
            operation=operation,
            path=rel,
            category=category,
            condition=self.condition,
            detail=detail,
        )

    # -- root routing --------------------------------------------------------
    def _root_for(self, category):
        access = self.access()
        if category in ("execution_feedback", "diagnosis") and access.feedback_source == "mismatch_run":
            return self.mismatch
        if category in ("static_input", "candidate_source", "execution_feedback", "diagnosis"):
            return self.candidate
        if category == "verification":
            return self.verdict
        if category == "hidden_answer":
            return self.hidden
        return None

    def _root_name(self, category):
        root = self._root_for(category)
        if root is None:
            return None
        if root == self.candidate:
            return "candidate"
        if root == self.verdict:
            return "verdict"
        if root == self.hidden:
            return "hidden"
        return "mismatch"

    # -- the gate ------------------------------------------------------------
    def locate_path(self, operation, rel, category, *, record_allow=True):
        """Gate one path request and return the resolved path (no I/O on it)."""
        rel_text = _posix_rel(rel)
        if not self.access().allows(category):
            raise self._deny(
                operation, rel_text, category, POLICY_DENIED,
                "condition %s does not expose %s" % (self.condition, category))
        root = self._root_for(category)
        if root is None:
            raise self._deny(
                operation, rel_text, category, POLICY_DENIED,
                "no directory is wired for category %s" % category)
        # Path shape first: an absolute path or a ".." component is refused as
        # such, whatever the request happens to be named.  The reserved-name
        # rule then covers sealed names that are requested by a plain relative
        # path (for example verdict.json inside a candidate root).
        resolved = self._resolve(operation, rel_text, category, root)
        self._refuse_sealed_prefix(operation, rel_text, category)
        self._refuse_reserved_name(operation, rel_text, category)
        self._refuse_sealed_root(operation, rel_text, category, resolved)
        self._refuse_hardlink_alias(operation, rel_text, category, resolved)
        self._refuse_resolved_material(operation, rel_text, category, resolved)
        if record_allow:
            self._record(operation, rel_text, category, "allow", root=self._root_name(category),
                         resolved=resolved)
        return resolved

    def _refuse_sealed_prefix(self, operation, rel, category):
        """Sealed prefixes are unreadable for every condition, evaluator source included.

        They stay physically inside the candidate because the gate subprocess is
        executed there; sealing is a tool-facade property, not a filesystem one.
        """
        if self._root_for(category) != self.candidate:
            return
        for prefix in self.policy.sealed_prefixes:
            bare = prefix.rstrip("/")
            if rel == bare or rel.startswith(bare + "/"):
                raise self._deny(
                    operation, rel, category, SEALED_MATERIAL,
                    "%r is sealed in every condition: the evaluator source and its "
                    "thresholds stay in the candidate only so the gate subprocess can "
                    "run them" % prefix)

    def _refuse_reserved_name(self, operation, rel, category):
        if category not in AGENT_FILE_CATEGORIES:
            return
        name = rel.rsplit("/", 1)[-1] if rel else ""
        if name and name in self.policy.reserved_names:
            raise self._deny(
                operation, rel, category, RESERVED_NAME,
                "%r is reserved for sealed material and is never readable through a file tool" % name)

    def _resolve(self, operation, rel, category, root):
        raw = rel
        if "\x00" in raw:
            raise self._deny(operation, raw, category, OUTSIDE_ROOT, "NUL byte in path")
        if raw.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", raw):
            raise self._deny(
                operation, raw, category, ABSOLUTE_PATH,
                "absolute paths are never resolved inside a run root")
        parts = _split_parts(raw)
        if ".." in parts:
            raise self._deny(
                operation, raw, category, PARENT_TRAVERSAL,
                "'..' components are refused; use a path relative to the allowed root")
        relative = Path(*parts) if parts else Path(".")
        lexical = Path(os.path.normpath(os.path.join(str(root), str(relative))))
        if not _within(root, lexical):
            raise self._deny(operation, raw, category, OUTSIDE_ROOT,
                             "path leaves %s" % root)
        resolved = (root / relative).resolve()
        if _within(root, resolved):
            return resolved
        raise self._deny(
            operation, raw, category, SYMLINK_ALIAS,
            "path is lexically inside %s but resolves to %s" % (root, resolved))

    def _refuse_sealed_root(self, operation, rel, category, resolved):
        if category != "hidden_answer" and _within(self.hidden, resolved):
            raise self._deny(operation, rel, category, HIDDEN_MATERIAL,
                             "resolved into the hidden material root")
        if category != "verification" and _within(self.verdict, resolved):
            raise self._deny(operation, rel, category, VERDICT_MATERIAL,
                             "resolved into the independent verdict root")

    def _refuse_resolved_material(self, operation, rel, category, resolved):
        """Classify the target, not the name used to reach it.

        An internal symlink named code_alias pointing at gate passes every check
        on the requested path, then reads or writes the sealed real file. An alias
        to telemetry lets a no-feedback condition read execution feedback. Every
        check here runs on the resolved target.
        """
        for name, root in (("hidden", self.hidden), ("verdict", self.verdict),
                           ("mismatch", self.mismatch), ("candidate", self.candidate)):
            if root is None or not _within(root, resolved):
                continue
            under = resolved.relative_to(root).as_posix()
            if name == "hidden" and category != "hidden_answer":
                raise self._deny(operation, rel, category, HIDDEN_MATERIAL,
                                 "resolved into the hidden material root")
            if name == "verdict" and category != "verification":
                raise self._deny(operation, rel, category, VERDICT_MATERIAL,
                                 "resolved into the independent verdict root")
            if name == "mismatch" and category not in ("execution_feedback", "diagnosis"):
                raise self._deny(operation, rel, category, POLICY_DENIED,
                                 "resolved into the mismatch-run material root")
            if name != "candidate":
                continue
            for prefix in self.policy.sealed_prefixes:
                bare = prefix.rstrip("/")
                if under == bare or under.startswith(bare + "/"):
                    raise self._deny(operation, rel, category, SEALED_MATERIAL,
                                     "resolved into sealed path %s" % bare)
            if (under.startswith(self.policy.paths["telemetry_prefix"])
                    and not self.access().allows("execution_feedback")):
                raise self._deny(operation, rel, category, POLICY_DENIED,
                                 "resolved into execution feedback this condition cannot read")
            if operation in ("write", "write_file"):
                protected = self._protected_write(under)
                if protected is not None:
                    raise self._deny(operation, rel, category, PROTECTED_WRITE,
                                     "resolved target is protected as %r" % protected)
        return


    def _refuse_hardlink_alias(self, operation, rel, category, resolved):
        try:
            stat = resolved.stat()
        except OSError:
            return  # nothing on disk yet: nothing to link to
        if stat.st_nlink <= 1:
            return
        aliases = [str(path) for path in self._inode_matches(resolved, stat)]
        if aliases:
            raise self._deny(
                operation, rel, category, HARDLINK_ALIAS,
                "file shares an inode with sealed material: %s" % ", ".join(sorted(aliases)))
        self._record(operation, rel, category, "note", reason=HARDLINK_UNVERIFIED,
                     root=self._root_name(category), resolved=resolved)

    def _inode_matches(self, resolved, stat) -> Iterator[Path]:
        """Best effort: find another root's file sharing this inode.

        A cross-root hard link has no path-level signature, so this scans the
        sealed roots (bounded) for the same (st_dev, st_ino).  Mounts that present
        the same inode differently are out of reach; see VISIBILITY.md.
        """
        seen = 0
        for root in (self.verdict, self.hidden, self.mismatch):
            if root is None or not root.is_dir():
                continue
            for entry in _walk_entries(root, max_depth=4):
                seen += 1
                if seen > HARDLINK_SCAN_LIMIT:
                    return
                try:
                    if not entry.is_file(follow_symlinks=False):
                        continue
                    other = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                if (other.st_dev, other.st_ino) == (stat.st_dev, stat.st_ino):
                    yield Path(entry.path)

    # -- material access -----------------------------------------------------
    def category_for(self, rel) -> str:
        """Classify a request as static input, feedback or candidate source."""
        rel_text = _posix_rel(rel)
        for prefix in self.policy.static_prefixes:
            if rel_text == prefix.rstrip("/") or rel_text.startswith(prefix):
                return "static_input"
        if rel_text.startswith(self.policy.paths["telemetry_prefix"]):
            return "execution_feedback"
        return "candidate_source"

    def read_text(self, rel, category, *, missing_ok=False, record_allow=True):
        path = self.locate_path("read", rel, category, record_allow=record_allow)
        if not path.is_file():
            if missing_ok:
                return None
            raise MaterialUnavailable(rel, category, self._root_for(category))
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            if missing_ok:
                return None
            raise MaterialUnavailable(rel, category, self._root_for(category)) from exc

    def list_entries(self, rel, category):
        path = self.locate_path("list", rel, category)
        if not path.is_dir():
            raise MaterialUnavailable(rel, category, self._root_for(category))
        try:
            children = sorted(path.iterdir())
        except OSError as exc:
            raise MaterialUnavailable(rel, category, self._root_for(category)) from exc
        return [child.name + ("/" if child.is_dir() else "") for child in children]

    def write_text(self, rel, text, category="candidate_source"):
        if not isinstance(text, str):
            raise BoundaryError("write_text needs text, got %r" % type(text).__name__)
        rel_text = _posix_rel(rel)
        protected = self._protected_write(rel_text)
        if protected is not None:
            raise self._deny(
                "write", rel_text, category, PROTECTED_WRITE,
                "path is listed in policy.protected_writes as %r" % protected)
        path = self.locate_path("write", rel_text, category)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        except OSError as exc:
            raise BoundaryError("cannot write %s: %s" % (path, exc)) from exc
        return path

    def _protected_write(self, rel):
        for entry in self.policy.protected_writes:
            prefix = entry.rstrip("/")
            if rel == prefix or rel.startswith(prefix + "/"):
                return entry
        return None

    # -- condition channels --------------------------------------------------
    def read_feedback(self) -> str:
        """Raw execution feedback for this condition (own run, or the fixed other run)."""
        return self.read_text(self.policy.paths["telemetry"], "execution_feedback")

    def diagnose(self):
        """Bounded structured projection of the execution feedback.

        The projection is declared by the policy and never reads the verdict
        root: diagnosis is feedback the run produced, not the measurement.
        """
        rel = self.policy.paths["telemetry"]
        text = self.read_text(rel, "diagnosis", missing_ok=True)
        if text is None:
            return None
        projection = self.policy.diagnosis["projection"]
        truncate = int(self.policy.diagnosis["truncate_chars"])
        payload = {
            "source": rel,
            "root": self._root_name("diagnosis"),
            "parses_json": False,
            "doc": None,
            "tail": _tail(text, int(self.policy.diagnosis["max_tail_lines"]), truncate * 4),
        }
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return payload
        if not isinstance(parsed, dict):
            return payload
        payload["parses_json"] = True
        payload["doc"] = {key: _bounded(parsed[key], truncate)
                          for key in projection if key in parsed}
        return payload

    def read_verification(self):
        """Raw independent verdict.  Sealed unless the policy says otherwise."""
        return self.read_text(self.policy.paths["verdict"], "verification", missing_ok=True)

    # -- freshness -----------------------------------------------------------
    def assert_fresh_run(self, candidate_dir=None):
        """Fail closed when the candidate copy carries a previous round's material."""
        candidate = Path(candidate_dir).resolve() if candidate_dir is not None else self.candidate
        if not candidate.is_dir():
            raise PolicyError("candidate is not a directory: %s" % candidate)
        artifacts = scan_freshness(self.policy, candidate)
        if artifacts:
            raise StaleArtifact(artifacts, candidate)
        self._record("assert_fresh_run", ".", "candidate_source", "allow", root="candidate")
        return True


def scan_freshness(policy: Policy, candidate) -> list:
    """List forbidden leftovers under candidate (see policy.freshness)."""
    candidate = Path(candidate).resolve()
    forbidden_files = {entry for entry in policy.freshness_forbidden if not entry.endswith("/")}
    forbidden_dirs = {entry.rstrip("/") for entry in policy.freshness_forbidden if entry.endswith("/")}
    found = []
    for entry in _walk_entries(candidate, max_depth=policy.freshness_max_depth):
        name = entry.name
        is_dir = entry.is_dir(follow_symlinks=False)
        matched = None
        if is_dir and name in forbidden_dirs:
            matched = name + "/"
        elif name in forbidden_files:
            matched = name
        if matched is None:
            continue
        path = Path(entry.path)
        item = {
            "path": path.relative_to(candidate).as_posix(),
            "kind": "symlink" if entry.is_symlink() else ("dir" if is_dir else "file"),
            "forbidden": matched,
        }
        if not is_dir:
            try:
                stat = entry.stat(follow_symlinks=False)
                item["bytes"] = stat.st_size
                if stat.st_size <= MAX_HASH_BYTES:
                    item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                pass
        found.append(item)
    return sorted(found, key=lambda item: item["path"])


def assert_fresh_run(policy, candidate_dir):
    """Module-level convenience wrapper around RunBoundary.assert_fresh_run."""
    artifacts = scan_freshness(policy, candidate_dir)
    if artifacts:
        raise StaleArtifact(artifacts, Path(candidate_dir).resolve())
    return True


def _walk_entries(root: Path, max_depth: int) -> Iterator[os.DirEntry]:
    """Depth-bounded, symlink-safe walk (does not follow directory symlinks)."""
    stack = [(str(root), 0)]
    while stack:
        current, depth = stack.pop()
        try:
            with os.scandir(current) as iterator:
                entries = sorted(iterator, key=lambda item: item.name)
        except OSError:
            continue
        for entry in entries:
            yield entry
            if depth + 1 >= max_depth:
                continue
            if entry.name in SKIP_DIRS:
                continue
            if entry.is_dir(follow_symlinks=False):
                stack.append((entry.path, depth + 1))


def _bounded(value, limit: int):
    if isinstance(value, str):
        return value[:limit]
    rendered = json.dumps(value, sort_keys=True, ensure_ascii=True, default=str)
    return rendered[:limit]


def _tail(text: str, max_lines: int, limit: int) -> str:
    lines = text.splitlines()[-max_lines:]
    return "\n".join(lines)[:limit]


# ---------------------------------------------------------------------- feedback
@dataclass(frozen=True)
class FeedbackPacket:
    """One feedback delivery, with its provenance attached.

    source_run_id names the run the text came from.  mismatched says the text is
    *not* this run's feedback: it comes from the fixed other run named in
    source_run_id, and the packet is still shaped like a real one so the
    condition controls for information content, not for information format.
    """

    source_run_id: str
    condition: str
    sha256: str
    text: str
    mismatched: bool = False
    source_rel: Optional[str] = None
    source_root: Optional[str] = None
    guidance: Optional[str] = None
    guidance_sha256: Optional[str] = None

    @classmethod
    def build(cls, text, *, source_run_id, condition, mismatched=False,
              source_rel=None, source_root=None, guidance=None):
        if not isinstance(text, str) or not text.strip():
            raise BoundaryError(
                "feedback text is empty; a feedback condition must receive real text")
        if not str(source_run_id or "").strip():
            raise BoundaryError("feedback needs the run id its text came from")
        if condition not in CONDITIONS:
            raise BoundaryError("unknown condition %r for a feedback packet" % (condition,))
        if guidance is not None and not str(guidance).strip():
            raise BoundaryError("guidance must be non-empty when present")
        return cls(
            source_run_id=str(source_run_id),
            condition=condition,
            sha256=_sha256_text(text),
            text=text,
            mismatched=bool(mismatched),
            source_rel=source_rel,
            source_root=source_root,
            guidance=guidance,
            guidance_sha256=_sha256_text(guidance) if guidance else None,
        )

    @property
    def bytes(self) -> int:
        return len(self.text.encode("utf-8"))

    def as_dict(self, include_text=True):
        payload = {
            "source_run_id": self.source_run_id,
            "condition": self.condition,
            "sha256": self.sha256,
            "bytes": self.bytes,
            "mismatched": self.mismatched,
            "source_rel": self.source_rel,
            "source_root": self.source_root,
            "guidance_sha256": self.guidance_sha256,
            "guidance": self.guidance,
        }
        if include_text:
            payload["text"] = self.text
        return payload


def collect_feedback(boundary, run_id, mismatch_run_id=None):
    """Build the feedback packet this condition is entitled to.

    Returns None for the no-feedback condition -- None, never an empty string, so
    "no feedback" cannot be confused with "empty feedback".
    """
    access = boundary.access()
    source = access.feedback_source
    if source == "none":
        return None
    telemetry = boundary.policy.paths["telemetry"]
    if source == "own_run":
        text = boundary.read_feedback()
        return FeedbackPacket.build(
            text,
            source_run_id=run_id,
            condition=boundary.condition,
            mismatched=False,
            source_rel=telemetry,
            source_root="candidate",
            guidance=access.guidance,
        )
    if source == "mismatch_run":
        if boundary.mismatch is None:
            raise PolicyError(
                "condition %s needs a mismatch run directory to draw feedback from"
                % boundary.condition)
        if not str(mismatch_run_id or "").strip():
            raise BoundaryError(
                "condition %s must name the run id of the mismatched feedback source"
                % boundary.condition)
        text = boundary.read_feedback()
        return FeedbackPacket.build(
            text,
            source_run_id=mismatch_run_id,
            condition=boundary.condition,
            mismatched=True,
            source_rel=telemetry,
            source_root="mismatch",
        )
    raise PolicyError("unsupported feedback_source %r" % source)


# ------------------------------------------------------------------- tool facade
class ToolFacade:
    """The agent-facing tools; every call goes through the boundary.

    Method names and return shapes follow experiments/pilot-001/pilot/toolbox.py
    so a condition can be swapped in without rewriting agent prompts, but the
    authorisation model changed: the policy decides which categories exist, and
    the boundary decides which paths exist.
    """

    def __init__(self, boundary):
        if not isinstance(boundary, RunBoundary):
            raise BoundaryError("ToolFacade needs a RunBoundary")
        self.boundary = boundary
        self.calls = []

    # -- call bookkeeping ----------------------------------------------------
    def _note(self, tool, argument, outcome):
        self.calls.append({"tool": tool, "argument": argument, "outcome": outcome})

    def _refused(self, tool, argument, exc):
        self._note(tool, argument, "denied:" + exc.reason)
        return exc

    # -- file tools ----------------------------------------------------------
    def read_file(self, rel, start=None, count=None):
        category = self.boundary.category_for(rel)
        try:
            path = self.boundary.locate_path("read_file", rel, category)
        except AccessDenied as exc:
            raise self._refused("read_file", rel, exc)
        if path.is_dir():
            names = sorted(child.name for child in path.iterdir())
            self._note("read_file", rel, "allow:directory")
            return "directory %s:\n%s" % (rel, "\n".join(names))
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            self._note("read_file", rel, "missing")
            raise MaterialUnavailable(rel, category, self.boundary._root_for(category)) from exc
        self._note("read_file", rel, "allow")
        if start is None and count is None:
            return text
        lines = text.splitlines()
        first = max(1, int(start or 1))
        last = len(lines) if count is None else min(len(lines), first + int(count) - 1)
        numbered = ["%5d| %s" % (number, lines[number - 1])
                    for number in range(first, last + 1)]
        return "lines %d-%d of %d\n%s" % (first, last, len(lines), "\n".join(numbered))

    def list_dir(self, rel="."):
        try:
            entries = self.boundary.list_entries(rel, self.boundary.category_for(rel))
        except AccessDenied as exc:
            raise self._refused("list_dir", rel, exc)
        self._note("list_dir", rel, "allow")
        return "\n".join(entries)

    def search_code(self, pattern, path=".", max_hits=60):
        """Regex search over the material this condition may read."""
        try:
            expression = re.compile(pattern)
        except re.error as exc:
            self._note("search_code", pattern, "bad-regex")
            return "ERROR: bad regex: %s" % exc
        category = self.boundary.category_for(path)
        try:
            start = self.boundary.locate_path("search_code", path, category)
        except AccessDenied as exc:
            raise self._refused("search_code", path, exc)
        hits = []
        files = [start] if start.is_file() else sorted(
            candidate for candidate in start.rglob("*") if candidate.is_file())
        for file in files:
            if file.suffix not in TEXT_SUFFIXES:
                continue
            rel = file.relative_to(self.boundary.candidate).as_posix()
            try:
                text = self.boundary.read_text(
                    rel, self.boundary.category_for(rel), record_allow=False)
            except (AccessDenied, MaterialUnavailable):
                continue
            if text is None:
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if expression.search(line):
                    hits.append("%s:%d: %s" % (rel, number, line.strip()[:160]))
                    if len(hits) >= max_hits:
                        self._note("search_code", pattern, "allow:%d" % len(hits))
                        return "\n".join(hits)
        self._note("search_code", pattern, "allow:%d" % len(hits))
        return "\n".join(hits) if hits else "(no matches)"

    def write_file(self, rel, content):
        try:
            self.boundary.write_text(rel, content)
        except AccessDenied as exc:
            raise self._refused("write_file", rel, exc)
        self._note("write_file", rel, "allow")
        return True

    # -- feedback tools ------------------------------------------------------
    def read_telemetry(self):
        try:
            text = self.boundary.read_text(
                self.boundary.policy.paths["telemetry"], "execution_feedback", missing_ok=True)
        except AccessDenied as exc:
            raise self._refused("read_telemetry", "", exc)
        self._note("read_telemetry", "", "allow")
        return text if text is not None else "(no telemetry)"

    def read_diagnosis(self):
        try:
            payload = self.boundary.diagnose()
        except AccessDenied as exc:
            raise self._refused("read_diagnosis", "", exc)
        self._note("read_diagnosis", "", "allow" if payload is not None else "missing")
        return payload

    def read_verification(self):
        try:
            text = self.boundary.read_verification()
        except AccessDenied as exc:
            raise self._refused("read_verification", "", exc)
        self._note("read_verification", "", "allow")
        return text


# ----------------------------------------------------------------------- demo CLI
DEMO_SOURCE = '''"""Recovery decision used by the workcell executor."""


def next_action(outcome, error_code, budget):
    """Return the next step after a skill result."""
    if outcome == 0:
        return "DONE"
    return "ABORT"
'''


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_demo_tree(root: Path) -> dict:
    run_root = root / "run-b"
    candidate = run_root / "candidate"
    verdict = run_root / "verdict"
    hidden = run_root / "hidden"
    other = root / "run-a"
    _write(candidate / "task.md",
           "# demo task\n\nFix skill/recovery.py so a recoverable failure is retried.\n")
    _write(candidate / "gate" / "sim.py", "# frozen gate; the candidate may read, never write\n")
    _write(candidate / "tests" / "test_regression.py", "# frozen regression contract\n")
    _write(candidate / "skill" / "recovery.py", DEMO_SOURCE)
    _write(verdict / "verdict.json", json.dumps(
        {"passed": False, "error_code": 30, "failed_stage": "grasp", "answer": "SEALED"},
        indent=2) + "\n")
    _write(hidden / "answers.txt", "SEALED-ANSWER\n")
    _write(other / "telemetry" / "execution.log", json.dumps(
        {"returncode": 1, "passed": False, "stdout": "run-a: target scenario failed\n"},
        sort_keys=True) + "\n")
    _write(other / "verdict.json", json.dumps({"passed": False, "error_code": 30}) + "\n")
    return {
        "root": root,
        "run_root": run_root,
        "candidate": candidate,
        "verdict": verdict,
        "hidden": hidden,
        "other": other,
    }


def run_demo(policy_path=POLICY_PATH) -> dict:
    """Build a throwaway tree and show allow / refuse / refuse-inheritance.

    Output is deterministic: every reported path is relative to the temporary
    tree, so two demo runs on different machines can be diffed.
    """
    policy = load_policy(policy_path)
    examples = {}
    with tempfile.TemporaryDirectory(prefix="repair-eval-visibility-") as temp:
        tree = _build_demo_tree(Path(temp))
        run_root = tree["run_root"]

        def boundary(condition, **kwargs):
            return RunBoundary(policy, run_root, tree["candidate"], tree["verdict"],
                               tree["hidden"], condition=condition, **kwargs)

        a_boundary = boundary("A_STATIC")
        a_tools = ToolFacade(a_boundary)

        text = a_tools.read_file("skill/recovery.py")
        examples["allowed_read"] = {
            "condition": "A_STATIC",
            "path": "skill/recovery.py",
            "category": "candidate_source",
            "bytes": len(text.encode("utf-8")),
            "sha256": _sha256_text(text),
            "first_line": text.splitlines()[0],
        }

        for label, rel, note in (
            ("refused_reserved_name", "verdict.json",
             "the judge's verdict name is sealed even though the candidate root is readable"),
            ("refused_parent_traversal", "../run-a/verdict.json",
             "'..' is refused before any link or path is resolved"),
        ):
            try:
                a_tools.read_file(rel)
                examples[label] = {"path": rel, "refused": False}
            except AccessDenied as exc:
                examples[label] = dict(exc.as_dict(), refused=True, note=note)

        alias = tree["candidate"] / "alias.txt"
        os.symlink("../verdict/verdict.json", alias)
        try:
            try:
                a_tools.read_file("alias.txt")
                examples["refused_symlink_alias"] = {"path": "alias.txt", "refused": False}
            except AccessDenied as exc:
                examples["refused_symlink_alias"] = dict(
                    exc.as_dict(), refused=True,
                    note="the link is lexically inside the candidate and points at the verdict")
        finally:
            alias.unlink()

        try:
            a_tools.read_telemetry()
            examples["refused_feedback_tool"] = {"tool": "read_telemetry", "refused": False}
        except AccessDenied as exc:
            examples["refused_feedback_tool"] = dict(
                exc.as_dict(), refused=True, tool="read_telemetry",
                note="condition A has no feedback channel at all")

        _write(tree["candidate"] / "telemetry" / "execution.log", json.dumps(
            {"returncode": 1, "passed": False, "stdout": "target scenario failed: expected OBSERVE"},
            sort_keys=True) + "\n")
        b_packet = collect_feedback(boundary("B_REAL_FEEDBACK"), run_id="run-b")
        examples["real_feedback"] = {
            "condition": "B_REAL_FEEDBACK",
            "packet": b_packet.as_dict(include_text=False),
            "text_preview": b_packet.text.splitlines()[0][:120],
            "empty_string_instead_of_none": False,
        }
        a_packet = collect_feedback(a_boundary, run_id="run-b")
        examples["no_feedback"] = {
            "condition": "A_STATIC",
            "packet": None,
            "is_none": a_packet is None,
            "note": "no feedback is None, never an empty string",
        }
        c_packet = collect_feedback(
            boundary("C_MISMATCHED_FEEDBACK", mismatch_dir=tree["other"]),
            run_id="run-b", mismatch_run_id="run-a")
        examples["mismatched_feedback"] = {
            "condition": "C_MISMATCHED_FEEDBACK",
            "packet": c_packet.as_dict(include_text=False),
            "shares_text_with_own_feedback": c_packet.sha256 == b_packet.sha256,
        }
        d_packet = collect_feedback(boundary("D_GUIDED"), run_id="run-b")
        examples["guided_feedback"] = {
            "condition": "D_GUIDED",
            "packet": d_packet.as_dict(include_text=False),
            "guidance_length": len(d_packet.guidance or ""),
            "guidance_max_chars": policy.guidance_max_chars,
            "within_policy_bound": len(d_packet.guidance or "") <= policy.guidance_max_chars,
        }

        stale = run_root / "stale-candidate"
        shutil.copytree(tree["candidate"], stale)
        _write(stale / "verdict.json", json.dumps({"passed": False}) + "\n")
        _write(stale / "experience" / "lesson.json", json.dumps({"lesson": "old"}) + "\n")
        try:
            boundary("B_REAL_FEEDBACK").assert_fresh_run(stale)
            examples["refused_stale_inheritance"] = {"refused": False}
        except StaleArtifact as exc:
            examples["refused_stale_inheritance"] = dict(
                exc.as_dict(), refused=True,
                note="a new run must not inherit the previous round's verdict or experience",
                relative_candidate=Path(exc.candidate).relative_to(run_root).as_posix())

        examples["attempts_recorded"] = {
            "denials": len(a_boundary.denials()),
            "reasons": a_boundary.denial_reasons(),
        }

    return {
        "policy": {
            "policy_id": policy.policy_id,
            "schema_version": policy.schema_version,
            "fingerprint": policy.fingerprint(),
            "model_interface": dict(policy.model_interface),
        },
        "visibility": visibility_matrix(policy),
        "examples": examples,
        "notes": [
            "paths are relative to a throwaway tree created for this demo",
            "a path gate is not a runtime sandbox; see docs/repair_eval/VISIBILITY.md",
        ],
    }


def run_check(args) -> tuple:
    """Audit a real run tree: policy, freshness, one optional read."""
    policy = load_policy(args.policy)
    missing = [flag for flag, value in (
        ("--run-root", args.run_root), ("--candidate", args.candidate),
        ("--verdict", args.verdict), ("--hidden", args.hidden)) if value is None]
    if missing:
        raise SystemExit("missing required options: " + ", ".join(missing))
    try:
        boundary = RunBoundary(policy, args.run_root, args.candidate, args.verdict,
                               args.hidden, condition=args.condition,
                               mismatch_dir=args.mismatch)
    except PolicyError as exc:
        return {"ok": False, "error": {"reason": "policy_error", "detail": str(exc)}}, 2
    payload = {"ok": True, "boundary": boundary.describe()}
    freshness = "not_checked"
    if args.check_freshness:
        try:
            boundary.assert_fresh_run()
            freshness = "fresh"
        except StaleArtifact as exc:
            freshness = "stale"
            payload["ok"] = False
            payload["stale"] = exc.as_dict()
    payload["freshness"] = freshness
    if args.read:
        category = boundary.category_for(args.read)
        try:
            text = boundary.read_text(args.read, category)
            payload["read"] = {
                "path": args.read,
                "category": category,
                "bytes": len(text.encode("utf-8")),
                "sha256": _sha256_text(text),
            }
        except AccessDenied as exc:
            payload["ok"] = False
            payload["read"] = dict(exc.as_dict(), refused=True)
        except MaterialUnavailable as exc:
            payload["read"] = dict(exc.as_dict(), refused=False)
    payload["attempts"] = boundary.attempts
    return payload, (0 if payload["ok"] else 1)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m benchmark.repair_eval.visibility",
        description="Audit the repair-eval visibility boundary offline.")
    parser.add_argument("--demo", action="store_true",
                        help="print the allow / refuse / refuse-inheritance examples")
    parser.add_argument("--policy", type=Path, default=POLICY_PATH,
                        help="policy document (default: the shipped visibility_policy.json)")
    parser.add_argument("--condition", default=DEFAULT_CONDITION, choices=CONDITIONS)
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--verdict", type=Path)
    parser.add_argument("--hidden", type=Path)
    parser.add_argument("--mismatch", type=Path)
    parser.add_argument("--read", help="relative path to read through the gate")
    parser.add_argument("--check-freshness", action="store_true",
                        help="refuse a candidate copy that inherited an earlier round")
    args = parser.parse_args(argv)
    if args.demo or args.run_root is None:
        payload = run_demo(args.policy)
        print(json.dumps(payload, indent=2, sort_keys=False))
        return 0
    try:
        payload, code = run_check(args)
    except PolicyError as exc:
        payload, code = {"ok": False, "error": {"reason": "policy_error", "detail": str(exc)}}, 2
    print(json.dumps(payload, indent=2, sort_keys=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
