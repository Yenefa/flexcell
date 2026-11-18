#!/usr/bin/env python3
"""Resolve a live consumer's parameters from a REVIEWED experience asset, fail-closed.

THE GAP THIS EXISTS FOR
    The live executor consumer exists: setup/acceptance/evobot_unified_runner_20261111/
    run_batch.sh:107 calls runtime/recovery/recovery_driver.py, whose line 146 calls
    recover.apply_respread(plan, avoid=avoid) with the FUNCTION'S DEFAULT kwargs. It performs
    no experience lookup. The compiled E2 asset carries exactly those defaults today, so
    behaviour matches — but a REVISED entry can never reach the robot: the call site reads
    the function signature, not the entry.

WHAT IT PROVIDES
    resolve(asset_path, consumer, entry_store, ledger) -> (kwargs, why)
        kwargs is {} on ANY gate failure (caller uses its defaults). No exception escapes.
        The four gates are the SAME ones retrieval uses, in the same order:

            1  chain intact       store.verify_chain(entry_store)
            2  entry ACTIVE       the version named by the asset is ACTIVE on its lineage
            3  reviewed ACCEPT    there is no live external reviewer here, so a REJECT or
                                  absence of ACCEPT REFUSES the parameter
            4  callable matches   asset.callable names this consumer's function and kwargs
                                  are numeric and finite

    A refusal is NOT an error: the robot keeps using the defaults it always used. That is
    what makes this safe to add to a live path. It is opt-in — the driver calls resolve()
    only when an asset path is supplied, so the frozen baseline default is byte-identical.

WHY NOT JUST READ THE ASSET
    A compiled asset is a derivative. Reading it without re-checking the entry's status would
    let a RETIRED or REVISED asset drive the robot. Every gate here is re-derived from the
    store at call time, not trusted from the asset's cached fields.
"""
import json
import math
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import skill_asset  # noqa: E402
import store  # noqa: E402

CONSUMER_FUNCTIONS = {
    "executor_recovery": "apply_respread",
    "harness": "deliver_config",
    "planner": "validate_plan",
    "spread_policy": "spread",
}


def resolve(asset_path, consumer, entry_store, ledger_path=None, asset_version=None):
    """Return (kwargs, why). kwargs == {} means REFUSED — caller must use its defaults.

    Never raises. A live path cannot take down a robot run because an experience lookup
    failed; a refusal simply means "no reviewed update reached here".
    """
    if not asset_path or not os.path.exists(asset_path):
        return {}, "no asset path supplied; using the call site's defaults"

    # gate 1: the entry chain must be intact
    try:
        intact, detail = store.verify_chain(entry_store)
    except Exception as exc:  # noqa: BLE001 - a broken chain is a refusal, not a crash
        return {}, "entry chain unreadable: %s" % exc
    if not intact:
        return {}, "entry chain does not verify"

    # load assets and bind to the requested consumer
    try:
        assets = skill_asset.read(asset_path)
    except Exception as exc:  # noqa: BLE001
        return {}, "assets unreadable: %s" % exc
    rows = store.read(entry_store)
    by_id = {r.get("entry_id"): r for r in rows}
    by_label = {(r.get("version") or {}).get("label"): r for r in rows}

    for asset in assets:
        source = asset.get("source_entry")
        entry = by_id.get(source)
        if entry is None:
            continue
        if asset_version and asset.get("source_version") != asset_version:
            continue
        # gate 2: ACTIVE on the lineage, and this is the LATEST version of that lineage
        if (entry.get("version") or {}).get("status") != "ACTIVE":
            continue
        lineage = [r for r in rows
                   if (r.get("version") or {}).get("label")
                   == (entry.get("version") or {}).get("label")]
        # "latest" is by STORE ORDER (append-only hash chain), not by a version number:
        # these records carry no numeric version field, and sorting by a missing key just
        # returns the first one - which would make the newest compiled asset look stale and
        # refuse everything. The last row of a lineage is the current one.
        if lineage and lineage[-1].get("entry_id") != entry.get("entry_id"):
            continue

        # gate 3: explicit ACCEPT, never a missing or REJECT verdict
        validation = entry.get("validation") or {}
        if validation.get("review_verdict") != "ACCEPT":
            continue
        if validation.get("reviewed_by") in (None, "", "chain-demo-reviewer"):
            # a self-review is not the independent acceptance a live change needs
            continue

        # gate 4: the callable and kwargs are what this consumer expects
        try:
            binding = skill_asset.binding_for(entry)
        except Exception:  # noqa: BLE001
            continue
        # binding_for returns the flat {module, function, kwargs} shape; the consumer is
        # carried by the ENTRY, not the binding. Reading a "callable" key here would
        # silently refuse every asset, which is fail-safe but also fails to close the gap.
        if not isinstance(binding, dict) or entry.get("consumer") != consumer:
            continue
        expected = CONSUMER_FUNCTIONS.get(consumer)
        if expected and binding.get("function") != expected:
            continue
        kwargs = binding.get("kwargs") or {}
        if not isinstance(kwargs, dict):
            continue
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                   and math.isfinite(v) for v in kwargs.values()):
            continue
        return dict(kwargs), ("accepted entry %s (%s) for %s"
                              % ((entry.get("version") or {}).get("label"),
                                 source[:12], consumer))

    return {}, ("no asset passed every gate (chain, ACTIVE+latest, independent ACCEPT, "
                "callable); using the call site's defaults")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", required=True)
    ap.add_argument("--consumer", required=True)
    ap.add_argument("--entries", required=True)
    args = ap.parse_args()
    kwargs, why = resolve(args.asset, args.consumer, args.entries)
    print(json.dumps({"kwargs": kwargs, "why": why}, indent=2))
