"""The feedback a slot receives must come from the source that slot uses.

Four times in this project a new source of truth was added and the path that
reads it was not switched with it. The last one: instance slots refreshed their
initial message from the sealed gate, but the per-step refresh still called the
synthetic pytest helper, which ran in a workspace with no tests and overwrote the
gate's typed answer. Conditions B and C then received "no tests ran" instead of
a reason code, and the contrast the experiment exists to measure was gone.

This test drives one instance slot with a transport that does not finish on its
first reply, and checks what the second call was told.
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
for path in (str(HERE), str(HERE.parents[1]),
             str(HERE.parents[1] / "benchmark" / "repair_eval" / "contracts")):
    if path not in sys.path:
        sys.path.insert(0, path)

import run_matrix_real as R          # noqa: E402
from benchmark.repair_eval import visibility as vis  # noqa: E402

KNOWN_CODES = {"PASS", "OBJECT_NOT_REGISTERED", "CONFIG_UNPARSEABLE",
               "CONFIG_SECTION_MISSING", "CONFIG_PARAMS_MISSING",
               "CONFIG_PARAMS_MALFORMED", "CONFIG_BAD_TYPE", "GATE_FAILED"}


class TwoStepTransport:
    """Repairs on the second turn, and remembers what it was told between."""

    def __init__(self):
        self.calls = 0
        self.seen = []

    def metadata(self):
        return {"requested_model": "scripted", "base_url": "-", "temperature": 0,
                "max_tokens": 0, "key_fingerprint": "scripted", "key_source": "none",
                "gate": "none", "adapter": "TwoStepTransport/1"}

    def chat(self, messages, **kwargs):
        self.calls += 1
        self.seen.append(json.dumps(messages, ensure_ascii=False))
        if self.calls == 1:
            return {"text": json.dumps({"actions": [], "done": False}),
                    "usage": {"total_tokens": 0, "split_available": False},
                    "model_returned": "scripted", "seconds": 0.0}
        body = ("observe_server:\n  ros__parameters:\n    tracked_objects: "
                "['target_box_a', 'target_box_b']\n    zones: ['zone_1', 'zone_2']\n")
        return {"text": json.dumps({"actions": [{"write_file": ["config/week1.yaml", body]}],
                                    "claim_success": True, "done": True}),
                "usage": {"total_tokens": 0, "split_available": False},
                "model_returned": "scripted", "seconds": 0.0}


def test_the_second_interaction_is_told_the_gates_answer():
    policy = vis.load_policy(Path(HERE.parents[1]) / "benchmark" / "repair_eval"
                             / "visibility_policy.json")
    original = R.GatedTransport
    transport = TwoStepTransport()
    R.GatedTransport = lambda *a, **kw: transport
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            donor = tmp / "donor"
            (donor / "telemetry").mkdir(parents=True)
            (donor / "telemetry" / "execution.log").write_text("DONOR" + chr(10))
            work = tmp / "slot"
            work.mkdir()
            row = R.run_slot("F1_OBJECT_REGISTRATION", "B_REAL_FEEDBACK", 1, work,
                             policy, donor, "scripted", 4, seed=5101,
                             source_sha=R.health.checked_run(
                                 ["git", "rev-parse", "HEAD"], cwd=R.ROOT).stdout.strip(),
                             source="instances")
    finally:
        R.GatedTransport = original

    assert transport.calls >= 2, "the two-step transport was never asked twice"
    second = transport.seen[1]
    assert any(code in second for code in KNOWN_CODES), \
        "the second interaction was not told a gate code: %s" % second[-400:]
    assert "no tests ran" not in second and "ERROR: file or directory not found" not in second, \
        "the second interaction got the synthetic test runner's output"
    assert row["qualification"].endswith("|INSTANCE")
    first_request = json.loads(transport.seen[0])
    delivered = next(m["content"].removeprefix("EXECUTION FEEDBACK\n")
                     for m in first_request if m["content"].startswith("EXECUTION FEEDBACK\n"))
    assert row["feedback_payload_sha256"] == R.REC.sha256_text(delivered)
