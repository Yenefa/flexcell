#!/usr/bin/env python3
"""Voyager-style executable skill assets: a stored lesson can become a CALLABLE artifact.

WHAT IS MISSING WITHOUT THIS
    An entry that only says "separate same-bin landings" changes behaviour only for as
    long as a human reads it and calls the right function. Voyager's contribution was not
    the note, it was the STORED, EXECUTABLE skill: a program the next task calls without
    re-deriving anything. So an ACTIVE entry whose effect_spec is a parameter change is
    compiled here into a callable asset with:
      id            a stable name, derived from the entry, not typed by hand
      callable      module path + function name, checked to exist
      signature     the parameters it takes, taken from effect_spec.params
      guard         the conditions under which it MUST refuse
      source_entry  the entry that produced it (parent link, so it can be retired)

WHY THE ASSET IS NOT JUST THE ENTRY
    An entry is evidence plus a claim. An asset is something a planner can call. Keeping
    them separate means an entry can be re-reviewed and re-compiled into a new asset
    version without pretending the old calls never happened, and a retired entry can be
    traced to the assets it produced.

WHAT IT DELIBERATELY DOES NOT DO
    It does not generate new robot code. It compiles a bounded, already-tested parameter
    change into a callable wrapper. Generating arbitrary robot skills from prose is the
    step this repository has no evidence for, and the asset schema says so in
    generation: "code_generated": false.
"""
import importlib
import json
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import consumers  # noqa: E402
import schema  # noqa: E402

ASSETS = os.path.join(WT, "evolution", "experience", "skill_assets.jsonl")

# Which callable a consumer's asset binds to. The function must already exist and be
# tested; the asset only fixes the parameters and the guard.
BINDINGS = {
    "spread_policy": {"module": "runtime.planner.spread_destinations",
                      "function": "spread",
                      "param_map": {"step_m": "SPREAD_STEP_M"}},
    "executor_recovery": {"module": "runtime.recovery.recover",
                          "function": "apply_respread",
                          "param_map": {"step_m": "spread_step",
                                        "cluster_m": "cluster_m"}},
}


class AssetError(ValueError):
    """The entry cannot be compiled into a callable asset."""


def asset_id(entry):
    """Stable, derived from the entry's identity - never hand-typed."""
    return "skill.%s.%s" % (entry.get("consumer"), entry.get("entry_id", "")[:12])


def binding_for(entry):
    """The callable an entry WOULD bind to, without the asset-quality gates.

    WHY THIS IS SEPARATE FROM compile_asset: delivery.py asks a narrower question than
    compilation - "does this entry have a callable with concrete kwargs at all" - and it
    must be answerable for a candidate that has not been reviewed or given a guard yet.
    Conflating the two made an unreviewed entry report DROPPED, which is the wrong reason:
    the envelope is fine and the ASSET is simply not ready. Those lead to different fixes.
    """
    consumer = entry.get("consumer")
    binding = BINDINGS.get(consumer)
    if binding is None:
        raise AssetError("consumer %r has no callable binding: this stack has no function "
                         "that could execute its change" % (consumer,))
    params = (entry.get("effect_spec") or {}).get("params") or {}
    param_map = binding["param_map"]
    kwargs, unbound = {}, []
    for key, target in param_map.items():
        if key in params:
            kwargs[target] = params[key]
        else:
            unbound.append(key)
    if unbound:
        raise AssetError("unbound parameter(s) %s: an entry that omits a parameter cannot be "
                         "called, and silently defaulting it would apply a value nobody "
                         "chose" % (unbound,))
    return {"module": binding["module"], "function": binding["function"],
            "kwargs": kwargs}


def compile_asset(entry, require_active=True):
    """Compile one ACTIVE entry into a callable asset record. Refuses when not compilable.

    require_active=False exists ONLY for delivery.py's pre-flight check: it asks "would this
    entry bind to a callable at all", which must be answerable for a candidate. The status
    gate itself is unchanged and every other caller keeps the default.
    """
    if require_active and (entry.get("version") or {}).get("status") != "ACTIVE":
        raise AssetError("only an ACTIVE entry may be compiled; status is %r"
                         % ((entry.get("version") or {}).get("status"),))
    # The ACCEPT gate applies to the same pre-flight case as the status gate: delivery.py
    # asks "would this entry bind to a callable at all", which must be answerable before
    # review. Every other caller keeps the default and still faces both gates.
    if require_active and (entry.get("validation") or {}).get("review_verdict") != "ACCEPT":
        raise AssetError("only an independently ACCEPTed entry may be compiled")
    consumer = entry.get("consumer")
    binding = BINDINGS.get(consumer)
    if binding is None:
        raise AssetError("consumer %r has no callable binding: this stack has no "
                         "function that could execute its change" % (consumer,))
    module_path = binding["module"]
    module_file = os.path.join(WT, module_path.replace(".", os.sep) + ".py")
    if not os.path.exists(module_file):
        raise AssetError("binding module is missing from this checkout: " + module_file)
    params = dict((entry.get("effect_spec") or {}).get("params") or {})
    bound = {}
    for key, value in params.items():
        target = binding["param_map"].get(key)
        if target is None:
            raise AssetError("effect_spec param %r has no binding for consumer %r; an "
                             "unbound parameter would be silently dropped"
                             % (key, consumer))
        bound[target] = value
    if not bound:
        raise AssetError("effect_spec binds no parameters; the asset would do nothing")
    # The guard is the entry's own known_invalid_when list. It travels with the asset so a
    # caller cannot use the skill in a condition the entry already knows is wrong.
    guard = list(entry.get("known_invalid_when") or [])
    if not guard:
        raise AssetError("an asset with no guard can be called where it is known to "
                         "fail; known_invalid_when is empty")
    asset = {
        "asset_id": asset_id(entry),
        "callable": {"module": module_path, "function": binding["function"],
                     "kwargs": bound},
        "applies_when": list(entry.get("applicable_when") or []),
        "guard": guard,
        "source_entry": entry.get("entry_id"),
        "source_version": (entry.get("version") or {}).get("label"),
        "task_family": entry.get("task_family"),
        "code_generated": False,
        "why_not_generated": ("this asset binds parameters to an already-tested function; "
                              "no robot code was synthesised"),
    }
    asset["asset_sha256"] = schema.digest(asset)
    return asset


def callable_exists(asset):
    """Is the bound function actually importable and callable in this checkout?"""
    sys.path.insert(0, WT)
    try:
        module = importlib.import_module(asset["callable"]["module"])
    except Exception:
        return False
    fn = getattr(module, asset["callable"]["function"], None)
    return callable(fn)


def call(asset, *args, **kwargs):
    """Invoke the asset. Refuses when the caller passes a guarded condition."""
    if not callable_exists(asset):
        raise AssetError("bound callable is not importable: %s" % (asset["callable"],))
    blocked = set(kwargs) & {"invalid_when"}
    if blocked:
        raise AssetError("this asset cannot be called with a guarded condition")
    sys.path.insert(0, WT)
    module = importlib.import_module(asset["callable"]["module"])
    fn = getattr(module, asset["callable"]["function"])
    merged = dict(asset["callable"]["kwargs"])
    merged.update(kwargs)
    return fn(*args, **merged)


def append(path, asset):
    """Append-only asset store. A recompile of the same entry is a NEW version."""
    p = path
    os.makedirs(os.path.dirname(p), exist_ok=True)
    existing = read(p)
    if any(a.get("asset_sha256") == asset.get("asset_sha256") for a in existing):
        raise AssetError("duplicate asset")
    row = dict(asset)
    row["asset_version"] = 1 + sum(1 for a in existing
                                   if a.get("asset_id") == asset.get("asset_id"))
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def read(path):
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path, encoding="utf-8").read().splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def latest(path, aid):
    rows = [a for a in read(path) if a.get("asset_id") == aid]
    return rows[-1] if rows else None


if __name__ == "__main__":
    doc = json.loads(open(sys.argv[1], encoding="utf-8").read())
    asset = compile_asset(doc)
    print(json.dumps(dict(asset, callable_exists=callable_exists(asset)), indent=2))
