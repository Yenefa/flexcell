#!/usr/bin/env python3
"""Experience entry v2: the record a CONSUMER can act on, not a note about one.

WHY A SECOND SCHEMA EXISTS AT ALL
    evolution/experience/store.py already stores a hash-chained record with
    {task_id, failure_class, evidence, lesson, source_run, outcome}. That record proved
    two things the hard way:
      * a true record can still be useless, because the planner has no field to put a
        landing coordinate in (see evolution/transfer/route_lessons.py);
      * a record can be "validated" by the seeder and still be false (an independent
        review rejected 2 of 4), so provenance alone is not truth.

    So this schema adds exactly the fields whose ABSENCE made those failures possible:
      consumer        which module receives the entry, and which entrypoint
      action_kind     what kind of change it is, so routing can be decided by
                      capability rather than by keyword luck
      effect_spec     a MACHINE-RUNNABLE description of the change, so the effect can be
                      executed and measured instead of narrated
      applicable_when / known_invalid_when
                      the boundary of the entry, written before it is used
      version         DGM-style parent link, so a later version cannot silently replace
                      an earlier one and a rejected branch stays on disk
      validation      an independent verdict, never set by whoever wrote the entry
      origin          HUMAN_AUTHORED vs AGENT_GENERATED (master goal section 11.2)

    The seven fields the master goal requires are all present; master_goal_coverage()
    reports them one by one so a verifier can assert the mapping instead of trusting
    this docstring.

APPEND-ONLY, HASH-CHAINED: entries are written through store.append, which adds
prev_sha256/chain_sha256. Nothing here updates or deletes a record.
"""
import hashlib
import json

SCHEMA_VERSION = "experience-entry/2"

ORIGINS = ("AGENT_GENERATED", "HUMAN_AUTHORED")

# Status is a property of the VERSION, not of the entry text. Only ACTIVE may reach a
# consumer. CANDIDATE means "built, not yet validated"; CONFLICT means two entries make
# incompatible claims under the same condition and a human has to choose.
STATUSES = ("CANDIDATE", "ACTIVE", "RETIRED", "REJECTED", "CONFLICT")

# The kinds of change a robot stack can actually receive. Routing is decided by whether
# a consumer DECLARES the kind, not by whether the lesson text contains a keyword.
ACTION_KINDS = (
    "move_order",        # which object moves, where, in what order
    "object_set",        # which objects are in the plan at all
    "landing_spacing",   # where inside a bin a landing point sits
    "recovery_action",   # what to do after a measured failure
    "harness_config",    # launch / DDS / environment configuration
    "development",       # a practice for the coding agent, never for the robot
)

REQUIRED = (
    "schema_version", "origin", "task_family", "failure_class", "source_run",
    "evidence", "applicable_when", "known_invalid_when", "suggested_action",
    "action_kind", "consumer", "effect_spec", "validation", "version",
)


class EntryError(ValueError):
    """A malformed or over-claiming entry. Refused at write time, never repaired."""


def canonical(obj):
    """Serialise exactly the way store._hash does.

    A v2 record is stored THROUGH store.append, and store.verify_chain re-hashes every
    record to prove the chain is intact. If this function used different JSON separators
    than store._hash, every v2 record would fail verification as "tampered" the moment
    it was written - the chain guard would reject its own new records. So the
    serialisation is deliberately identical, and the compact form is NOT used here.
    """
    return json.dumps(obj, sort_keys=True)


def digest(obj):
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def _body(entry):
    return {k: v for k, v in entry.items()
            if k not in ("entry_id", "record_sha256", "prev_sha256", "chain_sha256")}


def make_entry(origin, task_family, failure_class, source_run, evidence,
               applicable_when, known_invalid_when, suggested_action, action_kind,
               consumer, effect_spec, version, validation=None, evidence_files=None,
               provenance_verified=False, notes=""):
    """Build one entry. Every argument is checked; nothing is inferred from prose.

    validation defaults to NOT_REVIEWED. It is deliberately not this function's to set:
    the master goal forbids the agent that generated an experience from declaring it
    verified, so the field is filled by whoever reviews it, and retrieval refuses an
    entry without an explicit ACCEPT.
    """
    if origin not in ORIGINS:
        raise EntryError("unknown origin %r; expected one of %s" % (origin, ORIGINS))
    if action_kind not in ACTION_KINDS:
        raise EntryError("unknown action_kind %r; expected one of %s"
                         % (action_kind, ACTION_KINDS))
    if not isinstance(evidence, dict) or not evidence:
        raise EntryError("evidence must be a non-empty dict of measured facts")
    if not isinstance(effect_spec, dict) or not effect_spec.get("fixture"):
        raise EntryError("effect_spec needs a fixture: an effect that cannot be run is a claim")
    if not isinstance(applicable_when, list) or not applicable_when:
        raise EntryError("applicable_when must list at least one condition")
    if not isinstance(known_invalid_when, list):
        raise EntryError("known_invalid_when must be a list (empty is allowed)")
    if not str(suggested_action).strip():
        raise EntryError("suggested_action is empty")
    ver = dict(version or {})
    for key in ("label", "status"):
        if not ver.get(key):
            raise EntryError("version.%s is required" % key)
    if ver["status"] not in STATUSES:
        raise EntryError("version.status %r not in %s" % (ver["status"], STATUSES))
    val = {"review_verdict": "NOT_REVIEWED", "review_ref": None, "reviewed_by": None}
    if validation:
        val.update(validation)
    entry = {
        "schema_version": SCHEMA_VERSION,
        "origin": origin,
        "task_family": task_family,
        "failure_class": failure_class,
        "source_run": source_run,
        "evidence": evidence,
        "evidence_files": list(evidence_files or []),
        "provenance_verified": bool(provenance_verified),
        "applicable_when": list(applicable_when),
        "known_invalid_when": list(known_invalid_when),
        "suggested_action": str(suggested_action)[:500],
        "action_kind": action_kind,
        "consumer": consumer,
        "effect_spec": effect_spec,
        "validation": val,
        "version": ver,
        "stats": {"retrieved": 0, "applied": 0, "helpful": 0, "harmful": 0},
        "notes": notes,
    }
    entry["entry_id"] = digest(_body(entry))
    entry["record_sha256"] = digest({k: v for k, v in entry.items()
                                     if k != "record_sha256"})
    return entry


def validate(entry):
    """Return a list of problems. Empty means the entry is well formed AND not over-claiming."""
    problems = []
    if not isinstance(entry, dict):
        return ["entry is not an object"]
    for key in REQUIRED:
        if key not in entry:
            problems.append("missing field: " + key)
    if problems:
        return problems
    if entry["schema_version"] != SCHEMA_VERSION:
        problems.append("schema_version is %r, expected %r"
                        % (entry["schema_version"], SCHEMA_VERSION))
    if entry["origin"] not in ORIGINS:
        problems.append("origin %r not allowed" % (entry["origin"],))
    if entry["action_kind"] not in ACTION_KINDS:
        problems.append("action_kind %r not allowed" % (entry["action_kind"],))
    if entry["version"].get("status") not in STATUSES:
        problems.append("version.status %r not allowed" % (entry["version"].get("status"),))
    # An entry that names a consumer but no runnable effect is the exact defect this
    # schema exists to prevent, so it is a validation failure rather than a warning.
    if not entry["effect_spec"].get("fixture"):
        problems.append("effect_spec has no fixture: the effect cannot be run")
    if entry["validation"].get("review_verdict") not in (
            "NOT_REVIEWED", "ACCEPT", "REJECT"):
        problems.append("review_verdict %r not allowed"
                        % (entry["validation"].get("review_verdict"),))
    # Self-verification is refused: a generated entry may not carry its own ACCEPT.
    if entry["origin"] == "AGENT_GENERATED" and entry["validation"].get(
            "review_verdict") == "ACCEPT" and not entry["validation"].get("reviewed_by"):
        problems.append("AGENT_GENERATED entry claims ACCEPT without a reviewer")
    expected = digest(_body(entry))
    if entry.get("entry_id") != expected:
        problems.append("entry_id does not match the body (edited after write?)")
    return problems


def master_goal_coverage(entry):
    """Map master goal section 11.2's seven required fields onto this schema.

    Reported as a dict rather than asserted in prose, so an acceptance verifier can
    check the mapping mechanically and a reader can see which field carries which.
    """
    return {
        "1_source_experiment": bool(entry.get("source_run")),
        "2_raw_evidence": bool(entry.get("evidence")),
        "3_applicable_task": bool(entry.get("task_family")),
        "4_applicable_conditions": bool(entry.get("applicable_when")),
        "5_known_invalid_conditions": isinstance(entry.get("known_invalid_when"), list),
        "6_confidence_state": bool(entry.get("validation", {}).get("review_verdict")),
        "7_verification_record": bool(entry.get("validation", {}).get("review_ref")
                                     or entry.get("effect", {}).get("verdict")),
    }


if __name__ == "__main__":
    import sys
    doc = json.loads(open(sys.argv[1], encoding="utf-8").read())
    probs = validate(doc)
    print(json.dumps({"problems": probs,
                      "master_goal_coverage": master_goal_coverage(doc)}, indent=2))
    raise SystemExit(0 if not probs else 1)
