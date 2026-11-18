#!/usr/bin/env python3
"""Versioned task contract: the user's goal frozen, the repair's freedom bounded.

WHY THIS MODULE EXISTS
    A repair experiment asks one question: did the fix make the task pass? Two
    shortcuts make that question unanswerable, and both were observed in the
    archived runs:

    1. Asking the candidate. `claim_success` is written by the thing being
       graded, and in the archived corpus it is false almost every time - it
       carries no information about whether the run actually worked.
    2. Letting the candidate declare the ruler. A goal, an object tolerance or
       an acceptance threshold supplied alongside the candidate can be edited by
       the candidate, so "met the goal" quietly becomes "met whatever I wrote
       down".

    The fix is not a stricter threshold, it is a different owner for the ruler.
    A TaskContract is a separate artifact, written before the run and frozen by
    its own digest. It states:

        the user goal      -> immutable.user_goal (human text, never machine-parsed)
        what "reached" means -> immutable.objects[].position / tolerance
        where "there" is   -> immutable.zones[].position / radius
        the policy numbers -> immutable.thresholds.max_position_error_m / min_regressions
        what the fix may touch -> editable_fields
        what must not change   -> protected_paths (path + expected sha256)
        what evidence must exist -> evidence_required
        which run counts   -> run_id_pattern

    A candidate state is then judged ONLY against this contract. Nothing the
    candidate writes about the goal, the objects or the thresholds is read.

WHY protected_paths CARRIES A DIGEST AND NOT JUST A PATH
    A bare path list would still need a baseline hash from somewhere, and the
    only other place to get one is the candidate - which is the vulnerability
    this module exists to close. The expected digest is therefore part of the
    frozen contract.

FAIL-CLOSED BY CONSTRUCTION
    validate() returns a list of problems; only an empty list means valid. There
    is no assume-valid path: an unknown field is a problem, a missing field is a
    problem, a wrong version is a problem, and an internally contradictory
    contract (an editable field inside a protected path) is a problem. A
    contract that cannot be constructed cannot be used to grade anything.

Everything here is stdlib-only, deterministic and side-effect free.
"""

import hashlib
import json
import re

# A contract from another schema generation is not upgraded silently: an
# evaluator written against this field set must refuse to grade with it.
SCHEMA = "flexcell.repair_eval.task_contract/1"

TOP_LEVEL_KEYS = (
    "schema",
    "task_id",
    "version",
    "immutable",
    "editable_fields",
    "protected_paths",
    "evidence_required",
    "run_id_pattern",
)
IMMUTABLE_KEYS = ("user_goal", "objects", "zones", "thresholds")
OBJECT_KEYS = ("name", "position", "tolerance")
OBJECT_OPTIONAL_KEYS = ("zone",)
ZONE_KEYS = ("name", "position", "radius")
THRESHOLD_KEYS = ("max_position_error_m", "min_regressions")
PROTECTED_KEYS = ("path", "sha256")

# --------------------------------------------------------------- boundary codes
#
# The three answers this module can give about a path. They are the written
# boundary between "the repair may change this" and "this is the user's goal".
EDITABLE_FIELD = "EDITABLE_FIELD"      # declared in editable_fields -> may change
PROTECTED_PATH = "PROTECTED_PATH"      # declared in protected_paths -> digest gate
UNDECLARED_PATH = "UNDECLARED_PATH"    # neither -> not authorised, treated as a violation

BOUNDARY_CODES = (EDITABLE_FIELD, PROTECTED_PATH, UNDECLARED_PATH)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ContractError(RuntimeError):
    """Raised when a mapping is not a valid contract.

    Carries every problem, not just the first one: a contract with three
    mistakes should be fixed once, not three times.
    """

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__(
            "invalid task contract: " + "; ".join(self.problems))
        self.problems = tuple(self.problems)


# --------------------------------------------------------------------- helpers
def _is_bool(value):
    return isinstance(value, bool)


def _is_finite(value):
    if _is_bool(value) or not isinstance(value, (int, float)):
        return False
    # json.dumps writes NaN/Infinity by default; allow_nan=False rejects them,
    # but a value can also arrive from Python code, so check it here too.
    return value == value and value not in (float("inf"), float("-inf"))


def _is_int(value):
    return not _is_bool(value) and isinstance(value, int)


def _is_text(value):
    return isinstance(value, str) and value.strip() != ""


def _problems_sha256(value, where):
    if not isinstance(value, str) or not _SHA256_RE.match(value):
        return [where + ": must be a 64-character lowercase sha256 hex digest"]
    return []


def _problems_position(value, where):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return [where + ": must be a list of three numbers"]
    if not all(_is_finite(v) for v in value):
        return [where + ": must be three finite numbers"]
    return []


def _normalise(path):
    """The single definition of "the same path" used by every comparison.

    Trailing slashes are stripped so a directory may be written `skill/` or
    `skill`. This function must be the ONLY place that decides, because the
    alternative - normalising in one comparison and not in another - is exactly
    how a directory-form authorisation silently matched nothing.
    """
    return str(path).strip().rstrip("/")


def split_path(path):
    """Split `file:member` into (file, member). member is None for plain paths.

    A repair is often authorised on one parameter of a file (`controller.yaml:kp`)
    rather than on the whole file, so the member has to survive normalisation.

    The file part is normalised through the same function the comparison uses.
    It used to keep its trailing slash, so `skill/` became the root `skill//`
    and startswith() matched nothing: the contract validated, the run was
    rejected, and nothing pointed at the contract.
    """
    text = str(path).strip()
    if ":" in text:
        head, _, tail = text.partition(":")
        return _normalise(head), (tail.strip() or None)
    return _normalise(text), None


def _under(path, root):
    """True when `path` is `root` or lives inside the directory `root`."""
    if path == root:
        return True
    return path.startswith(root + "/")


def _field_permits(field, path):
    """Does the editable field `field` authorise a change to `path`?"""
    field_file, field_member = split_path(field)
    path_file, path_member = split_path(path)
    if not _under(path_file, field_file):
        return False
    if field_member is None:
        return True
    # A member-scoped authorisation does not extend to the whole file, and it
    # does not extend to a sibling member: that is the difference between
    # "you may retune kp" and "you may rewrite the controller".
    if path_file != field_file:
        return False
    return path_member == field_member


# ------------------------------------------------------------------ validation
def _problems_unknown_keys(section, allowed, where):
    unknown = sorted(set(section) - set(allowed))
    return ["%s.%s: unknown field" % (where, key) for key in unknown]


def _problems_objects(section, zone_names, where="immutable.objects"):
    if not isinstance(section, list) or not section:
        return [where + ": must be a non-empty list"]
    problems, seen = [], set()
    for index, entry in enumerate(section):
        at = "%s[%d]" % (where, index)
        if not isinstance(entry, dict):
            problems.append(at + ": must be an object")
            continue
        problems += _problems_unknown_keys(
            entry, OBJECT_KEYS + OBJECT_OPTIONAL_KEYS, at)
        for key in OBJECT_KEYS:
            if key not in entry:
                problems.append("%s.%s: missing" % (at, key))
        name = entry.get("name")
        if not _is_text(name):
            problems.append(at + ".name: must be a non-empty string")
        elif name in seen:
            problems.append(at + ".name: duplicate object name %r" % (name,))
        else:
            seen.add(name)
        problems += _problems_position(entry.get("position"), at + ".position")
        tolerance = entry.get("tolerance")
        if not _is_finite(tolerance) or tolerance <= 0:
            problems.append(at + ".tolerance: must be a finite number > 0")
        zone = entry.get("zone")
        if zone is not None:
            if not _is_text(zone):
                problems.append(at + ".zone: must be a non-empty string")
            elif zone_names is not None and zone not in zone_names:
                problems.append(
                    at + ".zone: %r is not a declared zone" % (zone,))
    return problems


def _problems_zones(section, where="immutable.zones"):
    if not isinstance(section, list):
        return [where + ": must be a list (an empty list is allowed)"]
    problems, seen = [], set()
    for index, entry in enumerate(section):
        at = "%s[%d]" % (where, index)
        if not isinstance(entry, dict):
            problems.append(at + ": must be an object")
            continue
        problems += _problems_unknown_keys(entry, ZONE_KEYS, at)
        for key in ZONE_KEYS:
            if key not in entry:
                problems.append("%s.%s: missing" % (at, key))
        name = entry.get("name")
        if not _is_text(name):
            problems.append(at + ".name: must be a non-empty string")
        elif name in seen:
            problems.append(at + ".name: duplicate zone name %r" % (name,))
        else:
            seen.add(name)
        problems += _problems_position(entry.get("position"), at + ".position")
        radius = entry.get("radius")
        if not _is_finite(radius) or radius <= 0:
            problems.append(at + ".radius: must be a finite number > 0")
    return problems


def _problems_thresholds(section, where="immutable.thresholds"):
    if not isinstance(section, dict):
        return [where + ": must be an object"]
    problems = _problems_unknown_keys(section, THRESHOLD_KEYS, where)
    for key in THRESHOLD_KEYS:
        if key not in section:
            problems.append("%s.%s: missing" % (where, key))
    error = section.get("max_position_error_m")
    if not _is_finite(error) or error <= 0:
        problems.append(
            where + ".max_position_error_m: must be a finite number > 0")
    regressions = section.get("min_regressions")
    if not _is_int(regressions) or regressions < 1:
        problems.append(where + ".min_regressions: must be an integer >= 1")
    return problems


def _problems_protected(section, where="protected_paths"):
    if not isinstance(section, list) or not section:
        return [where + ": must be a non-empty list"]
    problems, seen = [], set()
    for index, entry in enumerate(section):
        at = "%s[%d]" % (where, index)
        if not isinstance(entry, dict):
            problems.append(at + ": must be an object with path and sha256")
            continue
        problems += _problems_unknown_keys(entry, PROTECTED_KEYS, at)
        for key in PROTECTED_KEYS:
            if key not in entry:
                problems.append("%s.%s: missing" % (at, key))
        path = entry.get("path")
        if not _is_text(path):
            problems.append(at + ".path: must be a non-empty string")
        elif _normalise(path) in seen:
            problems.append(at + ".path: duplicate protected path %r" % (path,))
        else:
            seen.add(_normalise(path))
        problems += _problems_sha256(entry.get("sha256"), at + ".sha256")
    return problems


def _problems_editable(section, protected, where="editable_fields"):
    if not isinstance(section, list) or not section:
        return [where + ": must be a non-empty list"]
    problems, seen = [], set()
    for index, entry in enumerate(section):
        at = "%s[%d]" % (where, index)
        if not _is_text(entry):
            problems.append(at + ": must be a non-empty string")
            continue
        field_file, field_member = split_path(entry)
        if not field_file:
            problems.append(at + ": %r has no path before the member separator"
                            % (entry,))
        if _normalise(entry) in seen:
            problems.append(at + ": duplicate editable field %r" % (entry,))
        seen.add(_normalise(entry))
        # Self-consistency: the field must authorise the very path it names. A
        # field that fails this can never authorise anything, and the author
        # would not find out until every run came back UNAUTHORIZED_EDIT.
        probe = entry if field_member else field_file
        if field_file and not _field_permits(entry, probe):
            problems.append(
                "%s: %r authorises no path (it cannot even match itself)"
                % (at, entry))
        # A contract that says "you may edit X" and "X must stay identical" has
        # no consistent reading, so it is refused rather than resolved by
        # precedence at grading time.
        for item in protected or []:
            if not isinstance(item, dict):
                continue
            root = item.get("path")
            if not _is_text(root):
                continue
            if _under(field_file, _normalise(root)):
                problems.append(
                    "%s: %r is editable but also protected by %r"
                    % (at, entry, root))
    return problems


def _problems_evidence(section, where="evidence_required"):
    if not isinstance(section, list) or not section:
        return [where + ": must be a non-empty list"]
    problems, seen = [], set()
    for index, entry in enumerate(section):
        at = "%s[%d]" % (where, index)
        if not _is_text(entry):
            problems.append(at + ": must be a non-empty string")
            continue
        if entry in seen:
            problems.append(at + ": duplicate evidence name %r" % (entry,))
        seen.add(entry)
    return problems


def _problems_run_id_pattern(section, where="run_id_pattern"):
    if not _is_text(section):
        return [where + ": must be a non-empty string"]
    try:
        compiled = re.compile(section)
    except re.error as error:
        return ["%s: not a valid regular expression (%s)" % (where, error)]
    # A pattern that matches the empty string accepts every run id in practice,
    # including the run id of the run that produced it. That is not a check.
    if compiled.fullmatch("") is not None:
        return [where + ": pattern matches the empty string, so it constrains nothing"]
    return []


def validate(mapping):
    """Return the problems with `mapping`. An empty list means valid.

    Deliberately a module-level function as well as a classmethod so a mapping
    can be checked without constructing anything.
    """
    if not isinstance(mapping, dict):
        return ["contract: must be an object"]
    problems = []
    for key in TOP_LEVEL_KEYS:
        if key not in mapping:
            problems.append("%s: missing" % (key,))
    problems += _problems_unknown_keys(mapping, TOP_LEVEL_KEYS, "contract")

    if mapping.get("schema") != SCHEMA:
        problems.append("schema: expected %r got %r"
                        % (SCHEMA, mapping.get("schema")))
    if not _is_text(mapping.get("task_id")):
        problems.append("task_id: must be a non-empty string")
    version = mapping.get("version")
    if not _is_int(version) or version < 1:
        problems.append("version: must be an integer >= 1")

    immutable = mapping.get("immutable")
    if not isinstance(immutable, dict):
        problems.append("immutable: must be an object")
        immutable = {}
    else:
        problems += _problems_unknown_keys(immutable, IMMUTABLE_KEYS, "immutable")
        for key in IMMUTABLE_KEYS:
            if key not in immutable:
                problems.append("immutable.%s: missing" % (key,))
        if not _is_text(immutable.get("user_goal")):
            problems.append("immutable.user_goal: must be a non-empty string")

    problems += _problems_zones(immutable.get("zones") if immutable else None)
    zone_names = set()
    if isinstance(immutable.get("zones"), list):
        zone_names = {z.get("name") for z in immutable["zones"]
                      if isinstance(z, dict)}
    problems += _problems_objects(
        immutable.get("objects") if immutable else None, zone_names)
    problems += _problems_thresholds(
        immutable.get("thresholds") if immutable else None)

    protected = mapping.get("protected_paths")
    problems += _problems_protected(protected)
    problems += _problems_editable(mapping.get("editable_fields"),
                                   protected if isinstance(protected, list) else [])
    problems += _problems_evidence(mapping.get("evidence_required"))
    problems += _problems_run_id_pattern(mapping.get("run_id_pattern"))
    return problems


class TaskContract:
    """A frozen acceptance ruler. Construct via from_mapping() or the class itself.

    Instances are immutable by convention: every accessor returns a copy or a
    scalar, so a caller cannot widen a tolerance by mutating what it was handed.
    """

    schema = SCHEMA

    def __init__(self, mapping):
        problems = self.validate(mapping)
        if problems:
            raise ContractError(problems)
        self._mapping = json.loads(json.dumps(mapping, allow_nan=False))
        self._objects = tuple(self._mapping["immutable"]["objects"])
        self._zones = tuple(self._mapping["immutable"]["zones"])
        self._thresholds = dict(self._mapping["immutable"]["thresholds"])
        self._editable = tuple(self._mapping["editable_fields"])
        self._protected = tuple(self._mapping["protected_paths"])
        self._evidence = tuple(self._mapping["evidence_required"])
        self._run_id_pattern = re.compile(self._mapping["run_id_pattern"])

    # ------------------------------------------------------------- construction
    @classmethod
    def validate(cls, mapping):
        return validate(mapping)

    @classmethod
    def from_mapping(cls, mapping):
        return cls(mapping)

    # ------------------------------------------------------------- field access
    @property
    def task_id(self):
        return self._mapping["task_id"]

    @property
    def version(self):
        return self._mapping["version"]

    @property
    def user_goal(self):
        return self._mapping["immutable"]["user_goal"]

    @property
    def objects(self):
        return tuple(json.loads(json.dumps(obj)) for obj in self._objects)

    @property
    def zones(self):
        return tuple(json.loads(json.dumps(zone)) for zone in self._zones)

    @property
    def thresholds(self):
        return dict(self._thresholds)

    @property
    def editable_fields(self):
        return tuple(self._editable)

    @property
    def protected_paths(self):
        return tuple(json.loads(json.dumps(item)) for item in self._protected)

    @property
    def evidence_required(self):
        return tuple(self._evidence)

    @property
    def run_id_pattern(self):
        return self._mapping["run_id_pattern"]

    # --------------------------------------------------------------- boundaries
    def classify_path(self, path):
        """Return (editable, code) for one path.

        Protected wins over editable. A contract cannot declare both (validate
        rejects it), but if one ever does, the stricter reading is the safe one.
        """
        normalised = _normalise(path)
        for item in self._protected:
            if _under(normalised, _normalise(item["path"])):
                return False, PROTECTED_PATH
        for field in self._editable:
            if _field_permits(field, normalised):
                return True, EDITABLE_FIELD
        return False, UNDECLARED_PATH

    def is_editable(self, path):
        return self.classify_path(path)[0]

    def object_by_name(self, name):
        for entry in self._objects:
            if entry["name"] == name:
                return json.loads(json.dumps(entry))
        return None

    def zone_by_name(self, name):
        for entry in self._zones:
            if entry["name"] == name:
                return json.loads(json.dumps(entry))
        return None

    def protected_digest(self, path):
        normalised = _normalise(path)
        for item in self._protected:
            if _normalise(item["path"]) == normalised:
                return item["sha256"]
        return None

    def effective_tolerance(self, obj):
        """The tolerance that actually governs `obj`.

        The per-object tolerance says what this object needs; the contract-wide
        threshold says what this evaluator accepts at all. The stricter number
        wins, so a generous per-object tolerance cannot talk its way past the
        policy.
        """
        return min(float(obj["tolerance"]),
                   float(self._thresholds["max_position_error_m"]))

    def matches_run_id(self, run_id):
        if not isinstance(run_id, str):
            return False
        return self._run_id_pattern.fullmatch(run_id) is not None

    # ------------------------------------------------------------ freeze / hash
    def to_mapping(self):
        return json.loads(json.dumps(self._mapping, allow_nan=False))

    def canonical_json(self):
        """Whitespace-free, key-sorted, ASCII-escaped JSON.

        Two contracts describing the same task hash the same regardless of the
        order their keys were written in, which is what makes the digest usable
        as a freeze marker.
        """
        return json.dumps(self._mapping, sort_keys=True, separators=(",", ":"),
                          allow_nan=False, ensure_ascii=True)

    def sha256(self):
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def __repr__(self):
        return "TaskContract(task_id=%r, version=%r, sha256=%s...)" % (
            self.task_id, self.version, self.sha256()[:12])
