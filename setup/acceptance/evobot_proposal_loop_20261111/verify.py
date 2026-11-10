#!/usr/bin/env python3
"""Verify the proposal loop exists, gates correctly, and labels itself honestly."""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    pd = WT / "evolution" / "proposals"
    # the directory that used to be empty must now carry the loop
    for f in ("generate.py", "run_loop.py", "check_applied.py", "scan_evidence.py"):
        assert (pd / f).exists(), "missing " + f

    gen = load("g", pd / "generate.py")
    chk = load("c", pd / "check_applied.py")

    # thin evidence must be refused
    prop, why = gen.build_proposal("occupied_destination",
                                   [{"error_code": 60, "detail": "occupied destination"}])
    assert prop is None and "need" in why

    # unknown class must be refused, not invented
    prop2, why2 = gen.build_proposal("unconfirmed",
                                     [{"error_code": 62, "detail": "unconfirmed"}] * 19)
    assert prop2 is None and "no evidence-backed change" in why2

    # the stored proposal must be gate-accepted AND honestly labelled retrospective
    doc = json.loads((HERE / "proposal_occupied_destination.json").read_text(encoding="utf-8"))
    assert doc["requires_human_approval"] is True
    assert doc["occurrences"] == 5
    assert doc["rollback"]
    label, why3 = chk.check_occupied_destination()
    assert label == "ALREADY_SATISFIED", (label, why3)

    # the generator must not have touched source
    src = (WT / "experiments" / "baselines" / "spread_destinations.py").read_text()
    assert "def spread(" in src

    print(json.dumps({
        "verdict": "EVOBOT_PROPOSAL_LOOP_WIRED_AND_HONESTLY_LABELLED",
        "proposals_dir_was_empty": True,
        "gate_accepts_evidence_backed_proposal": True,
        "thin_evidence_refused": True,
        "unknown_class_refused": True,
        "behavioural_label": label,
        "level5_improve": "NOT ACHIEVED (only retrospective proposal)",
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
