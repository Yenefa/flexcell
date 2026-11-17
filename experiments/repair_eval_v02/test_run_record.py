"""Does the record this code emits match the schema the document declares?

The data dictionary is the single source of truth for the run-record fields, so
this test reads the tables out of DATA_DICTIONARY.md rather than restating them.
A field added to the document fails here until the code catches up, and a field
the code invents fails too, because the check is two-way.
"""
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (str(HERE), str(ROOT), str(ROOT / "benchmark" / "repair_eval" / "contracts")):
    if path not in sys.path:
        sys.path.insert(0, path)

import budget as B                                    # noqa: E402
import run_record as R                                # noqa: E402
from benchmark.repair_eval import visibility as vis    # noqa: E402

DICT_PATH = ROOT / "docs" / "research" / "evobot-paper-v02" / "DATA_DICTIONARY.md"

# what each declared type must look like in Python
TYPE_CHECKS = {
    "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "float": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "string": lambda v: isinstance(v, str),
    "bool": lambda v: isinstance(v, bool),
    "map": lambda v: isinstance(v, dict),
    "list": lambda v: isinstance(v, list),
    "enum": lambda v: isinstance(v, str),
}

FIELD_RE = re.compile(r"`([a-z_0-9]+)`")


def declared_fields(section):
    """Pull (name, type) pairs out of one table in the data dictionary."""
    text = DICT_PATH.read_text(encoding="utf-8")
    start = text.index(section)
    rest = text[start:]
    end = rest.find(chr(10) + "### ", 4)
    body = rest if end < 0 else rest[:end]
    fields = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        match = FIELD_RE.fullmatch(cells[0])
        if not match:
            continue
        required = (len(cells) < 5) or (cells[4].strip() == "是")
        fields.append((match.group(1), cells[1], required))
    return fields


def a_policy():
    return vis.load_policy(ROOT / "benchmark" / "repair_eval" / "visibility_policy.json")


class _Transport:
    def chat(self, messages, **kwargs):
        return {"text": "ok", "usage": {"prompt_tokens": 10, "completion_tokens": 5}}


def a_record(condition="B_REAL_FEEDBACK", **over):
    policy = a_policy()
    ledger = B.Ledger(_Transport())
    ledger.chat([{"role": "user", "content": "hi"}])
    ledger.count_execution()
    ledger.count_final_scene()
    ledger.finish()
    kwargs = dict(
        slot_id="F1-B-r1", condition=condition,
        condition_access=policy.conditions[condition],
        policy=policy, account=ledger.account(),
        terminal_status="PASS", claim_success=True,
        feedback_text="REAL FAILURE: registry returned []",
        guidance_text=None, donor_run_id=None,
        gate_target="PASS", gate_regression={"layout_x|s1": "PASS"},
        gate_contract="PASS", gate_contract_codes=[], gate_independent="NOT_RUN",
    )
    kwargs.update(over)
    return R.build_record(**kwargs)


# ------------------------------------------- the document is the source of truth
SECTIONS = ("### 3.3", "### 3.4", "### 3.5", "### 3.6")


def test_the_data_dictionary_declares_the_fields_we_ship():
    for section in SECTIONS:
        fields = declared_fields(section)
        assert fields, "no table parsed out of " + section
        record = a_record()
        for name, declared, required in fields:
            if required:
                assert name in record, "%s declares %r but the record omits it" % (section, name)
            if name not in record:
                continue
            check = TYPE_CHECKS.get(declared)
            assert check is not None, "unknown declared type %r for %r" % (declared, name)
            value = record[name]
            if value is None and declared in ("string", "enum"):
                continue                       # declared optional-by-null
            assert check(value), "%r should be %s, got %r" % (name, declared, value)


def test_false_accept_is_derived_not_asserted():
    ok = a_record(gate_target="PASS", gate_independent="PASS", gate_contract="PASS",
                  gate_regression={"a": "PASS"}, claim_success=True)
    assert ok["false_accept"] is False
    missed = a_record(gate_target="FAIL", claim_success=True)
    assert missed["false_accept"] is True
    honest = a_record(gate_target="FAIL", claim_success=False)
    assert honest["false_accept"] is False


def test_an_unmeasured_gate_does_not_count_as_a_verified_success():
    record = a_record(gate_target="PASS", gate_independent="NOT_RUN", claim_success=True)
    assert record["false_accept"] is True


def test_a_false_reject_is_never_inferred_by_this_code():
    assert a_record()["false_reject"] is False


def test_the_process_surface_is_carried_through():
    record = a_record(edited_paths=["skill/registry.py"],
                      first_edit_after_execution=True,
                      deviation_codes=["D-ENV"], evidence_path="runs/F1-B-r1",
                      notes="")
    assert record["edited_paths"] == ["skill/registry.py"]
    assert record["first_edit_after_execution"] is True
    assert record["deviation_codes"] == ["D-ENV"]
    assert record["evidence_path"] == "runs/F1-B-r1"


def test_the_record_invents_no_field_the_document_does_not_declare():
    declared = {name for section in SECTIONS
                for name, _, _ in declared_fields(section)}
    record = a_record()
    allowed_extra = {"slot_id", "condition", "visibility_policy_fingerprint"}
    invented = set(record) - declared - allowed_extra
    assert not invented, "record carries undeclared fields: %s" % sorted(invented)


# ------------------------------------------------- the vocabulary mapping
@pytest.mark.parametrize("condition,expected", [
    ("A_STATIC", "none"),
    ("B_REAL_FEEDBACK", "own_run"),
    ("C_MISMATCHED_FEEDBACK", "donor_run"),
    ("D_GUIDED", "own_run_plus_guidance"),
])
def test_the_policy_vocabulary_maps_onto_the_record_vocabulary(condition, expected):
    policy = a_policy()
    assert R.feedback_source_for(policy.conditions[condition]) == expected


def test_every_policy_condition_has_a_mapping():
    policy = a_policy()
    for name, access in policy.conditions.items():
        assert access.feedback_source in R.POLICY_TO_RECORD, (
            "policy condition %s uses feedback_source %r with no record mapping"
            % (name, access.feedback_source))


def test_an_unmapped_policy_vocabulary_is_refused_rather_than_written_through():
    class Odd:
        feedback_source = "some_new_thing"
        guidance = None
    with pytest.raises(R.RecordError):
        R.feedback_source_for(Odd())


# ------------------------------------------------------- the surface rules
def test_a_delivers_no_payload_and_carries_no_donor():
    record = a_record(condition="A_STATIC", feedback_text=None)
    assert record["feedback_source"] == "none"
    assert record["feedback_payload_sha256"] is None
    assert record["guidance_sha256"] is None
    assert record["donor_run_id"] is None


def test_a_that_smuggles_feedback_is_refused():
    with pytest.raises(R.RecordError):
        a_record(condition="A_STATIC", feedback_text="you failed at registry.py")


def test_a_condition_that_must_deliver_feedback_cannot_deliver_nothing():
    with pytest.raises(R.RecordError):
        a_record(condition="B_REAL_FEEDBACK", feedback_text=None)


def test_c_must_name_its_donor():
    with pytest.raises(R.RecordError):
        a_record(condition="C_MISMATCHED_FEEDBACK", donor_run_id=None)


def test_only_c_may_name_a_donor():
    with pytest.raises(R.RecordError):
        a_record(condition="B_REAL_FEEDBACK", donor_run_id="RUN-0002")


def test_d_hashes_the_guidance_it_sent():
    text = "Consume the remaining retry budget before giving up."
    record = a_record(condition="D_GUIDED", guidance_text=text)
    assert record["guidance_sha256"] == R.sha256_text(text)


def test_a_guidance_hash_requires_the_guidance_text():
    with pytest.raises(R.RecordError):
        a_record(condition="D_GUIDED", guidance_text=None)


def test_only_d_may_carry_guidance():
    with pytest.raises(R.RecordError):
        a_record(condition="B_REAL_FEEDBACK", guidance_text="try harder")


def test_the_feedback_digest_is_of_the_text_actually_delivered():
    text = "REAL FAILURE: registry returned []"
    record = a_record(condition="B_REAL_FEEDBACK", feedback_text=text)
    assert record["feedback_payload_sha256"] == R.sha256_text(text)
    other = a_record(condition="B_REAL_FEEDBACK", feedback_text=text + " ")
    assert other["feedback_payload_sha256"] != record["feedback_payload_sha256"]


# --------------------------------------------------------- digest convention
def test_the_digest_does_not_depend_on_the_line_endings_of_the_platform():
    """Windows and Linux must not record different numbers for one payload.

    Measured before this existed: the same two lines hashed to e9024f1a with LF
    and 6612d9c9 with CRLF, so a record written on one platform could not be
    compared with a record written on the other.
    """
    lf = "line one" + chr(10) + "line two" + chr(10)
    crlf = "line one" + chr(13) + chr(10) + "line two" + chr(13) + chr(10)
    cr = "line one" + chr(13) + "line two" + chr(13)
    assert R.sha256_text(lf) == R.sha256_text(crlf) == R.sha256_text(cr)
    assert R.DIGEST_CONVENTION == "utf8-lf-sha256/1"


def test_a_byte_payload_is_never_normalised():
    """Bytes are the evidence; normalising them would change what was measured."""
    assert R.sha256_bytes(b"a" + bytes([13]) + bytes([10]) + b"b") != \
        R.sha256_bytes(b"a" + bytes([10]) + b"b")


def test_text_and_bytes_are_not_interchangeable():
    with pytest.raises(TypeError):
        R.sha256_text(b"bytes")
    with pytest.raises(TypeError):
        R.sha256_bytes("text")


def test_the_record_digests_follow_the_documented_convention():
    text = "REAL FAILURE: registry returned []" + chr(10)
    record = a_record(condition="B_REAL_FEEDBACK", feedback_text=text)
    assert record["feedback_payload_sha256"] == R.sha256_text(text)


# ------------------------------------------------------------ gate surface
def test_an_invented_gate_value_is_refused():
    with pytest.raises(R.RecordError):
        a_record(gate_target="OK")


def test_gates_default_to_not_run_rather_than_a_guess():
    policy = a_policy()
    ledger = B.Ledger(_Transport())
    record = R.build_record(slot_id="s", condition="B_REAL_FEEDBACK",
                            condition_access=policy.conditions["B_REAL_FEEDBACK"],
                            policy=policy, account=ledger.account(),
                            terminal_status="NOT_RUN", claim_success=False,
                            feedback_text="x")
    assert record["gate_target"] == "NOT_RUN"
    assert record["gate_independent"] == "NOT_RUN"
    assert record["gate_regression"] == {}
    assert record["gate_contract_codes"] == []
