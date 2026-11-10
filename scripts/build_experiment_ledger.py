#!/usr/bin/env python3
"""Build a durable experiment ledger from docs/EXPERIMENTS.md.

Every field is EXTRACTED, never hand-written. The index table supplies id, title,
outcome and evidence link; entry bodies supply purpose / scenario / setup /
result / evidence / stated limits, using whatever bold field names the original
entry uses. A record present in the index but with no body is reported as a gap.

Usage: python3 scripts/build_experiment_ledger.py SRC_MD OUT_DIR
"""
import json
import re
import sys
from pathlib import Path

INDEX_ROW = re.compile(r"^\|\s*(E-\d+)\s*\|(.+?)\|(.+?)\|(.+?)\|\s*$", re.M)
ENTRY_HEAD = re.compile("^###\\s+(E-\\d+)\\s+[-\u2014]\\s+(.+)$", re.M)
FIELD = re.compile(r"^-\s+\*\*(.+?)\*\*:\s*(.+?)(?=\n-\s+\*\*|\Z)", re.M | re.S)
FENCE = chr(96) * 3

ROLES = {
    "purpose": "purpose", "what it was": "purpose",
    "scenario": "scenario",
    "configuration": "configuration", "setup": "configuration",
    "result": "acceptance", "validation": "acceptance", "outcome": "acceptance",
    "fix": "change", "change": "change",
    "evidence": "evidence_text",
    "limits": "limits_text", "open": "limits_text", "budget/limits": "limits_text",
    "next": "next_text", "note": "note_text",
}

CAUTION = {
    "SUPERSEDED": "superseded by a later experiment; not citable",
    "NOT CITABLE": "not citable",
    "NOT CITED": "not citable",
    "FROZEN": "sample-size threshold unmet; frozen",
    "n>=50": "sample-size threshold unmet; frozen",
    "NOT RUN": "not run",
    "PARTIAL": "partial only",
    "HARNESS_ERROR": "includes a harness error",
    "BLOCKED": "blocked",
    "MECHANISM": "mechanism evidence, not a baseline",
    "NOT BENCHMARK": "not a benchmark result",
    "TRUNCATED": "batch truncated",
    "DEGRADED": "downgraded",
}

def parse_table(text):
    rows = {}
    for m in INDEX_ROW.finditer(text):
        eid, title, outcome, evidence = (m.group(i).strip() for i in (1, 2, 3, 4))
        link = re.search(r"\[([^\]]+)\]\(([^)]+)\)", evidence)
        rows[eid] = {
            "id": eid,
            "title": title,
            "outcome": outcome,
            "evidence_link": link.group(2) if link else None,
            "evidence_label": link.group(1) if link else (evidence or None),
        }
    return rows


def parse_entries(text):
    heads = list(ENTRY_HEAD.finditer(text))
    out = {}
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = text[h.end():end]
        raw = {}
        for m in FIELD.finditer(body):
            raw[m.group(1).strip().lower()] = " ".join(m.group(2).split())
        out[h.group(1)] = {"heading_title": h.group(2).strip(), "fields": raw}
    return out


def slot(ent, name):
    for field, mapped in ROLES.items():
        if mapped == name and ent["fields"].get(field):
            return ent["fields"][field]
    return None


def all_limits(ent):
    """Only fields whose NAME says they are limits; nothing inferred."""
    return [{"field": f, "text": v} for f, v in ent["fields"].items()
            if ROLES.get(f) in ("limits_text", "next_text")]


def cautions(outcome):
    up = (outcome or "").upper()
    return [{"token": t, "meaning": v} for t, v in CAUTION.items() if t.upper() in up]

def main():
    src, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    text = src.read_text(encoding="utf-8")
    table, entries = parse_table(text), parse_entries(text)

    records = []
    for eid in sorted(set(table) | set(entries)):
        row = table.get(eid, {})
        ent = entries.get(eid, {})
        outcome = row.get("outcome") or ""
        rec = {
            "id": eid,
            "title": row.get("title") or ent.get("heading_title"),
            "outcome": outcome or None,
            "has_entry_body": bool(ent),
            "acceptance": slot(ent, "acceptance") if ent else None,
            "purpose": slot(ent, "purpose") if ent else None,
            "scenario": slot(ent, "scenario") if ent else None,
            "configuration": slot(ent, "configuration") if ent else None,
            "change": slot(ent, "change") if ent else None,
            "stated_limits": all_limits(ent) if ent else [],
            "fields_present": list(ent["fields"]) if ent else [],
            "evidence": {
                "link": row.get("evidence_link"),
                "label": row.get("evidence_label"),
                "entry_text": slot(ent, "evidence_text") if ent else None,
            },
            "known_limitations": cautions(outcome),
        }
        if not rec["has_entry_body"]:
            rec["gaps"] = ["index row without an entry body"]
        records.append(rec)

    no_body = [r["id"] for r in records if not r["has_entry_body"]]
    caution_ids = {r["id"]: [c["token"] for c in r["known_limitations"]]
                   for r in records if r["known_limitations"]}
    no_acc = [r["id"] for r in records if not r["acceptance"]]
    no_ev = [r["id"] for r in records
             if not (r["evidence"].get("link") or r["evidence"].get("entry_text"))]

    doc = {
        "schema": "flexcell.experiment_ledger/1",
        "source": str(src),
        "source_note": "extracted from docs/EXPERIMENTS.md; no field is hand-written",
        "counts": {"records": len(records), "no_entry_body": len(no_body),
                   "with_caution": len(caution_ids)},
        "integrity": {
            "ids_in_index_without_body": no_body,
            "ids_with_outcome_caution": caution_ids,
            "ids_without_acceptance": no_acc,
            "ids_without_evidence": no_ev,
        },
        "records": records,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "experiment_ledger.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    L = []
    L.append("# Experiment ledger (extracted from docs/EXPERIMENTS.md)")
    L.append("")
    L.append("> Generated by scripts/build_experiment_ledger.py. Every field is")
    L.append("> extracted from the source; nothing is written by hand. Verify")
    L.append("> against docs/EXPERIMENTS.md on origin/main (ebe27f0).")
    L.append("")
    L.append("## Overview")
    L.append("")
    L.append("| item | value |")
    L.append("| --- | --- |")
    L.append("| records | %d |" % len(records))
    L.append("| in index but no entry body | %d (%s) |"
             % (len(no_body), ", ".join(no_body) or "none"))
    L.append("| outcome carries a caveat | %d |" % len(caution_ids))
    L.append("| entry states an explicit limit | %d |"
             % sum(1 for r in records if r["stated_limits"]))
    L.append("")
    L.append("## Index")
    L.append("")
    L.append("| ID | experiment | outcome (verbatim) | body |")
    L.append("| --- | --- | --- | --- |")
    for r in records:
        L.append("| %s | %s | %s | %s |" % (
            r["id"], (r["title"] or "")[:62], (r["outcome"] or "")[:56],
            "yes" if r["has_entry_body"] else "**MISSING**"))
    L.append("")
    L.append("## Acceptance criteria (verbatim from each entry)")
    L.append("")
    for r in records:
        if r["acceptance"]:
            L.append("### %s - %s" % (r["id"], r["title"] or ""))
            L.append("")
            L.append(FENCE)
            L.append(r["acceptance"][:900])
            L.append(FENCE)
            L.append("")
    L.append("## Known limitations")
    L.append("")
    L.append("### From the outcome column")
    L.append("")
    for eid in sorted(caution_ids):
        items = ["%s -> %s" % (t, CAUTION[t]) for t in caution_ids[eid] if t in CAUTION]
        L.append("- **%s**: %s" % (eid, "; ".join(items)))
    L.append("")
    L.append("### Stated in the entry body")
    L.append("")
    wrote = False
    for r in records:
        for lim in r["stated_limits"]:
            wrote = True
            L.append("- **%s** (%s): %s" % (r["id"], lim["field"], lim["text"][:300]))
    if not wrote:
        L.append("(none recorded)")
    L.append("")
    L.append("## Raw evidence pointers")
    L.append("")
    for r in records:
        bits = [x for x in (r["evidence"].get("link"),
                            r["evidence"].get("entry_text")) if x]
        if bits:
            L.append("- **%s**: %s" % (r["id"], " | ".join(b[:220] for b in bits)))
    L.append("")
    L.append("## Data gaps")
    L.append("")
    L.append("Properties of the source, not of the extractor:")
    L.append("")
    L.append("- no acceptance/result field: %s" % (", ".join(no_acc) or "none"))
    L.append("- no evidence pointer: %s" % (", ".join(no_ev) or "none"))
    L.append("- index row without body: %s" % (", ".join(no_body) or "none"))
    (out_dir / "EXPERIMENT_LEDGER.md").write_text("\n".join(L) + "\n",
                                                  encoding="utf-8")
    print(json.dumps(doc["counts"], ensure_ascii=False))
    print("no_acceptance:", len(no_acc), "no_evidence:", len(no_ev))
    return 0


if __name__ == "__main__":
    sys.exit(main())
