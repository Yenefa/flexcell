#!/usr/bin/env python3
"""Apply a stored skill to EVERY archived task and report what it does there.

THE QUESTION THIS ANSWERS
    The objective's claim is that experience accumulated on one task is REUSED on later
    tasks. Until now this package could show that a lesson acts on the single plan it was
    learned from - which is a demonstration, not a reuse. "It works on the input it was
    derived from" is the weakest possible claim and it is also the one a demo naturally
    produces.

    So this module takes a compiled skill asset and runs it over the whole archive,
    including every task the lesson never saw, and reports four numbers per task family:
    newly fixed, untouched, made worse, refused.

WHY "NO CHANGE" IS THE INTERESTING NUMBER TOO
    An asset that touches a conforming plan is a defect, not a bonus - that is how the
    2026-11-18 rotation bug was found. So "untouched" is reported as a pass condition, not
    as a miss. A reuse audit that only counted fixes would reward an asset for thrashing.

WHAT IT REFUSES TO CLAIM
    Every instance here is held-out (the archive only contains HO- runs), so this is
    cross-FAMILY reuse and NOT cross-split transfer. Those are different claims and the
    report says which one it supports. Conflating them is how "it generalizes" gets said
    without anything having been shown.
"""
import collections
import glob
import json
import math
import os
import re
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))
sys.path.insert(0, os.path.join(WT, "runtime", "recovery"))

import skill_asset  # noqa: E402

SPREAD_CONTRACT_M = 0.090
_TEMPLATE = re.compile(r'"template_id"\s*:\s*"([^"]+)"')


def _pts(stages):
    return [(float(s["place_pose"][0]), float(s["place_pose"][1])) for s in stages]


def _min_sep(stages):
    p = _pts(stages)
    if len(p) < 2:
        return None
    return min(math.hypot(a[0] - b[0], a[1] - b[1])
               for i, a in enumerate(p) for b in p[i + 1:])


# task_id -> template. Resolving an id means scanning the archive, and audit() asks once
# per plan file; uncached that is O(plans x archive) and the test suite went past its
# deadline. The cache is keyed by (root, task_id) so two archives cannot collide.
_TEMPLATE_CACHE = {}


def _index_templates(root):
    """One pass over the archive: task_id -> template_id, from any file naming the id."""
    key = ("index", root)
    if key in _TEMPLATE_CACHE:
        return _TEMPLATE_CACHE[key]
    index = {}
    # Narrow the scan: template_id lives in verdict/spec-shaped files, and the archive has
    # ~4500 json files where ~400 carry it. Scanning all of them took 33 s for one audit,
    # which is long enough that nobody would run it.
    pats = ("**/verdict*.json", "**/spec.json", "**/results.json",
            "**/offline_verification.json")
    paths = []
    for pat in pats:
        paths.extend(glob.glob(os.path.join(root, pat), recursive=True))
    for path in paths:
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        m = _TEMPLATE.search(text)
        if not m:
            continue
        template = m.group(1)
        base = os.path.basename(path)
        for token in re.findall(r"\bHO-[0-9a-f]{12}\b|\bT\d\d-[a-z]+-seed\d+\b", base):
            index.setdefault(token, template)
        # a file may also name its task inside, e.g. {"task_id": "HO-..."}
        for token in re.findall(r'"task_id"\s*:\s*"([^"]+)"', text):
            index.setdefault(token, template)
    if not index:
        # No template metadata anywhere: fall back to the path-substring scan below.
        return None
    _TEMPLATE_CACHE[key] = index
    return index


def template_of(task_id, acceptance=None):
    """Which task TEMPLATE an instance belongs to, read from the archive.

    Returns UNKNOWN rather than guessing from the id: an id that cannot be resolved must
    not be silently filed under a family, because the whole point of the family breakdown
    is to say which families the lesson transferred to.
    """
    root = acceptance or os.path.join(WT, "setup", "acceptance")
    index = _index_templates(root)
    if index and task_id in index:
        return index[task_id]
    if index is not None:
        return "UNKNOWN"
    # fallback: the archive has no template metadata, scan paths for the id
    for path in glob.glob(os.path.join(root, "**", "*.json"), recursive=True):
        if task_id not in path:
            continue
        try:
            m = _TEMPLATE.search(open(path, encoding="utf-8", errors="replace").read())
        except OSError:
            continue
        if m:
            return m.group(1)
    return "UNKNOWN"


def _stages(doc):
    return [s for s in (doc.get("stages") or [])
            if isinstance(s, dict) and isinstance(s.get("place_pose"), (list, tuple))]


def audit(asset, acceptance=None, source_task=None):
    """Run one asset over every archived multi-stage plan. Returns a report dict."""
    root = acceptance or os.path.join(WT, "setup", "acceptance")
    per_family = collections.defaultdict(lambda: {"fixed": 0, "untouched": 0,
                                                  "worse": 0, "refused": 0,
                                                  "instances": set()})
    seen = set()
    for path in glob.glob(os.path.join(root, "**", "plan*.json"), recursive=True):
        try:
            doc = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(doc, dict):
            continue
        stages = _stages(doc)
        if len(stages) < 2:
            continue
        before = _min_sep(stages)
        task_id = str(doc.get("task_id") or "?")
        family = template_of(task_id, acceptance)
        # Count each TASK INSTANCE once. The same instance appears in several batches, and
        # counting plan files would let one instance inflate the transfer result fourfold.
        key = (family, task_id)
        try:
            out = skill_asset.call(asset, doc)
        except Exception:  # noqa: BLE001 - a refusal is data, not a crash
            per_family[family]["refused"] += 1
            continue
        after_stages = out["stages"] if isinstance(out, dict) else out
        after = _min_sep(after_stages)
        if _pts(after_stages) == _pts(stages):
            per_family[family]["untouched"] += 1
            continue
        if after is not None and before is not None and after < before - 1e-9:
            per_family[family]["worse"] += 1
            continue
        if after is not None and after >= SPREAD_CONTRACT_M - 1e-9:
            if key not in seen:
                seen.add(key)
                per_family[family]["fixed"] += 1
                per_family[family]["instances"].add(task_id)
    families = {}
    for family, row in per_family.items():
        families[family] = {"newly_fixed_instances": row["fixed"],
                            "untouched_plans": row["untouched"],
                            "made_worse": row["worse"],
                            "refused": row["refused"],
                            "instances": sorted(row["instances"])}
    source_family = template_of(source_task, acceptance) if source_task else None
    transferred = sorted(f for f, r in families.items()
                         if r["newly_fixed_instances"] and f != source_family)
    return {
        "asset_id": asset.get("asset_id"),
        "source_task": source_task,
        "source_family": source_family,
        "families": families,
        "families_with_fixes": sorted(f for f, r in families.items()
                                      if r["newly_fixed_instances"]),
        "families_fixed_beyond_the_source": transferred,
        "total_instances_fixed": sum(r["newly_fixed_instances"]
                                     for r in families.values()),
        "total_made_worse": sum(r["made_worse"] for r in families.values()),
        "claim": ("cross-FAMILY reuse only; every instance in this archive is held-out, "
                  "so this is NOT cross-split transfer"),
    }


def reuse_assets(assets_path, source_task=None, acceptance=None):
    """Audit every compiled asset in a skill_assets.jsonl."""
    assets = skill_asset.read(assets_path)
    return [audit(a, acceptance=acceptance, source_task=source_task) for a in assets]


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        WT, "setup", "acceptance", "evobot_continual_chain_20261118", "skill_assets.jsonl")
    print(json.dumps(reuse_assets(path, source_task="HO-90899d657e68"), indent=2))
