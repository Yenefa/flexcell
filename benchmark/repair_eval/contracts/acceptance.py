#!/usr/bin/env python3
"""Independent acceptance for a repair candidate, judged only against the contract.

WHY THE RULER IS NOT THE CANDIDATE
    Three things are routinely read from the candidate and all three are
    writable by the candidate:

        claim_success        self-report; false in almost every archived run
        reported thresholds  "my tolerance is 0.5 m" -> every goal is met
        reported goal        "the block was supposed to be there" -> same

    None of them is read here. Goal positions, tolerances, zone radii and the
    regression minimum come from the TaskContract only. A candidate that
    restates them is not ignored silently either: restating an immutable field
    is itself a contract violation, so it is recorded as TAMPERED_IMMUTABLE and
    rejected, while the numbers used for measurement stay the contract's.

WHY THREE STATUSES AND NOT A BOOLEAN
    "passed: false" merges two very different outcomes:

        the run was measured and it failed   -> REJECT
        the run could not be measured        -> UNKNOWN

    Collapsing UNKNOWN into REJECT is a false negative; collapsing it into
    ACCEPT is the false acceptance this module is built to prevent. So a gate
    that cannot be evaluated produces UNKNOWN, and UNKNOWN never becomes
    ACCEPT - which is also why acceptance requires every gate to have produced a
    positive result, not merely the absence of a rejection.

WHY REJECT WINS OVER UNKNOWN
    A measured violation is a fact; an unmeasurable gate is a gap. When both are
    present the fact decides the verdict, because no amount of missing evidence
    would make a violated tolerance true.

WHY EVERY FAILING GATE CARRIES A CODE
    A verdict that only says "REJECT" cannot be audited: a bundle that fails
    the schema check also returns REJECT and would happily stand in for "the
    goal was not reached". Each negative case in cases/ therefore asserts the
    specific code, so the six defect classes cannot collapse into one another.

Everything here is stdlib-only, deterministic and side-effect free.
"""

import dataclasses
import math
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# Imported package-first on purpose. A caller who does
# "from benchmark.repair_eval.contracts.task_contract import TaskContract" and
# then hands that instance to evaluate() must hit the SAME class object; a flat
# import here would load a second copy of the module, and the isinstance check
# below would then reject the caller's own contract. That is a silent wiring
# bug, not an error message, so the fallback is only for script execution.
if __package__:
    from . import task_contract
    from .task_contract import TaskContract
else:
    import task_contract
    from task_contract import TaskContract

# The candidate format is versioned separately from the contract, and the tag is
# a GATE in evaluate(), not a comment: a report that does not declare this format
# is UNKNOWN, never ACCEPT. It used to be declared and never read, which meant a
# report from another harness - or one with no format tag at all - was judged as
# if its fields meant what they mean here.
CANDIDATE_SCHEMA = "flexcell.repair_eval.candidate/1"

ACCEPT = "ACCEPT"
REJECT = "REJECT"
UNKNOWN = "UNKNOWN"
STATUSES = (ACCEPT, REJECT, UNKNOWN)

# code -> (severity, what it means). One table, so the meaning of a code cannot
# drift between the evaluator, the tests and the documentation.
REASONS = {
    # measured violations: a fact about this run decides the verdict
    "GOAL_NOT_MET": (REJECT, "a contract object ended outside its declared tolerance"),
    "REGRESSION_FAILED": (REJECT, "a declared regression reported FAIL"),
    "PROTECTED_MODIFIED": (REJECT, "a protected file's digest does not match the contract"),
    "NONZERO_EXIT": (REJECT, "the acceptance subprocess exited non-zero"),
    "UNAUTHORIZED_EDIT": (REJECT, "the repair changed a path the contract does not authorise"),
    "TAMPERED_IMMUTABLE": (REJECT, "the candidate restated an immutable goal/threshold field"),
    "TASK_MISMATCH": (REJECT, "the candidate reports a different task than the contract"),
    # unmeasurable gates: a gap in this run decides nothing
    "GOAL_UNMEASURED": (UNKNOWN, "no measured final position for a contract object"),
    "REGRESSION_MISSING": (UNKNOWN, "fewer usable regression records than the contract requires"),
    "PROTECTED_UNVERIFIABLE": (UNKNOWN, "no digest supplied for a protected file"),
    "EVIDENCE_MISSING": (UNKNOWN, "a required evidence artifact is absent or malformed"),
    "RUN_ID_MISMATCH": (UNKNOWN, "the run id does not match the contract's pattern"),
    "EXIT_CODE_MISSING": (UNKNOWN, "the acceptance subprocess exit code was not recorded"),
    "CHANGED_FILES_UNREPORTED": (UNKNOWN, "the candidate did not declare what it changed"),
    "CANDIDATE_MALFORMED": (UNKNOWN, "the candidate state is not a usable report"),
    # internal invariant guard: a gate failed without a code would otherwise be
    # neither rejected nor unknown, which is the one outcome that must not exist
    "UNATTRIBUTED_FAILURE": (UNKNOWN, "a gate failed without producing a reason code"),
}

REJECT_CODES = tuple(c for c, (s, _) in REASONS.items() if s == REJECT)
UNKNOWN_CODES = tuple(c for c, (s, _) in REASONS.items() if s == UNKNOWN)

# Keys a candidate may never restate. They are the ruler, not a measurement.
# The schema and version keys are listed because the candidate's own format
# lives in candidate_schema: anything else claiming to be a schema is claiming
# the contract's authority.
FORBIDDEN_CANDIDATE_KEYS = frozenset({
    "schema", "version", "immutable", "user_goal", "thresholds", "zones",
    "editable_fields", "protected_paths", "evidence_required", "run_id_pattern",
    "tolerance", "target", "goal", "expected_goal", "expected_objects",
    "reported_goal", "reported_thresholds", "reported_tolerance",
})

# NOT forbidden, checked for equality instead: contract_version and
# contract_sha256 are provenance. The collector - not the repaired agent - writes
# the candidate state, and stamping "this report was produced under contract v1"
# is a reasonable thing for it to do. They were briefly members of the set above,
# which made every run from an echoing collector a REJECT: a false failure that
# silently lowers the reported success rate, the mirror image of a false
# acceptance. Absence is normal, a match is recorded, a mismatch is TASK_MISMATCH.

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_PASS_TEXT_RE = re.compile(r"\b(pass|passed|passing|success|succeeded)\b",
                           re.IGNORECASE)


def _is_finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return value == value and value not in (float("inf"), float("-inf"))


def _normalise(path):
    return str(path).strip().rstrip("/")


def _position(value):
    """A measured position, or None when the report cannot supply one."""
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    if not all(_is_finite(v) for v in value):
        return None
    return tuple(float(v) for v in value)


# Containers whose KEYS are data, not schema fields: "objects" is keyed by
# object name, "protected_hashes" by file path. Their keys must never be read as
# a field declaration, or a task with an object called "target" - about the most
# natural name there is - would be rejected on every run as TAMPERED_IMMUTABLE:
# the evaluator accusing the repair of cheating when the bug is its own.
DATA_KEYED_CONTAINERS = frozenset({"objects", "protected_hashes"})


def _forbidden_key_hits(node, prefix="$"):
    """Every path in the candidate that names an immutable SCHEMA field.

    Recursion stops at the containers whose keys are data. The key that opens
    such a container is still checked - a top-level "zones" is still a restated
    schema field - but what lives inside it is a value, not a declaration.
    """
    hits = []
    if isinstance(node, dict):
        for key in sorted(node, key=str):
            path = prefix + "." + str(key)
            if str(key) in FORBIDDEN_CANDIDATE_KEYS:
                hits.append(path)
            if str(key) in DATA_KEYED_CONTAINERS:
                continue
            hits.extend(_forbidden_key_hits(node[key], path))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            hits.extend(_forbidden_key_hits(item, "%s[%d]" % (prefix, index)))
    return hits


def _claims_pass_text(state):
    """Does the candidate's own stdout claim success?

    Only used to explain a non-zero exit, never to decide anything.
    """
    for key in ("stdout_tail", "stdout"):
        text = state.get(key)
        if isinstance(text, str) and _PASS_TEXT_RE.search(text):
            return True
    return False


def _evidence_index(state):
    """Split declared evidence into usable records and why the rest is unusable."""
    entries = state.get("evidence")
    good, bad = {}, {}
    if not isinstance(entries, list):
        return good, bad
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            bad["#%d" % index] = "evidence record %d is not an object" % index
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            bad["#%d" % index] = "evidence record %d has no name" % index
            continue
        if name in good or name in bad:
            good.pop(name, None)
            bad[name] = "evidence %r is declared more than once" % (name,)
            continue
        path = entry.get("path")
        digest = entry.get("sha256")
        if not isinstance(path, str) or not path.strip():
            bad[name] = "evidence %r has no path" % (name,)
            continue
        if not isinstance(digest, str) or not _SHA256_RE.match(digest):
            bad[name] = "evidence %r has no valid sha256" % (name,)
            continue
        good[name] = entry
    return good, bad


@dataclasses.dataclass
class Verdict:
    """The acceptance result, attributable to the exact contract that produced it."""

    status: str
    reasons: list
    checks: list
    task_id: str
    contract_version: int
    contract_sha256: str

    @property
    def codes(self):
        return sorted({reason["code"] for reason in self.reasons})

    @property
    def accepted(self):
        return self.status == ACCEPT

    def failed_checks(self):
        return [check["check"] for check in self.checks if not check["ok"]]

    def to_dict(self):
        return {
            "status": self.status,
            "task_id": self.task_id,
            "contract_version": self.contract_version,
            "contract_sha256": self.contract_sha256,
            "reasons": [dict(reason) for reason in self.reasons],
            "checks": [dict(check) for check in self.checks],
        }


def evaluate(contract, candidate_state):
    """Judge one candidate state against one frozen contract.

    Contract: evaluate(contract: TaskContract, candidate_state: mapping) -> Verdict

    The candidate state is read as a REPORT of measurements. Its provenance (who
    measured the final positions, and whether the candidate could have written
    them) is out of scope here and is the subject of the visibility policy.
    """
    if not isinstance(contract, TaskContract):
        raise TypeError("contract must be a TaskContract, got %r"
                        % (type(contract).__name__,))

    checks = []
    reasons = []

    def check(name, ok, code=None, detail=None, informational=False, **evidence):
        """Record one gate. A failing gate without a code is a programming error."""
        ok = bool(ok)
        if not ok and not code:
            raise AssertionError("gate %r failed without a reason code" % (name,))
        entry = {"check": name, "ok": ok, "evidence": evidence}
        if informational:
            # Recorded, never decisive: the invariant guard in _verdict() must
            # not mistake an informational record for a gate.
            entry["informational"] = True
        checks.append(entry)
        if not ok:
            reasons.append({"code": code, "detail": detail or name})
        return ok

    if not isinstance(candidate_state, dict):
        check("candidate_state", False, "CANDIDATE_MALFORMED",
              "candidate state is %r, expected an object"
              % (type(candidate_state).__name__,),
              received_type=type(candidate_state).__name__)
        return _verdict(contract, checks, reasons)

    state = candidate_state

    # ------------------------------------------------------ report format gate
    # A report from another generation of the harness cannot be read: its field
    # names may mean something else. So this gate stops BEFORE reading anything
    # else - an ACCEPT from an unreadable report is an invention, and a REJECT
    # built from fields we just admitted we cannot interpret is an accusation.
    declared_schema = state.get("candidate_schema")
    if not check("candidate_schema", declared_schema == CANDIDATE_SCHEMA,
                 "CANDIDATE_MALFORMED",
                 "candidate report declares format %r; this evaluator reads %r, "
                 "so its fields cannot be interpreted"
                 % (declared_schema, CANDIDATE_SCHEMA),
                 declared=declared_schema, expected=CANDIDATE_SCHEMA):
        return _verdict(contract, checks, reasons)

    # ---------------------------------------------------------------- identity
    declared_task = state.get("task_id")
    if declared_task is not None:
        check("task_identity", declared_task == contract.task_id,
              "TASK_MISMATCH",
              "candidate reports task %r but the contract is %r"
              % (declared_task, contract.task_id),
              declared=declared_task, contract=contract.task_id)

    # ------------------------------------------------------- contract identity
    # Same shape as the task identity above, for the same reason: identity is
    # compared, not forbidden. A mismatch is decisive, and its code is
    # TASK_MISMATCH - the report and the contract disagree about which rulebook
    # is in force - rather than TAMPERED_IMMUTABLE, which means the candidate
    # edited the ruler. Merging those two would collapse defect classes the
    # corpus keeps apart.
    declared_version = state.get("contract_version")
    declared_digest = state.get("contract_sha256")
    if declared_version is not None or declared_digest is not None:
        mismatches = []
        if declared_version is not None:
            usable = (isinstance(declared_version, int)
                      and not isinstance(declared_version, bool))
            if not usable or declared_version != contract.version:
                mismatches.append("contract_version %r != %r"
                                  % (declared_version, contract.version))
        if declared_digest is not None:
            if (not isinstance(declared_digest, str)
                    or declared_digest != contract.sha256()):
                mismatches.append("contract_sha256 %r != %r"
                                  % (declared_digest, contract.sha256()))
        check("contract_identity_echo", not mismatches, "TASK_MISMATCH",
              "the report echoes a different contract: %s"
              % ("; ".join(mismatches),),
              declared={"contract_version": declared_version,
                        "contract_sha256": declared_digest},
              expected={"contract_version": contract.version,
                        "contract_sha256": contract.sha256()},
              informational=not mismatches)

    # ------------------------------------------------------- tampering / freeze
    hits = _forbidden_key_hits(state)
    check("immutable_not_restated", not hits,
          "TAMPERED_IMMUTABLE",
          "candidate supplied immutable contract fields: %s" % (", ".join(hits),),
          tampered_paths=hits, contract_sha256=contract.sha256())

    # ------------------------------------------------------------ exit status
    exit_code = state.get("exit_code")
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        check("subprocess_exit", False, "EXIT_CODE_MISSING",
              "the acceptance subprocess exit code was not recorded (%r)"
              % (exit_code,), observed=exit_code, expected=0)
    else:
        claims_pass = _claims_pass_text(state)
        if exit_code == 0:
            detail = None
        elif claims_pass:
            detail = ("stdout claims success but the subprocess exited %d; the "
                      "claim does not survive the exit code" % exit_code)
        else:
            detail = "the acceptance subprocess exited %d" % (exit_code,)
        check("subprocess_exit", exit_code == 0, "NONZERO_EXIT", detail,
              observed=exit_code, expected=0, claims_pass_text=claims_pass)

    # ---------------------------------------------------------------- evidence
    good_evidence, bad_evidence = _evidence_index(state)
    for required in contract.evidence_required:
        record = good_evidence.get(required)
        if record is None:
            check("evidence:" + required, False, "EVIDENCE_MISSING",
                  bad_evidence.get(required)
                  or "no evidence record named %r" % (required,),
                  required=required)
        else:
            check("evidence:" + required, True,
                  path=record["path"], sha256=record["sha256"])

    # ------------------------------------------------------------------ run id
    run_id = state.get("run_id")
    check("run_id", contract.matches_run_id(run_id), "RUN_ID_MISMATCH",
          "run id %r does not match the contract pattern %r"
          % (run_id, contract.run_id_pattern),
          observed=run_id, pattern=contract.run_id_pattern)

    # -------------------------------------------------------- protected files
    declared_digests = state.get("protected_hashes")
    if not isinstance(declared_digests, dict):
        declared_digests = {}
    digests = {_normalise(key): value for key, value in declared_digests.items()
               if isinstance(key, str)}
    for item in contract.protected_paths:
        path = item["path"]
        expected = item["sha256"]
        actual = digests.get(_normalise(path))
        if not isinstance(actual, str) or not actual:
            check("protected:" + path, False, "PROTECTED_UNVERIFIABLE",
                  "no digest reported for protected path %r" % (path,),
                  path=path, expected_sha256=expected)
            continue
        check("protected:" + path, actual == expected, "PROTECTED_MODIFIED",
              "protected path %r changed: expected %s, observed %s"
              % (path, expected, actual),
              path=path, expected_sha256=expected, observed_sha256=actual)

    # -------------------------------------------------------- authorised edits
    changed = state.get("changed_files")
    if not isinstance(changed, list) or not changed:
        check("changed_files", False, "CHANGED_FILES_UNREPORTED",
              "the candidate did not declare which paths it changed",
              declared=changed)
    else:
        violations, examined = [], []
        for path in changed:
            if not isinstance(path, str) or not path.strip():
                violations.append({"path": path, "reason": "MALFORMED"})
                continue
            editable, code = contract.classify_path(path)
            examined.append({"path": path, "reason": code})
            if not editable:
                violations.append({"path": path, "reason": code})
        check("changed_files", not violations, "UNAUTHORIZED_EDIT",
              "the repair changed paths outside editable_fields: %s"
              % (", ".join("%s (%s)" % (v["path"], v["reason"])
                           for v in violations),),
              examined=examined, violations=violations,
              editable_fields=list(contract.editable_fields))

    # -------------------------------------------------------------------- goal
    measured_objects = state.get("objects")
    if not isinstance(measured_objects, dict):
        measured_objects = {}
    for obj in contract.objects:
        name = obj["name"]
        position = _position(measured_objects.get(name))
        if position is None:
            check("goal:" + name, False, "GOAL_UNMEASURED",
                  "no measured final position for %r" % (name,),
                  object=name, required_position=[float(v) for v in obj["position"]])
            continue
        required = tuple(float(v) for v in obj["position"])
        tolerance = contract.effective_tolerance(obj)
        distance = math.dist(position, required)
        evidence = {
            "object": name,
            "measured_position": list(position),
            "required_position": list(required),
            "distance_m": round(distance, 6),
            "tolerance_m": tolerance,
            # Explicit, so a reader can see the number came from the contract and
            # not from anything the candidate said about tolerances.
            "tolerance_source": "contract",
        }
        ok = distance <= tolerance
        detail = ("%s ended %.6f m from its required position (tolerance %.6f m)"
                  % (name, distance, tolerance))
        zone_name = obj.get("zone")
        if zone_name:
            zone = contract.zone_by_name(zone_name)
            zone_distance = math.dist(position,
                                      tuple(float(v) for v in zone["position"]))
            zone_radius = float(zone["radius"])
            ok = ok and zone_distance <= zone_radius
            evidence.update({
                "zone": zone_name,
                "zone_distance_m": round(zone_distance, 6),
                "zone_radius_m": zone_radius,
                "zone_source": "contract",
            })
            if zone_distance > zone_radius:
                detail += "; outside zone %r by %.6f m" % (
                    zone_name, zone_distance - zone_radius)
        check("goal:" + name, ok, "GOAL_NOT_MET", detail, **evidence)

    # ------------------------------------------------------------- regressions
    records = state.get("regressions")
    usable = 0
    if not isinstance(records, list):
        check("regressions_present", False, "REGRESSION_MISSING",
              "no regression records declared",
              required=contract.thresholds["min_regressions"])
    else:
        seen_regressions = set()
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                check("regression:#%d" % index, False, "REGRESSION_MISSING",
                      "regression record %d is not an object" % (index,))
                continue
            label = record.get("name")
            if not isinstance(label, str) or not label.strip():
                check("regression:#%d" % index, False, "REGRESSION_MISSING",
                      "regression must have a non-empty identity")
                continue
            label = label.strip()
            if label in seen_regressions:
                check("regression:" + label, False, "REGRESSION_MISSING",
                      "duplicate regression identity: %s" % label)
                continue
            seen_regressions.add(label)
            status = record.get("status")
            if status not in ("PASS", "FAIL"):
                check("regression:" + label, False, "REGRESSION_MISSING",
                      "regression %r reported status %r, which cannot testify"
                      % (label, status),
                      regression=label, status=status)
                continue
            usable += 1
            check("regression:" + label, status == "PASS", "REGRESSION_FAILED",
                  "regression %r reported %s" % (label, status),
                  regression=label, status=status)
        minimum = contract.thresholds["min_regressions"]
        check("regressions_present", usable >= minimum,
              "REGRESSION_MISSING" if usable < minimum else None,
              "only %d usable regression record(s); the contract requires %d"
              % (usable, minimum),
              usable=usable, required=minimum)

    return _verdict(contract, checks, reasons, state)


def _status_from(reasons):
    severities = {REASONS[reason["code"]][0] for reason in reasons}
    if REJECT in severities:
        return REJECT
    if UNKNOWN in severities:
        return UNKNOWN
    return ACCEPT


def _verdict(contract, checks, reasons, state=None):
    """Assemble the verdict, including the claim record that decides nothing."""
    status = _status_from(reasons)
    if status == ACCEPT:
        # Invariant guard. Every gate raises a reason when it fails, so this can
        # only trigger on a bug - but a bug must not be able to produce an
        # acceptance, so it downgrades to UNKNOWN instead of passing.
        failed = [check["check"] for check in checks
                  if not check["ok"] and not check.get("informational")]
        if failed:
            reasons.append({
                "code": "UNATTRIBUTED_FAILURE",
                "detail": "gates failed without a reason code: %s"
                          % (", ".join(failed),),
            })
            status = UNKNOWN

    if state is not None:
        present = "claim_success" in state
        claim = state.get("claim_success")
        claim_bool = claim if isinstance(claim, bool) else None
        checks.append({
            "check": "claim",
            "ok": True,
            "informational": True,
            "evidence": {
                "claim_present": present,
                "claim_success": claim_bool,
                # The point of the whole module, stated where a reader will
                # find it: this field is recorded, and it is not an input to
                # the verdict.
                "used_for_decision": False,
                "false_success": bool(claim_bool is True and status != ACCEPT),
                "false_failure": bool(claim_bool is False and status == ACCEPT),
            },
        })

    return Verdict(
        status=status,
        reasons=reasons,
        checks=checks,
        task_id=contract.task_id,
        contract_version=contract.version,
        contract_sha256=contract.sha256(),
    )


def evaluate_mapping(contract_mapping, candidate_state):
    """Convenience for case files: build the contract, then judge."""
    return evaluate(task_contract.TaskContract.from_mapping(contract_mapping),
                    candidate_state)
