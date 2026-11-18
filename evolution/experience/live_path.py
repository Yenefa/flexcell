#!/usr/bin/env python3
"""Is the continual chain connected to the path that actually plans a robot run?

THE GAP THIS EXISTS FOR
    Everything up to now is connected INSIDE the chain's own harness: an entry is generated,
    reviewed, gated, delivered, retrieved, applied to an archived run, and recorded. The demo
    proves that chain works. It does not prove the chain is where a plan is made.

    It is not. There are TWO stores with TWO schemas:

        evolution/experience/records.jsonl                     <- the live path reads this
            lesson, validated, provenance_verified, record_sha256, failure_class, ...

        setup/acceptance/evobot_continual_chain_.../records_v2.jsonl   <- the chain writes this
            entry_id, suggested_action, consumer, action_kind, version, validation, ...

    and zero lessons appear in both. So the chain's ACTIVE entries are invisible to
    experiments/baselines/baseline_c.py, which is the code that hands experience to the
    planner for a real run. The loop is correct and unplugged.

    A SCHEMA MISMATCH IS NOT THE REAL REASON, AND THIS FILE FIRST SAID IT WAS. Looking at
    the two ACTIVE entries more closely showed the first explanation was too coarse:

        auto-harness_dds_exhaustion  failure_class=tooling, consumer=harness
        E2                           failure_class=control, consumer=executor_recovery

    The live path's retrieve() admits only failure_class in (planning, state) and its
    _NON_PLANNER word list excludes "landing", "spread", "participant" - so BOTH entries
    are excluded BY DESIGN, not by an accident of field names. No schema bridge would make
    them visible: the live retrieve() is planner-only, and neither entry is a planner entry.

    The real reason is stronger and worse: THE LIVE RUN PATH HAS NO CONSUMER for either
    harness or executor experience. run_baseline_b.py and baseline_c.py never call
    apply_respread and never apply a DDS config from an entry. Both are hard-coded into the
    stack. So the chain learned to improve two consumers that the live path does not read.

    Choosing a schema (the original two "options") would therefore "fix" nothing: it would
    bridge two lessons into a filter that correctly refuses them, and the robot would behave
    exactly as before. The options below state that plainly.

WHAT IT REPORTS
    active_entries            how many ACTIVE entries the chain holds
    visible_to_live_path      how many of them the live retrieval filter would admit
    by_reason                 why each invisible one is invisible
    planner_filter_result     would the live planner filter admit a bridged entry?
    consumers_in_live_path    which of the entry's consumers exist in the live run scripts
    options                   the real ways to close it, with what each costs
"""
import json
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import store  # noqa: E402

LIVE_STORE = os.path.join(WT, "evolution", "experience", "records.jsonl")
LIVE_LEDGER = os.path.join(WT, "evolution", "experience", "review_ledger.jsonl")
CHAIN_STORE = os.path.join(WT, "setup", "acceptance", "evobot_continual_chain_20261118",
                           "records_v2.jsonl")


def _live_verdicts(path):
    """record_sha256 -> latest verdict, exactly as the live path reads it."""
    if not os.path.exists(path):
        return {}
    out = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        out[entry.get("record_sha256")] = entry.get("verdict")
    return out


def live_filter_admits(record, verdicts):
    """Would baseline_c.retrieve() let this record through? (None, reason) when not.

    Reproduces the live filter rather than guessing at it: provenance_verified must be True
    AND the review ledger must hold an explicit ACCEPT for the record's own digest.
    """
    if record.get("provenance_verified") is not True:
        return False, "no provenance_verified"
    digest = record.get("record_sha256")
    if verdicts.get(digest) != "ACCEPT":
        return False, "no independent ACCEPT in the review ledger"
    return True, None


def report(live_store=None, live_ledger=None, chain_store=None):
    """Count the chain's ACTIVE entries that the live planning path can actually see."""
    live_store = live_store or LIVE_STORE
    live_ledger = live_ledger or LIVE_LEDGER
    chain_store = chain_store or CHAIN_STORE
    verdicts = _live_verdicts(live_ledger)
    live_rows = store.read(live_store)
    live_lessons = {str(r.get("lesson") or "") for r in live_rows}
    chain_rows = [r for r in store.read(chain_store)
                  if (r.get("version") or {}).get("status") == "ACTIVE"]
    by_reason, visible, detail = {}, 0, []
    for row in chain_rows:
        # The chain record is v2; hand it to the v1 filter unchanged. That is the honest
        # test: if the live path cannot read the record AS IT IS, it is not connected.
        admits, why = live_filter_admits(row, verdicts)
        text = str(row.get("suggested_action") or "")
        in_store = text and text in live_lessons
        if admits and in_store:
            visible += 1
            detail.append({"entry": (row.get("version") or {}).get("label"),
                           "visible": True})
            continue
        if not admits:
            reason = why
        else:
            reason = "admitted by the filter but absent from the live store"
        by_reason[reason] = by_reason.get(reason, 0) + 1
        detail.append({"entry": (row.get("version") or {}).get("label"),
                       "visible": False, "why": reason})
    # THE LIVE PATH IS PLANNER-ONLY. Its retrieve() keeps failure_class in (planning, state)
    # and its _NON_PLANNER word list rejects "landing", "spread", "participant". Test each
    # ACTIVE entry against that filter directly: a schema bridge cannot rescue an entry the
    # filter refuses by design.
    planner_filter = _live_planner_filter()
    filter_result = []
    for row in chain_rows:
        text = str(row.get("suggested_action") or row.get("lesson") or "")
        cls = row.get("failure_class")
        cls_ok = cls in ("planning", "state")
        word_ok = not any(w in text.lower() for w in planner_filter["non_planner"])
        filter_result.append({"entry": (row.get("version") or {}).get("label"),
                              "failure_class": cls, "class_admitted": cls_ok,
                              "word_admitted": word_ok,
                              "would_a_bridge_help": cls_ok and word_ok})
    live_scripts = _live_run_scripts()
    consumer_presence = {}
    for row in chain_rows:
        consumer = row.get("consumer")
        consumer_presence[consumer] = {
            "call_sites_in_live_scripts": live_scripts.get(consumer, []),
            "has_a_live_consumer": bool(live_scripts.get(consumer)),
        }
    return {
        "active_entries": len(chain_rows),
        "visible_to_live_path": visible,
        "by_reason": by_reason,
        "entries": detail,
        "live_store_rows": len(live_rows),
        "planner_filter": planner_filter,
        "planner_filter_result": filter_result,
        "consumers_in_live_path": consumer_presence,
        "chain_store": os.path.relpath(chain_store, WT),
        "live_store": os.path.relpath(live_store, WT),
        "options": [
            {"option": "bridge the two v2 entries into the live store",
             "cost": ("NOTHING - retrieve() admits only planning/state classes and rejects "
                      "landing/spread/participant words; both entries are excluded by design, "
                      "so the robot would behave exactly as before")},
            {"option": "give the live run path the missing consumers",
             "cost": ("run_baseline_b.py and baseline_c.py must actually CALL the executor "
                      "respread and the harness config that the entries describe, with a "
                      "reviewed gate before each call - this changes the frozen baseline")},
        ],
        "claim": ("the chain is correct and UNPLUGGED, and a schema bridge is NOT the fix: "
                  "the live path is planner-only and has no harness/executor consumer at "
                  "all. The two ACTIVE entries are for consumers the robot never reads. "
                  "Only adding those consumers to the live path closes the loop"),
    }


def _live_planner_filter():
    """The live retrieve() constants, read from the file rather than copied by hand."""
    path = os.path.join(WT, "experiments", "baselines", "baseline_c.py")
    src = open(path, encoding="utf-8").read()
    import ast
    tree = ast.parse(src)
    out = {"non_planner": [], "classes": []}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "_NON_PLANNER":
                try:
                    out["non_planner"] = list(ast.literal_eval(node.value))
                except (ValueError, TypeError):
                    pass
            if isinstance(target, ast.Name) and target.id == "PLANNER_RELEVANT_CLASSES":
                try:
                    out["classes"] = sorted(ast.literal_eval(node.value.args[0]))
                except (ValueError, TypeError, AttributeError, IndexError):
                    pass
    return out


def _live_run_scripts():
    """Which entry consumers are actually called by the scripts that run a baseline?"""
    root = os.path.join(WT, "experiments", "baselines")
    calls = {"executor_recovery": ["apply_respread", "recover"],
             "harness": ["apply_harness", "cyclonedds", "participant_capacity"],
             "planner": ["validate_plan", "describe"],
             "spread_policy": ["spread("]}
    out = {consumer: [] for consumer in calls}
    for name in sorted(os.listdir(root)):
        if not name.startswith("run_") or not name.endswith(".py"):
            continue
        src = open(os.path.join(root, name), encoding="utf-8").read()
        for consumer, symbols in calls.items():
            for symbol in symbols:
                if symbol in src:
                    out[consumer].append("%s:%s" % (name, symbol))
    return out


if __name__ == "__main__":
    print(json.dumps(report(), indent=2, ensure_ascii=False))
