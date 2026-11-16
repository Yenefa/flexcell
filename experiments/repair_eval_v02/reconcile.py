"""Reconcile the hand-written RUN_MANIFEST slot table against actual records.

WHY THIS EXISTS
    RUN_MANIFEST section 1 is a hand-written table whose own header says the
    status column is the authoritative count. Nothing checked it against reality.
    The existing doc self-check asserts all 24 rows are NOT_RUN, which only
    proves the package has not been executed - it cannot notice a table that
    disagrees with the records sitting next to it.

    Two failures matter, and they pull in opposite directions:

      - a slot marked terminal with no record behind it (a claim with nothing
        under it);
      - a record that is terminal while the table still says NOT_RUN (work done
        and then not counted).

    The third one is specific to this repository and the most dangerous: a
    dry-run record quietly promoting a slot. The matrix drivers produce real
    looking records marked DRY_RUN, and if anyone ever concatenates them into
    the manifest the trail from "we never ran this" to "we ran this" becomes
    invisible. Those records are reported and excluded, never counted.
"""
import json
import re

NOT_RUN = "NOT_RUN"
TERMINAL = ("SUCCESS_VERIFIED", "FAIL", "BUDGET_EXHAUSTED", "UNKNOWN", "INVALID")
KNOWN_STATUSES = (NOT_RUN, "RUNNING") + TERMINAL

# A record whose qualification contains any of these is not a real run.
NOT_REAL = ("DRY_RUN", "SCRIPTED")

SLOT_RE = re.compile(r"^\|\s*\d+\s*\|\s*`([^`]+)`\s*\|")


class ReconcileError(Exception):
    """Raised when the manifest and the records disagree."""


def parse_manifest(path):
    """Return slot_id -> status from the manifest table."""
    text = open(path, encoding="utf-8").read()
    statuses = {}
    for line in text.splitlines():
        stripped = line.strip()
        match = SLOT_RE.match(stripped)
        if not match:
            continue
        cells = [c.strip().strip("`") for c in stripped.strip("|").split("|")]
        slot_id = match.group(1)
        status = cells[-1].strip()
        if status not in KNOWN_STATUSES:
            raise ReconcileError(
                "slot %s declares status %r, which is not in the vocabulary"
                % (slot_id, status))
        if slot_id in statuses:
            raise ReconcileError("slot %s appears more than once" % (slot_id,))
        statuses[slot_id] = status
    return statuses


def is_real(record):
    qualification = str(record.get("qualification") or "").upper()
    return not any(marker in qualification for marker in NOT_REAL)


def reconcile(manifest_statuses, records):
    """Compare the table to the records. Returns a report, raises on drift."""
    report = {
        "manifest_slots": len(manifest_statuses),
        "records": len(records),
        "excluded_not_real": [],
        "drift": [],
    }
    seen = {}
    for record in records:
        slot_id = record.get("slot_id")
        if slot_id not in manifest_statuses:
            raise ReconcileError(
                "record for slot %r, which the manifest does not list" % (slot_id,))
        if not is_real(record):
            # kept visible but never counted: a dry run must not move a slot
            report["excluded_not_real"].append(slot_id)
            continue
        if slot_id in seen:
            raise ReconcileError(
                "two real records for slot %s; a re-run is a new row, not a "
                "second record on the same row" % (slot_id,))
        seen[slot_id] = record

    for slot_id in sorted(seen):
        record = seen[slot_id]
        declared = manifest_statuses[slot_id]
        actual = record.get("terminal_status")
        if actual not in KNOWN_STATUSES:
            raise ReconcileError(
                "record %s has terminal_status %r, outside the vocabulary"
                % (slot_id, actual))
        if declared == NOT_RUN and actual not in (NOT_RUN, "RUNNING"):
            report["drift"].append(
                "slot %s: manifest says NOT_RUN, a real record says %s"
                % (slot_id, actual))
        elif declared != actual:
            report["drift"].append(
                "slot %s: manifest says %s, record says %s"
                % (slot_id, declared, actual))

    for slot_id in sorted(manifest_statuses):
        declared = manifest_statuses[slot_id]
        if declared in TERMINAL and slot_id not in seen:
            report["drift"].append(
                "slot %s: manifest says %s but no real record backs it"
                % (slot_id, declared))

    report["consistent"] = not report["drift"]
    return report


def assert_reconciled(manifest_statuses, records):
    report = reconcile(manifest_statuses, records)
    if not report["consistent"]:
        raise ReconcileError("; ".join(report["drift"]))
    return report


def load_records(path):
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        payload = payload.get("rows") or payload.get("records") or []
    if not isinstance(payload, list):
        raise ReconcileError("records file must hold a list or {rows: [...]}")
    return payload


def main(argv=None):
    """Check a records file against the manifest. Exit code is the verdict."""
    import argparse
    import os

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True,
                        help="path to RUN_MANIFEST.md")
    parser.add_argument("--records", default=None,
                        help="records JSON (a list, or {rows: [...]})")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    statuses = parse_manifest(args.manifest)
    records = load_records(args.records) if args.records else []
    report = reconcile(statuses, records)
    report["manifest"] = os.path.relpath(args.manifest) if hasattr(os, "relpath") else args.manifest
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print("manifest slots   : %d" % report["manifest_slots"])
        print("records read     : %d" % report["records"])
        print("excluded non-real: %d" % len(report["excluded_not_real"]))
        if report["drift"]:
            print("DRIFT:")
            for line in report["drift"]:
                print("  - " + line)
        print("verdict          : %s" % ("CONSISTENT" if report["consistent"] else "DRIFT"))
    return 0 if report["consistent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
