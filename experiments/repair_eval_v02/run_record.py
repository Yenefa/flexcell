"""Assemble a run record that matches DATA_DICTIONARY 3.3 - 3.5.

WHY THIS MODULE EXISTS
    The matrix drivers produce a verdict and a ledger account, but a record that
    the data dictionary would accept also needs the information-supply surface
    (3.3) and the gate surface (3.5). Without this, a real run would produce
    something close to the declared schema but not equal to it, and the gap
    would only be found when the analysis script started reading fields that
    were never written.

TWO VOCABULARIES, ONE RECORD
    The #249 policy and the data dictionary do not use the same names for the
    same thing, and that is fine as long as the mapping is written down:

        policy feedback_source     record feedback_source
        none                   ->  none                     (A)
        own_run  + no guidance ->  own_run                  (B)
        mismatch_run           ->  donor_run                (C)
        own_run  + guidance    ->  own_run_plus_guidance    (D)

    The policy calls it mismatch_run because that is what the run is; the record
    calls it donor_run because that is what the analysis reads. Converting
    silently is how two documents end up disagreeing while both look right, so
    the mapping is a table in the code and a test asserts each arm of it.

WHAT THIS DOES NOT DO
    It does not compute gates. Gates come from the evaluator and the contract
    layer, and inventing a NOT_RUN here would turn "nobody measured this" into a
    declared result. Callers must pass what they actually have.
"""
import hashlib

FEEDBACK_SOURCE_NONE = "none"
FEEDBACK_SOURCE_OWN = "own_run"
FEEDBACK_SOURCE_DONOR = "donor_run"
FEEDBACK_SOURCE_GUIDED = "own_run_plus_guidance"
FEEDBACK_SOURCES = (FEEDBACK_SOURCE_NONE, FEEDBACK_SOURCE_OWN,
                    FEEDBACK_SOURCE_DONOR, FEEDBACK_SOURCE_GUIDED)

# policy vocabulary -> record vocabulary. A condition with guidance is handled
# separately because the guidance is what distinguishes D from B.
POLICY_TO_RECORD = {
    "none": FEEDBACK_SOURCE_NONE,
    "own_run": FEEDBACK_SOURCE_OWN,
    "mismatch_run": FEEDBACK_SOURCE_DONOR,
}

GATE_ENUM = ("PASS", "FAIL", "NOT_RUN")


class RecordError(Exception):
    """Raised when a record would not match the declared schema."""


# The digest convention is part of the record, not an implementation detail.
# Without it the same delivered feedback hashes differently on Windows and Linux,
# because the two produce different line endings, and two records that should be
# comparable become two different numbers. Measured before this was fixed:
#
#     sha256("line one\nline two\n")        -> e9024f1a...
#     sha256("line one\r\nline two\r\n")    -> 6612d9c9...
#
# So the convention is: decode as UTF-8, map CRLF and bare CR to LF, encode as
# UTF-8, then sha256. It is written here and in DATA_DICTIONARY 3.3 so a reader
# of a record can reproduce the number instead of guessing how it was made.
DIGEST_CONVENTION = "utf8-lf-sha256/1"


def sha256_text(text):
    """Digest of a text payload under DIGEST_CONVENTION.

    Line endings are normalised on purpose: they are an artefact of the platform
    that wrote the file, not part of what was said to the repairer.
    """
    if not isinstance(text, str):
        raise TypeError("sha256_text expects str, got %s" % type(text).__name__)
    normalised = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def sha256_bytes(payload):
    """Digest of a byte payload, with no normalisation whatsoever.

    Use this when the bytes themselves are the evidence - an archive member, a
    binary, a file whose exact content matters. Normalising bytes would change
    what was measured.
    """
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("sha256_bytes expects bytes")
    return hashlib.sha256(bytes(payload)).hexdigest()


def feedback_source_for(condition_access):
    """Map one policy condition onto the record's vocabulary."""
    source = getattr(condition_access, "feedback_source", None)
    if source not in POLICY_TO_RECORD:
        raise RecordError(
            "policy feedback_source %r has no mapping to the record vocabulary; "
            "add it to POLICY_TO_RECORD rather than writing it through as-is"
            % (source,))
    mapped = POLICY_TO_RECORD[source]
    if getattr(condition_access, "guidance", None):
        if mapped != FEEDBACK_SOURCE_OWN:
            raise RecordError(
                "guidance is only defined on top of this run's own feedback, got %r"
                % (mapped,))
        return FEEDBACK_SOURCE_GUIDED
    return mapped


def all_gates_passed(gate_target, gate_regression, gate_contract, gate_independent):
    """Every gate PASS, including every retained scenario.

    NOT_RUN counts as not passed on purpose. 3.5 defines false_accept as
    "claimed success but G1-G4 did not all pass", and a gate nobody ran did not
    pass - a claim that could not be checked is not a verified success. Reading
    it the other way would let an unmeasured run count as a true positive.
    """
    if gate_target != "PASS" or gate_contract != "PASS" or gate_independent != "PASS":
        return False
    return all(value == "PASS" for value in (gate_regression or {}).values())


def build_record(*, slot_id, condition, condition_access, policy, account,
                 terminal_status, claim_success, feedback_text=None,
                 guidance_text=None, donor_run_id=None, gate_target="NOT_RUN",
                 gate_regression=None, gate_contract="NOT_RUN",
                 gate_contract_codes=None, gate_independent="NOT_RUN",
                 false_reject=False, edited_paths=None,
                 first_edit_after_execution=False, deviation_codes=None,
                 evidence_path="", notes=""):
    """One record, in the shape the data dictionary declares."""
    source = feedback_source_for(condition_access)

    # 3.3 - the information-supply surface
    if source == FEEDBACK_SOURCE_NONE:
        if feedback_text:
            raise RecordError(
                "condition %s delivers no feedback but feedback_text was given"
                % (condition,))
        payload_sha = None
    else:
        if not feedback_text:
            raise RecordError(
                "condition %s must deliver feedback but feedback_text is empty"
                % (condition,))
        payload_sha = sha256_text(feedback_text)

    if source == FEEDBACK_SOURCE_GUIDED:
        if not guidance_text:
            raise RecordError("a guided record needs the guidance text it sent")
        guidance_sha = sha256_text(guidance_text)
    else:
        if guidance_text:
            raise RecordError(
                "condition %s carries no guidance but guidance_text was given"
                % (condition,))
        guidance_sha = None

    if source == FEEDBACK_SOURCE_DONOR:
        if not donor_run_id:
            raise RecordError("a donor record must name the run it borrowed from")
    else:
        if donor_run_id:
            raise RecordError(
                "condition %s borrows no run but donor_run_id was given"
                % (condition,))
        donor_run_id = None

    if source == FEEDBACK_SOURCE_GUIDED or source == FEEDBACK_SOURCE_OWN:
        pass

    record = {
        "slot_id": slot_id,
        "condition": condition,
        "feedback_source": source,
        "feedback_payload_sha256": payload_sha,
        "guidance_sha256": guidance_sha,
        "donor_run_id": donor_run_id,
        "visibility_policy_id": policy.policy_id,
        "visibility_policy_fingerprint": policy.fingerprint(),
    }
    record.update(account or {})

    for name, value in (("gate_target", gate_target),
                        ("gate_independent", gate_independent)):
        if value not in GATE_ENUM:
            raise RecordError("%s must be one of %s, got %r"
                              % (name, ", ".join(GATE_ENUM), value))
    if gate_contract not in ("PASS", "FAIL", "NOT_RUN"):
        raise RecordError("gate_contract must be PASS/FAIL/NOT_RUN, got %r"
                          % (gate_contract,))

    gates_ok = all_gates_passed(gate_target, gate_regression, gate_contract,
                                gate_independent)
    # 3.5: "claimed success but G1-G4 did not all pass". Derived, not asserted by
    # the caller, so it cannot be set to whatever makes the table look good.
    false_accept = bool(claim_success) and not gates_ok

    record.update({
        "terminal_status": terminal_status,
        "claim_success": bool(claim_success),
        "gate_target": gate_target,
        "gate_regression": dict(gate_regression or {}),
        "gate_contract": gate_contract,
        "gate_contract_codes": list(gate_contract_codes or []),
        "gate_independent": gate_independent,
        "false_accept": false_accept,
        # 3.5 says this needs human review before it can be true, so it is never
        # inferred here; it can only be passed in by someone who looked.
        "false_reject": bool(false_reject),
        # 3.6 process surface
        "edited_paths": list(edited_paths or []),
        "first_edit_after_execution": bool(first_edit_after_execution),
        "deviation_codes": list(deviation_codes or []),
        "evidence_path": str(evidence_path or ""),
        "notes": str(notes or ""),
    })
    return record
