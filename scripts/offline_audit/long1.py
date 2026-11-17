#!/usr/bin/env python3
"""LONG_1 native ContactPush archive adapter (issue #246, second PR).

This module only MAPS fields that already exist in a native archive into
``normalized/``. It never computes a stage, a contact, a displacement or a task
verdict. Every mapped value carries its source path; absent fields stay
UNKNOWN and are listed as issues.

Association uses native IDs found in composite events (``component_goal_uuid``
and ``component_run_id``) and in ``action_result.json`` (``goal_uuid`` and
``request_id``). Directory-name order is never used as evidence.
"""
import hashlib
import json
import zipfile
from pathlib import Path

UNKNOWN = "UNKNOWN"

# Relative to the repository root.
ARCHIVE_DIR = Path("setup/acceptance/physical_reachable_contact_20261113")
ARCHIVE_ZIP = "raw-43455056965.zip"
ARCHIVE_MANIFEST = "archive.json"

NATIVE_FILES = {
    "provenance": "provenance.json",
    "runtime": "runtime/runtime_result.json",
    "verdict": "verdict.json",
    "run_status": "run_status.json",
    "public_task": "public_task.json",
    "world_summary": "worldstate/summary.json",
    "world_states": "worldstate/world_state.jsonl",
    "world_events": "worldstate/events.jsonl",
    "goal_glob": "contact_goals/*/action_result.json",
    "composite_glob": "sim/skills/composites/*.jsonl",
}


class AdapterError(Exception):
    """Bad archive or unsafe extraction; CLI exit 2."""


def _issue(code, detail, **extra):
    item = dict(code=code, check="normalize", detail=detail)
    item.update(extra)
    return item


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_zip(zip_path, manifest=None, expected_sha=None):
    """Return the archive SHA. Refuse a mismatch with the recorded manifest."""
    zip_path = Path(zip_path)
    if not zip_path.is_file():
        raise AdapterError("archive not found: %s" % zip_path)
    digest = sha256_file(zip_path)
    if expected_sha and expected_sha.lower() != digest:
        raise AdapterError("archive SHA mismatch: expected %s, got %s"
                           % (expected_sha, digest))
    if manifest is None:
        return digest, "UNKNOWN"
    manifest = Path(manifest)
    if not manifest.is_file():
        raise AdapterError("archive manifest not found: %s" % manifest)
    try:
        doc = _json(manifest)
    except (OSError, ValueError) as exc:
        raise AdapterError("cannot read archive manifest: %s" % exc) from exc
    recorded = doc.get("sha256")
    if not recorded:
        raise AdapterError("archive manifest has no sha256 field: %s" % manifest)
    if recorded.lower() != digest:
        raise AdapterError("archive SHA mismatch: manifest says %s, file is %s"
                           % (recorded, digest))
    return digest, str(doc.get("executed_source") or UNKNOWN)


def safe_extract(zip_path, dest):
    """Extract into a NEW directory, refusing path traversal and absolute names."""
    dest = Path(dest)
    if dest.exists():
        raise AdapterError("extraction destination already exists: %s" % dest)
    dest.mkdir(parents=True, exist_ok=False)
    try:
        with zipfile.ZipFile(zip_path) as bundle:
            members = bundle.namelist()
            unsafe = []
            for name in members:
                parts = Path(name).parts
                if (name.startswith(("/", "\\")) or ".." in parts
                        or (len(name) > 1 and name[1] == ":")):
                    unsafe.append(name)
            if unsafe:
                raise AdapterError("refusing to extract unsafe member(s): %s"
                                   % unsafe[:5])
            bundle.extractall(dest)
    except (OSError, zipfile.BadZipFile) as exc:
        raise AdapterError("cannot extract archive: %s" % exc) from exc
    return dest


def find_long1(root):
    """Locate the LONG_1 directory without depending on archive top-level name."""
    root = Path(root)
    if root.name == "LONG_1":
        return root
    direct = root / "LONG_1"
    if direct.is_dir():
        return direct
    matches = [p for p in root.rglob("LONG_1") if p.is_dir()]
    if not matches:
        raise AdapterError("no LONG_1 directory under %s" % root)
    return sorted(matches)[0]


def _read_json_file(root, name, issues, source_label):
    path = root / name
    if not path.is_file():
        issues.append(_issue("SOURCE_FILE_ABSENT", "no %s" % name,
                             source=source_label))
        return None
    try:
        return _json(path)
    except (OSError, ValueError) as exc:
        issues.append(_issue("SOURCE_FILE_UNREADABLE", "%s: %s" % (name, exc),
                             source=source_label))
        return None


def _read_jsonl_file(path, issues):
    if not path.is_file():
        return []
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except ValueError as exc:
            issues.append(_issue("SOURCE_LINE_UNREADABLE",
                                 "%s line %d: %s" % (path.name, number, exc),
                                 source=path.as_posix()))
    return rows


def _field(doc, *keys):
    """Return a native field or UNKNOWN. No interpolation, no derivation."""
    for key in keys:
        if isinstance(doc, dict) and key in doc and doc[key] is not None:
            return doc[key]
    return UNKNOWN


def _needed(value, label, source, issues):
    """Record an explicit issue when a required native field is absent."""
    if value == UNKNOWN:
        issues.append(_issue("SOURCE_FIELD_ABSENT", label, source=source))
    return value


def _derived(path, sources, mapping):
    return dict(path=path, sources=sources, mapping=mapping,
                note="read-only field mapping; no value was inferred")


def normalize(root, out, archive_sha=UNKNOWN, executed_source=UNKNOWN,
              tool_sha=UNKNOWN):
    """Write normalized/* into an existing NEW output directory.

    Returns (derived_inputs, issues, meta). ``meta`` records the source SHA and
    the current tool version SEPARATELY, as required by the handoff document.
    """
    root = find_long1(root)
    out = Path(out)
    norm = out / "normalized"
    norm.mkdir(parents=True, exist_ok=False)
    issues = []
    derived = []

    prov = _read_json_file(root, NATIVE_FILES["provenance"], issues, "LONG_1")
    runtime = _read_json_file(root, NATIVE_FILES["runtime"], issues, "LONG_1")
    verdict = _read_json_file(root, NATIVE_FILES["verdict"], issues, "LONG_1")
    run_status = _read_json_file(root, NATIVE_FILES["run_status"], issues, "LONG_1")
    world_summary = _read_json_file(root, NATIVE_FILES["world_summary"], issues,
                                    "LONG_1")

    # -- provenance / identity ------------------------------------------
    identity = {
        "source_file": NATIVE_FILES["provenance"],
        "label": _field(prov, "label"),
        "backend": _field(prov, "backend"),
        "task_sha256": _field(prov, "task_sha256"),
        "image_source_revision": _field(prov, "image_source_revision"),
        "archive_sha256": str(archive_sha),
        "archive_executed_source": str(executed_source),
        "current_tool_version": str(tool_sha),
        "note": ("archive source revision and current tool version are recorded "
                 "separately; a difference is not evidence tampering"),
    }
    (norm / "identity.json").write_text(
        json.dumps(identity, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    derived.append(_derived("normalized/identity.json",
                            [NATIVE_FILES["provenance"],
                             ARCHIVE_DIR.as_posix() + "/" + ARCHIVE_MANIFEST],
                            {"label": "provenance.label",
                             "task_sha256": "provenance.task_sha256",
                             "image_source_revision": "provenance.image_source_revision",
                             "archive_sha256": "manifest.sha256"}))

    # -- composite event sequence (native IDs, never file-name order) ---
    composites = sorted(Path(root).glob(NATIVE_FILES["composite_glob"]))
    if not composites:
        issues.append(_issue("SOURCE_FILE_ABSENT", "no composite jsonl",
                             source=NATIVE_FILES["composite_glob"]))
    events = []
    for path in composites:
        events.extend(_read_jsonl_file(path, issues))
    for event in events:
        if "seq" not in event:
            issues.append(_issue("SOURCE_FIELD_ABSENT",
                                 "composite event has no native seq",
                                 source="sim/skills/composites/*.jsonl"))

    def event_seq(item):
        value = item.get("seq", UNKNOWN)
        return (0, value) if isinstance(value, int) else (1, 0)

    ordered = sorted(events, key=event_seq)
    sequence = {
        "source_files": [p.relative_to(root).as_posix() for p in composites],
        "order_basis": "native composite.seq (not file name or line order)",
        "event_count": len(ordered),
        "events": [{
            "seq": _field(e, "seq"),
            "event": _field(e, "event"),
            "stage_id": _field(e, "stage_id"),
            "goal_uuid": _field(e, "goal_uuid"),
            "component_goal_uuid": _field(e, "component_goal_uuid"),
            "component_run_id": _field(e, "component_run_id"),
            "boundary": _field(e, "boundary"),
        } for e in ordered],
    }
    (norm / "composite_sequence.json").write_text(
        json.dumps(sequence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    derived.append(_derived("normalized/composite_sequence.json",
                            sequence["source_files"],
                            {"seq": "composite.seq",
                             "component_goal_uuid": "composite.component_goal_uuid",
                             "component_run_id": "composite.component_run_id"}))

    # -- contact goals joined by native IDs -----------------------------
    runtime_result = runtime.get("runtime_result") if isinstance(runtime, dict) else None
    component_runs = _field(runtime_result, "component_run_ids")
    component_goals = _field(runtime_result, "component_goal_uuids")
    indexed_runs = (set(component_runs) if isinstance(component_runs, list)
                    else set())
    indexed_goals = (set(component_goals) if isinstance(component_goals, list)
                     else set())

    goal_rows = []
    goal_paths = sorted(root.glob(NATIVE_FILES["goal_glob"]))
    if not goal_paths:
        issues.append(_issue("SOURCE_FILE_ABSENT", "no contact action_result",
                             source=NATIVE_FILES["goal_glob"]))
    for path in goal_paths:
        doc = _read_json_file(path.parent, path.name, issues,
                              path.relative_to(root).as_posix())
        request_id = _field(doc, "request_id")
        goal_uuid = _field(doc, "goal_uuid")
        linked = []
        if request_id in indexed_runs:
            linked.append("request_id=component_run_ids")
        if goal_uuid in indexed_goals:
            linked.append("goal_uuid=component_goal_uuids")
        if not linked:
            issues.append(_issue("SOURCE_LINK_ABSENT",
                                 "no native ID link for %s"
                                 % path.relative_to(root).as_posix(),
                                 source=path.relative_to(root).as_posix()))
        goal_source = path.relative_to(root).as_posix()
        goal_rows.append({
            "source": goal_source,
            "request_id": _needed(request_id, "%s:request_id" % goal_source,
                                  goal_source, issues),
            "goal_uuid": _needed(goal_uuid, "%s:goal_uuid" % goal_source,
                                 goal_source, issues),
            "outcome": _needed(_field(doc, "outcome"), "%s:outcome" % goal_source,
                               goal_source, issues),
            "error_code": _needed(_field(doc, "error_code"),
                                  "%s:error_code" % goal_source,
                                  goal_source, issues),
            "arm_ready": _field(doc, "arm_ready"),
            "return_completed": _field(doc, "return_completed"),
            "motion_terminal_known": _field(doc, "motion_terminal_known"),
            "motion_goals_used": _field(doc, "motion_goals_used"),
            "native_links": linked or UNKNOWN,
        })
    goals_doc = {
        "join_basis": "request_id / goal_uuid from runtime_result and composite",
        "directory_name_used_for_order": False,
        "goals": goal_rows,
    }
    (norm / "contact_goals.json").write_text(
        json.dumps(goals_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    derived.append(_derived("normalized/contact_goals.json",
                            [NATIVE_FILES["runtime"]] +
                            [g["source"] for g in goal_rows],
                            {"request_id": "action_result.request_id ↔ runtime_result.component_run_ids",
                             "goal_uuid": "action_result.goal_uuid ↔ runtime_result.component_goal_uuids"}))

    # -- source claims kept side by side, never synthesised -------------
    claims = [{
        "source": "runtime/runtime_result.json",
        "field": "status",
        "value": _field(runtime, "status"),
        "kind": "source_reference",
    }, {
        "source": "verdict.json",
        "field": "passed",
        "value": _field(verdict, "passed"),
        "kind": "source_reference",
    }, {
        "source": "run_status.json",
        "field": "status",
        "value": _field(run_status, "status"),
        "kind": "source_reference",
    }, {
        "source": "worldstate/summary.json",
        "field": "status",
        "value": _field(world_summary, "status"),
        "kind": "source_reference",
    }]
    distinct = {str(c["value"]) for c in claims if c["value"] != UNKNOWN}
    conflicts = []
    if len(distinct) > 1:
        conflicts.append({
            "fields": ["%s:%s" % (c["source"], c["field"]) for c in claims],
            "detail": "native sources disagree; no conclusion was synthesised",
        })
        issues.append(_issue("SOURCE_CLAIM_CONFLICT",
                             "native status claims differ: %s" % sorted(distinct)))
    for claim in claims:
        if claim["value"] == UNKNOWN:
            issues.append(_issue("SOURCE_FIELD_ABSENT",
                                 "%s:%s" % (claim["source"], claim["field"]),
                                 source=claim["source"]))
    claims_doc = {
        "note": "These are source references only. This adapter computes NO task verdict.",
        "robot_task_outcome": "NOT_EVALUATED",
        "claims": claims,
        "conflicts": conflicts,
    }
    (norm / "source_claims.json").write_text(
        json.dumps(claims_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    derived.append(_derived("normalized/source_claims.json",
                            [c["source"] for c in claims],
                            {"value": "verbatim source field, marked source_reference"}))

    # -- world-state observations: counts only, no stage invention ------
    state_rows = _read_jsonl_file(root / NATIVE_FILES["world_states"], issues)
    event_rows = _read_jsonl_file(root / NATIVE_FILES["world_events"], issues)
    channels = {}
    for row in state_rows:
        key = str(_field(row, "channel"))
        channels[key] = channels.get(key, 0) + 1
    observation_doc = {
        "source_files": [NATIVE_FILES["world_states"], NATIVE_FILES["world_events"]],
        "world_state_records": len(state_rows),
        "world_event_records": len(event_rows),
        "channels": channels or UNKNOWN,
        "world_summary_status": _field(world_summary, "status"),
        "note": ("record counts and native status only; no phase, contact or "
                 "position evidence was created"),
    }
    (norm / "observations.json").write_text(
        json.dumps(observation_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    derived.append(_derived("normalized/observations.json",
                            observation_doc["source_files"],
                            {"channels": "count of world_state.channel",
                             "world_summary_status": "worldstate/summary.json:status"}))

    meta = {
        "label": _field(prov, "label"),
        "archive_sha256": str(archive_sha),
        "archive_executed_source": str(executed_source),
        "image_source_revision": _field(prov, "image_source_revision"),
        "current_tool_version": str(tool_sha),
        "normalized_files": sorted(p.name for p in norm.glob("*.json")),
    }
    return derived, issues, meta
