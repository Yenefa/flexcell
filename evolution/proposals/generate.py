#!/usr/bin/env python3
"""Turn measured failures into a GATED PROPOSAL - the missing link in the loop.

THE AUDIT THAT MOTIVATED THIS FILE: evolution/validation/regress.py has a gate that
checks a proposal, but evolution/proposals/ was EMPTY. Nothing produced proposals, so the
gate could never accept one, so C could never change itself. That is why two independent
B/C experiments measured exactly zero effect: the experience channel had no path to
action. Learning that never reaches behaviour is not learning.

This module closes that link in the narrowest defensible way:
  * it consumes only MEASURED evidence (archived run logs, never a hypothesis);
  * it emits a proposal the existing gate can judge;
  * it NEVER touches source. Applying is a separate, human-approved step.

Safety rules enforced here, not delegated:
  * a proposal needs a failure class seen at least MIN_OCCURRENCES times;
  * it can never name a protected path;
  * it must state a falsifiable expected effect and a rollback.

ISSUE #236 - DO NOT RE-PROPOSE A RETIRED IDEA. docs/FACT_STATE_20261112.md records
that an earlier synthetic reproduction re-generated a superseded release-retry idea,
because nothing consulted the status that had already been written down. So before a
proposal is built, the existing status records are read and any retired proposal is
skipped with a traceable reason (`skipped=[{id, reason, source}]`).

WHERE THAT STATUS ALREADY LIVES (read in this order, nothing is written back):
  1. evolution/experience/records.jsonl + review_ledger.jsonl - the experience store.
     It carries LESSON-level status (validated flag, ACCEPT/REJECT review verdicts, an
     append-only hash chain). It cannot answer "is this PROPOSAL retired", and it is
     keyed by task/lesson, not by proposal signature, so this module reads it as
     context only and does not invent a mapping from a lesson verdict to a proposal.
  2. evolution/proposals/check_applied.py - it computes ALREADY_SATISFIED / WOULD_FIX
     by running current code, but it does not persist the verdict, so it is not a
     registry either.
  3. The persisted proposal status that DOES exist, per docs/AGENT_HANDOFF.md
     ("superseded pre-registrations must be kept and marked `superseded_basis`"):
       * a pre-registration document with `superseded_basis` invalidates the proposal
         it names (`proposal` or `proposal_id`, falling back to the file stem);
       * a document with `supersedes` marks the proposals it names as replaced by its
         own `proposal_id`.
  4. An optional read-only overlay, evolution/proposals/superseded.json, for status
     that has no other home. Format (schema_version 1):

         {
           "schema_version": 1,
           "records": [
             {"id": "<proposal signature or kind>",
              "status": "invalidated" | "superseded" | "rejected",
              "reason": "<why it may not be generated again>",
              "source": "<where that decision is recorded>",
              "superseded_by": "<optional: the replacement proposal id>"}
           ]
         }

     Every key except superseded_by is required. A record that does not declare a
     status is REFUSED rather than read as "valid": incomplete status data must never
     turn into an approval. A missing file is not approval either - it only means no
     retirement is recorded, and the proposal still carries
     requires_human_approval: true.

A retired proposal is never rewritten, and neither is any proposal file that already
exists: the file on disk is kept byte-for-byte, so the historical proposal and its
evidence stay intact. That is not cosmetic - docs/FACT_STATE_20261112.md records a
round where in-place proposal writing overwrote evolution/proposals/actuator_stall.json,
a proposal awaiting review ("run_loop.py writes proposals in place"). A generated
proposal is UNVERIFIED by construction: it carries requires_human_approval true and is
reported as unverified, never as verified or approved.
"""
import argparse
import glob
import json
import os
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WT / "evolution" / "validation"))
import regress

MIN_OCCURRENCES = 2

STATUS_SCHEMA_VERSION = 1
STATUS_FILE = "superseded.json"
# only these statuses mean "do not generate this again"; anything else is refused
STATUS_SKIP = ("invalidated", "superseded", "rejected")

CLASS_TARGETS = {
    # A release stall is a SKILL-LAYER defect with a computable signature: the
    # controller reports stalled=True on an OPEN command, place_server treats that as
    # fatal on first occurrence, and no retry exists anywhere in that file.
    "actuator_stall": ["src/flexcell/flexcell_skills/flexcell_skills/place_server.py"],
    "planning": ["experiments/baselines/spread_destinations.py"],
    "execution": ["runtime/recovery/recover.py"],
    "grasp": ["runtime/recovery/recover.py"],
}


def load_evidence(runs_root):
    """Read archived run directories. Evidence only - no verdict, no grader file."""
    out = []
    for d in sorted(glob.glob(os.path.join(runs_root, "*"))):
        if not os.path.isdir(d):
            continue
        t = os.path.join(d, "task.out")
        if not os.path.exists(t):
            continue
        txt = open(t, encoding="utf-8", errors="replace").read()
        if "RESULT " not in txt:
            continue
        try:
            res = json.loads(txt.split("RESULT ", 1)[1])
        except json.JSONDecodeError:
            continue
        if res.get("error_code") in (0, None):
            continue
        out.append({"run": os.path.basename(d),
                    "error_code": res.get("error_code"),
                    "detail": str(res.get("detail") or ""),
                    "completed_stage_ids": res.get("completed_stage_ids") or []})
    return out


def cluster(failures):
    """Group failures by an observable signature. No guessing at causes."""
    buckets = {}
    for f in failures:
        d = f["detail"].lower()
        if "gripper did not open" in d:
            key = "actuator_stall"
        elif "occupied destination" in d or "destination occupied" in d:
            key = "occupied_destination"
        elif "state drift" in d:
            key = "state_drift"
        elif "unconfirmed" in d:
            key = "unconfirmed"
        else:
            key = "error_%s" % f["error_code"]
        buckets.setdefault(key, []).append(f)
    return buckets


def build_proposal(signature, failures):
    """Emit a proposal the gate can judge. Refuses when evidence is too thin."""
    if len(failures) < MIN_OCCURRENCES:
        return None, "only %d occurrence(s) of %s; need %d" % (
            len(failures), signature, MIN_OCCURRENCES)
    if signature == "actuator_stall":
        files = CLASS_TARGETS["actuator_stall"]
        return {
            "kind": "bounded_release_retry",
            "signature": signature,
            "files": list(files),
            "occurrences": len(failures),
            "evidence": {"signature": signature,
                         "runs": [f["run"] for f in failures][:16],
                         "error_codes": sorted({f["error_code"] for f in failures}),
                         "sample_detail": failures[0]["detail"][:160]},
            "change": ("when the gripper reports stalled=True on the release command, "
                       "retry the open a bounded number of times before declaring "
                       "PLACE failed; the signal is observable and a re-issued open "
                       "is a new attempt, not a longer wait"),
            # CORRECTED after measuring the base rate: my first wording claimed phases
            # "will succeed", but the existing plan-level retry ALREADY recovers 6 of 9
            # stalls (67%). So the honest increment is NOT final pass rate - it is
            # first-attempt success and cost: today a stall costs a whole-stage re-run
            # (median 13.0 s, and re-picking the box), not a re-issued open.
            "expected_effect": ("first-attempt pass rate rises by at most the 4 runs the "
                                "plan-level retry currently rescues; FINAL pass rate is "
                                "expected to be UNCHANGED at 29/32, because the existing "
                                "retry already reaches those end states; and a stall "
                                "that persists (3 of 9) MUST still fail with the same "
                                "error, so the change cannot turn a real failure into "
                                "a pass"),
            "increment_is": "latency and risk, not final pass rate",
            "rollback": "git revert this commit; the single-attempt release returns",
            "requires_human_approval": True,
        }, None
    if signature not in ("occupied_destination",):
        return None, "no evidence-backed change for %s yet" % signature
    files = CLASS_TARGETS["planning"]
    proposal = {
        "kind": "spacing_policy",
        "signature": signature,
        "files": list(files),
        "occurrences": len(failures),
        "evidence": {"signature": signature,
                     "runs": [f["run"] for f in failures][:16],
                     "error_codes": sorted({f["error_code"] for f in failures}),
                     "sample_detail": failures[0]["detail"][:160]},
        "change": ("when several objects share a bin, the spacing between landing "
                   "points must exceed the clearance contract PLUS measured landing "
                   "drift, and the spread axis must keep every destination clear of "
                   "the other objects; refuse rather than emit an unholdable plan"),
        "expected_effect": ("phases that failed with an occupied destination will "
                            "either succeed or be refused at plan time; no verified "
                            "task may regress"),
        "rollback": "git revert this commit; the previous spread policy is unchanged",
        "requires_human_approval": True,
    }
    return proposal, None


# ------------------------------------------------- proposal status registry (#236)
def _source_of(path):
    """A path a reader can follow: repository-relative when possible."""
    try:
        return Path(path).resolve().relative_to(WT).as_posix()
    except ValueError:
        return Path(path).as_posix()


def _one_line(text, limit=180):
    """One sentence of prose, for a machine-readable skipped[...] entry."""
    text = " ".join(str(text or "").split())
    head = text.split(". ", 1)[0]
    if len(head) <= limit:
        return head
    return head[:limit - 3].rstrip() + "..."


def _proposal_id(doc, path):
    """The proposal a status document names.

    proposal_id and proposal are the keys the existing pre-registrations use; the
    file stem is the fallback (actuator_stall_preregistration.json ->
    actuator_stall), because a retired proposal must not be silently ignored just
    because a status document is written slightly differently.
    """
    ident = doc.get("proposal_id") or doc.get("proposal")
    if isinstance(ident, str) and ident.strip():
        return ident.strip()
    stem = path.stem
    for suffix in ("_preregistration", "_proposal", "_proposal_preregistration"):
        if stem.endswith(suffix):
            return stem[:-len(suffix)]
    return stem


def _ids_named(text):
    """Proposal ids named in a supersedes string: 'a / b (why ...)' -> [a, b]."""
    names = []
    for chunk in str(text).replace(",", "/").split("/"):
        name = chunk.split("(", 1)[0].strip()
        if name:
            names.append(name)
    return names


def _entry(ident, status, reason, source, superseded_by=None):
    entry = {"id": ident, "status": status, "reason": reason, "source": source}
    if superseded_by:
        entry["superseded_by"] = superseded_by
    return entry


def load_status_file(path):
    """Read the optional superseded.json overlay. Never writes it."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError("cannot read %s: %s" % (path, exc))
    except json.JSONDecodeError as exc:
        raise RuntimeError("%s is not valid JSON: %s" % (path, exc))
    if not isinstance(doc, dict) or doc.get("schema_version") != STATUS_SCHEMA_VERSION:
        raise RuntimeError("%s must be an object with schema_version %d"
                           % (path, STATUS_SCHEMA_VERSION))
    records = doc.get("records")
    if not isinstance(records, list):
        raise RuntimeError("%s must carry a records list" % path)
    entries = []
    for index, record in enumerate(records):
        where = "%s records[%d]" % (path, index)
        if not isinstance(record, dict):
            raise RuntimeError("%s must be an object" % where)
        ident = record.get("id")
        status = record.get("status")
        if not isinstance(ident, str) or not ident.strip():
            raise RuntimeError("%s needs a non-empty id" % where)
        if status not in STATUS_SKIP:
            # the whole point: a record without a recognised status is NOT a pass, it
            # is status data missing, and that must not become an approval
            raise RuntimeError("%s (%s) has status %r; expected one of %s"
                               % (where, ident, status, ", ".join(STATUS_SKIP)))
        reason = record.get("reason")
        source = record.get("source")
        if not str(reason or "").strip() or not str(source or "").strip():
            raise RuntimeError("%s (%s) needs both reason and source"
                               % (where, ident))
        entries.append(_entry(str(ident).strip(), status, str(reason).strip(),
                              str(source).strip(), record.get("superseded_by")))
    return entries


def load_status_registry(proposals_dir):
    """{proposal id: [status entry, ...]} from the persisted status records.

    Read-only. Recorded status is what decides a skip; absent status is NOT approval,
    it is "nothing recorded" and generation proceeds under human approval.
    """
    registry = {}
    directory = Path(proposals_dir)
    if not directory.is_dir():
        return registry
    for path in sorted(directory.glob("*.json")):
        if path.name == STATUS_FILE:
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # a proposal/gate file that is not JSON is not a status record; the
            # overlay is the one place where malformed status is an error
            continue
        if not isinstance(doc, dict):
            continue
        ident = _proposal_id(doc, path)
        basis = doc.get("superseded_basis")
        if isinstance(basis, dict) and basis:
            why = basis.get("why") or basis.get("what_changes") or "basis superseded"
            recorded = basis.get("recorded")
            reason = _one_line(why)
            if recorded:
                reason = "%s: %s" % (recorded, reason)
            registry.setdefault(ident, []).append(_entry(
                ident, "invalidated", reason,
                _source_of(path) + "#superseded_basis"))
        supersedes = doc.get("supersedes")
        if isinstance(supersedes, str) and supersedes.strip():
            replacement = doc.get("proposal_id") or ident
            why = doc.get("why_the_old_proposal_was_wrong") or supersedes
            for named in _ids_named(supersedes):
                registry.setdefault(named, []).append(_entry(
                    named, "superseded",
                    "superseded by %s: %s" % (replacement,
                                              _one_line(why)),
                    _source_of(path) + "#supersedes", replacement))
    overlay = directory / STATUS_FILE
    if overlay.is_file():
        for entry in load_status_file(overlay):
            registry.setdefault(entry["id"], []).append(entry)
    return registry


def status_of(registry, *identifiers):
    """Every recorded status entry for any of these proposal identifiers."""
    found = []
    for ident in identifiers:
        if not ident:
            continue
        for entry in registry.get(ident, []):
            if entry not in found:
                found.append(entry)
    return found


def skipped_entry(entries):
    """One {id, reason, source} entry for the machine-readable skip line."""
    return {"id": entries[0]["id"],
            "reason": "; ".join(entry["reason"] for entry in entries),
            "source": ",".join(entry["source"] for entry in entries)}


def generate(buckets, registry, out_dir):
    """Plan, gate and write proposals; return what happened.

    A proposal whose signature or kind is retired is skipped BEFORE it is built, so
    no file, no gate decision and no side effect is produced for it.
    """
    result = {"written": [], "kept": [], "skipped": [], "refused": []}
    for signature, failures in sorted(buckets.items(),
                                      key=lambda item: -len(item[1])):
        retired = status_of(registry, signature)
        if retired:
            result["skipped"].append(skipped_entry(retired))
            continue
        proposal, why = build_proposal(signature, failures)
        if proposal is None:
            result["refused"].append({"id": signature, "reason": why})
            print("  SKIP %-22s %s" % (signature, why))
            continue
        retired = status_of(registry, proposal.get("kind"))
        if retired:
            result["skipped"].append(skipped_entry(retired))
            continue
        out = Path(out_dir) / ("%s.json" % signature)
        if out.exists():
            # history is kept, never regenerated over: the existing file is the
            # proposal of record and its evidence must stay readable as written
            result["kept"].append(str(out))
            print("  KEPT %-22s exists; not regenerated (%s)" % (signature, out))
            continue
        ok, reason = regress.gate(proposal, run_regressions=False)
        print("  PROPOSAL %-20s occurrences=%d gate=%s approval=required" % (
            signature, len(failures), "ACCEPTED" if ok else "REJECTED"))
        print("    reason:", reason)
        if not ok:
            result["refused"].append({"id": signature, "reason": reason})
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(proposal, indent=2) + "\n", encoding="utf-8")
        result["written"].append(str(out))
        print("    wrote", out)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate gated proposals from measured failures.")
    parser.add_argument("runs_root", nargs="?", default="/tmp/evobot-pair16",
                        help="archived run directories (default: %(default)s)")
    parser.add_argument("--proposals-dir",
                        default=str(WT / "evolution" / "proposals"),
                        help="where the status registry is read from")
    parser.add_argument("--out-dir",
                        help="where new proposals are written "
                             "(default: the proposals dir)")
    args = parser.parse_args(argv)
    out_dir = Path(args.out_dir or args.proposals_dir)
    try:
        registry = load_status_registry(args.proposals_dir)
    except RuntimeError as exc:
        # a broken status registry must not degrade into "nothing is retired"
        print("ERROR: proposal status registry unreadable: %s" % exc,
              file=sys.stderr)
        return 2

    failures = load_evidence(args.runs_root)
    print("measured failures:", len(failures))
    buckets = cluster(failures)
    result = generate(buckets, registry, out_dir)
    print("skipped=%s" % json.dumps(result["skipped"], sort_keys=True))
    print("written=%s" % json.dumps(result["written"], sort_keys=True))
    # nothing here is verified or approved: a proposal only becomes evidence-backed
    # after a measurement the gate can re-run, and applying is a human decision
    print("unverified=%d kept=%d refused=%d" % (
        len(result["written"]), len(result["kept"]), len(result["refused"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
