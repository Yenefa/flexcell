
"""Recompute the archived W5 numbers from the per-run records (#254 groundwork).

The paper's v0.1 tables quote 6/6, 3/3, 0/3, 0/2 and a token/iteration profile.
Those figures come from aggregate.json files written by the same loop that
produced the runs, so quoting them is quoting the harness. This script
recomputes each figure from the individual run records and reports disagreement
instead of resolving it silently.

WHAT IT DOES NOT DO
    It does not decide whether a run "really" passed. It reads the recorded
    fields and compares them with the recorded summary. A disagreement means the
    summary is not reproducible from the records, not that either side is wrong.

THE ARCHIVE IS NOT UNIFORMLY SHAPED
    Two of the six experiments do not lay their runs out as <rep>/result.json:
    the first pilot keeps one directory per arm (w5a, w5b) and the E2 experiment
    keeps the first pilot's files at the top level beside pilot2/ and pilot3/.
    Any recomputation has to declare its own mapping, so LAYOUTS does that here
    and the mapping is printed in the output. A tool that silently found two
    records where the material claims three would be worse than no tool.
"""
import argparse
import json
import sys
from pathlib import Path

# experiment -> (label, declared n in the v0.1 material, layout)
LAYOUTS = {
    # Two arms (W5A without diagnosis, W5B with the verdict), one run each.
    # The material quotes them per arm as n=1, so there are 2 records here.
    "p1.5-w5-20261109": ("W5-E1 (first pilot; 2 arms x 1 run)", 2, "arm_dirs"),
    "p1.5-w5e2-20261109": ("W5-E2 (3-round budget, BLOCKED)", 3, "flat_first_then_dirs"),
    "p1.5-w5e2b-20261109": ("W5-E2b (6 rounds + read-only gate)", 3, "rep_dirs"),
    "p1.5-w5e2c-20261109": ("W5-E2c (multi-scenario regression gate)", 2, "rep_dirs"),
    "p1.5-w5e2d-20261109": ("W5-E2d (explicit action instruction)", 6, "rep_dirs"),
    "p1.5-w5e2e-20261109": ("W5-E2e (flash model)", 3, "rep_dirs"),
}


def _load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _record(name, payload):
    if not isinstance(payload, dict):
        return dict(record=name, usable=False, reason="unreadable or not an object")
    cost = payload.get("cost") or {}
    meta = payload.get("meta") or {}
    return dict(
        record=name,
        usable=True,
        success=payload.get("success") is True,
        first_pass=payload.get("first_pass"),
        iterations=payload.get("iterations"),
        tokens=cost.get("tokens"),
        claim_success=payload.get("claim_success"),
        false_success=payload.get("false_success"),
        model=meta.get("model"),
        task=meta.get("task"),
    )


def collect(exp_dir, layout):
    """Return (records, note) for one experiment, honouring its actual layout."""
    records = []
    if layout == "rep_dirs":
        for child in sorted(exp_dir.iterdir()):
            result = child / "result.json"
            if child.is_dir() and result.is_file():
                records.append(_record(child.name, _load(result)))
        return records, "<rep>/result.json"

    if layout == "arm_dirs":
        # One directory per arm; the summary carries the per-arm rows instead.
        aggregate = _load(exp_dir / "aggregate.json") or {}
        rows = aggregate.get("rows") or []
        for row in rows:
            records.append(dict(
                record=str(row.get("arm")), usable=True,
                success=row.get("success") is True,
                first_pass=None, iterations=row.get("iters"),
                tokens=row.get("tokens"), claim_success=None,
                false_success=None, model=aggregate.get("model"),
                task=aggregate.get("task"),
                source="aggregate.rows (no per-run result.json in this layout)"))
        return records, "aggregate.rows[arm]"

    if layout == "flat_first_then_dirs":
        # The first pilot's files sit at the top level; the rest are subdirs.
        flat = exp_dir / "pilot1-result.json"
        if flat.is_file():
            records.append(_record("pilot1", _load(flat)))
        for child in sorted(exp_dir.iterdir()):
            result = child / "result.json"
            if child.is_dir() and result.is_file():
                records.append(_record(child.name, _load(result)))
        return records, "pilot1-result.json + <pilotN>/result.json"

    raise ValueError("unknown layout: " + layout)


def recompute(exp_dir, layout, declared_n, label):
    records, note = collect(exp_dir, layout)
    aggregate = _load(exp_dir / "aggregate.json") or {}
    usable = [row for row in records if row["usable"]]
    computed = dict(
        n=len(usable),
        success=sum(1 for row in usable if row["success"]),
        iters=[row["iterations"] for row in usable],
        tokens=[row["tokens"] for row in usable],
    )
    disagreements = []
    if declared_n is not None and computed["n"] != declared_n:
        disagreements.append("n: material says %d, records give %d" % (declared_n, computed["n"]))
    for key in ("n", "success"):
        if aggregate.get(key) is not None and aggregate[key] != computed[key]:
            disagreements.append("%s: aggregate says %r, records give %r"
                                 % (key, aggregate[key], computed[key]))
    return dict(
        experiment=exp_dir.name, label=label, layout=layout, mapping=note,
        declared_n=declared_n, aggregate=dict(n=aggregate.get("n"), success=aggregate.get("success")),
        computed=computed, disagreements=disagreements,
        claim_success_true=sum(1 for row in usable if row.get("claim_success") is True),
        false_success_true=sum(1 for row in usable if row.get("false_success") is True),
        models=sorted({row["model"] for row in usable if row.get("model")}),
        records=records,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=Path, required=True,
                        help="experiments/pilot-001/runs in the checkout")
    parser.add_argument("--out", type=Path, help="optional JSON output path")
    args = parser.parse_args(argv)

    results, problems = [], []
    for name, (label, declared_n, layout) in LAYOUTS.items():
        directory = args.runs / name
        if not directory.is_dir():
            problems.append("%s: directory missing" % name)
            continue
        results.append(recompute(directory, layout, declared_n, label))

    summary = dict(
        experiments=len(results),
        records=sum(item["computed"]["n"] for item in results),
        successes=sum(item["computed"]["success"] for item in results),
        disagreements=sum(len(item["disagreements"]) for item in results),
        claim_success_true=sum(item["claim_success_true"] for item in results),
        false_success_true=sum(item["false_success_true"] for item in results),
        models=sorted({model for item in results for model in item["models"]}),
        problems=problems,
    )
    payload = dict(
        qualification="ARCHIVE_RECOMPUTATION_NOT_A_NEW_EXPERIMENT",
        note="Recomputed from the recorded runs. The aggregate files remain the quoted source; "
             "a disagreement means the summary is not reproducible, not that a run was misgraded.",
        summary=summary, experiments=results)
    text = json.dumps(payload, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(json.dumps(summary, indent=2))
    for item in results:
        for line in item["disagreements"]:
            print("DISAGREEMENT %s: %s" % (item["experiment"], line), file=sys.stderr)
    return 0 if not summary["problems"] and not summary["disagreements"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
