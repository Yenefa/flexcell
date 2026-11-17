"""End-to-end dry run of a real instance with a scripted agent. No model tokens.

WHY
    The runner has just been wired to the pre-registered instances. Wiring that
    has never been exercised is a plan, not a pipeline: the round-2 lesson from
    the synthetic fixtures was that four defects only appeared once the whole
    loop ran with something standing in for the model.

    This substitutes a transport that always replies with the reference repair,
    which is the repair a perfect agent would produce on its first interaction.
    If the slot does not come back ACCEPT, the pipeline is wrong - not the model,
    because there is no model.

WHAT IT PROVES
    materialize -> boundary -> agent write -> gate -> record, for both
    pre-registered instances, including the sealed gate reading the file the
    agent wrote through the boundary.

WHAT IT CANNOT PROVE
    Anything about how a real model behaves. A scripted agent that already knows
    the answer says nothing about whether a repairer can find it.
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

import instances as IN              # noqa: E402
import run_matrix_real as R         # noqa: E402
from benchmark.repair_eval import visibility as vis  # noqa: E402


class ScriptedTransport:
    """Replies with the reference repair, written only inside its granted surface.

    The first version wrote IN.editable_rel(instance) - the correct path, known
    out of band. That meant it succeeded even when the runner granted the agent
    "skill/", the synthetic fixture's surface: a stand-in that is too clever
    tests the gate but not the boundary the real agent actually obeys. Four real
    slots and 35,140 tokens later that mistake surfaced for real.

    It now resolves the destination from the editable_fields it was granted,
    via surface_provider(). If the runner grants the wrong surface, the write
    lands in the wrong place and the sealed gate fails, without needing a
    separate assertion to notice.
    """

    def __init__(self, family, surface_provider=None, *args, **kwargs):
        self.family = "DEF-F1-REG" if family.startswith("F1") else "DEF-F2-MAP"
        self.surface_provider = surface_provider
        self.calls = 0

    def metadata(self):
        return {"requested_model": "scripted", "base_url": "-", "temperature": 0,
                "max_tokens": 0, "key_fingerprint": "scripted", "key_source": "none",
                "gate": "none", "adapter": "ScriptedTransport/1"}

    def chat(self, messages, **kwargs):
        self.calls += 1
        # Remember what the agent was told it could edit. Four real-instance
        # slots were spent discovering that this was still the synthetic
        # contract's "skill/" - the agent obeyed it and never touched the
        # instance, and every slot failed for a reason that had nothing to do
        # with the model.
        self.seen_prompt = json.dumps(messages, ensure_ascii=False)
        instance = self.family
        granted = (self.surface_provider() if self.surface_provider else None) or []
        if not granted:
            # no surface was communicated at all: write where it would have gone
            # and let the gate fail, rather than silently helping the runner
            rel = IN.editable_rel(instance)
        else:
            base = str(granted[0]).rstrip("/")
            rel = base + "/" + Path(IN.editable_rel(instance)).name
        body = IN.healthy_text(instance)
        return {"text": json.dumps({"actions": [{"write_file": [rel, body]}],
                                    "claim_success": True, "done": True}),
                "usage": {"total_tokens": 0, "split_available": False},
                "model_returned": "scripted", "seconds": 0.0}


def main():
    policy = vis.load_policy(Path(HERE.parents[1]) / "benchmark" / "repair_eval"
                             / "visibility_policy.json")
    original = R.GatedTransport
    original_agent = R.RepairAgent
    report = {}
    ok = True
    for family in ("F1_OBJECT_REGISTRATION", "F2_GOAL_MAPPING"):
        captured = {}
        def factory(model=None, base_url=None, timeout=None, caller="x", _f=family):
            transport = ScriptedTransport(
                _f, surface_provider=lambda: captured.get("editable_fields") or [])
            captured["transport"] = transport
            return transport

        class RecordingAgent(R.RepairAgent):
            """Capture the editable surface the agent is actually handed.

            Searching the rendered prompt for "config/" proved nothing: the task
            text itself names config/week1.yaml, so that string is present either
            way and the check passed with the fix removed. The argument is what
            the boundary enforces, so the argument is what gets asserted.
            """

            def __init__(self, ledger, boundary, task, editable, *a, **kw):
                super().__init__(ledger, boundary, task, editable, *a, **kw)
                captured["editable_fields"] = list(editable)
        R.GatedTransport = factory
        R.RepairAgent = RecordingAgent
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            donor = tmp / "donor"
            (donor / "telemetry").mkdir(parents=True)
            (donor / "telemetry" / "execution.log").write_text("DONOR" + chr(10))
            work = tmp / "slot"
            work.mkdir()
            row = R.run_slot(family, "B_REAL_FEEDBACK", 1, work, policy, donor,
                             "scripted", 3, seed=5101, source_sha=R.health.checked_run(
                                 ["git", "rev-parse", "HEAD"], cwd=R.ROOT).stdout.strip(),
                             source="instances")
        R.GatedTransport = original
        R.RepairAgent = original_agent
        entry = {"terminal": row["terminal_status"],
                 "verdict": row.get("contract_verdict"),
                 "qualification": row.get("qualification"),
                 "writes": row.get("edited_paths"),
                 "codes": row.get("gate_contract_codes")}
        report[family] = entry
        surface = str(Path(IN.editable_rel(
            "DEF-F1-REG" if family.startswith("F1") else "DEF-F2-MAP")).parent) + "/"
        entry["editable_surface"] = surface
        told = (captured.get("prompt") or "")
        fields = captured.get("editable_fields") or []
        entry["editable_fields"] = fields
        entry["surface_authorized"] = any(surface.startswith(f) or f.startswith(surface)
                                          for f in fields)
        if not entry["surface_authorized"]:
            ok = False
            print("  !! the agent was handed %r, not the instance surface %r"
                  % (fields, surface))
        good = entry["verdict"] == "ACCEPT" and entry["writes"]
        if not good:
            ok = False
        print("%-24s verdict=%-6s terminal=%-8s writes=%s"
              % (family, entry["verdict"], entry["terminal"], entry["writes"]))
    print(json.dumps({"ok": ok, "slots": report}, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
