#!/usr/bin/env python3
"""Audit one archived run directory for the logs its failure analysis needs.

WHY THIS EXISTS: a run that cannot explain itself after the fact is not evidence.
The concrete defect this guards against is recorded in docs/FACT_STATE_20261112.md
(addendum, 2026-11-12): the T08 push probe 's 'push.jsonl' was simply not retained,
because the legacy launch profile had no push_server log_dir entry, and the omission
was only discovered while reading the results. An auditor that reads a run and prints
"ok" for whatever it happens to find cannot catch that - it reports success by
silence. This tool is the opposite: the required inventory is data
(config/run_log_required.json), every missing item is named, and any missing item is
a non-zero exit.

Design rules, in the repository's own terms:
  * read-only input. Nothing under the audited run directory is modified, and no run
    artefact is copied: existing raw failure data is recorded as a path plus sha256,
    so a 600 MB archive costs a hash pass, not a duplicate.
  * every invocation writes a NEW output directory (or refuses, if the requested one
    already exists). Two audits of the same run never overwrite each other.
  * a missing item is printed as "MISSING: <path> (reason)" and exits 1. A run that
    does not exist, an empty directory and an unreadable config are errors (exit 2),
    never a pass.
  * the required set is PHASE-AWARE. A run that never started cannot have an episode
    record, and demanding one would train operators to ignore the report. The phase
    is derived from the run's own evidence (see classify()), never assumed.

Usage:
    python scripts/run_log_audit.py <run-dir-or-parent-dir>
    python scripts/run_log_audit.py runs/ --out-root artifacts/run_log_audit
    python scripts/run_log_audit.py runs/HO-0001 --out /tmp/audit-h0001

Exit codes: 0 all required items present, 1 at least one missing, 2 usage/config
error. See docs/RUN_LOG_RETENTION.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
DEFAULT_CONFIG = "config/run_log_required.json"
REPO_ROOT = Path(__file__).resolve().parents[1]
CHUNK = 1 << 20
# stage ids look like PUSH_A / PLACE_A / MOVE_A in a RESULT detail and in the FSM log
STAGE_TOKEN = re.compile(r"\b[A-Z][A-Z0-9]{1,}_[A-Z]\b")
# a skill-server jsonl cut off by a crash ends in one truncated line; the records
# before it are still valid evidence, so exactly that line is tolerated (and
# reported). Anything else unparseable means the file is not a jsonl at all.
KINDS = ("result_json", "text", "json", "jsonl", "jsonl_any", "glob_json",
         "skill_logs", "crash_evidence")


class UsageError(Exception):
    """Bad input or bad configuration: exit 2, never a silent pass."""


# --------------------------------------------------------------------- helpers
def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def extract_result(text: str):
    """Last RESULT <json> object in a task.out, or None.

    task.out is a log file, so the JSON object is not necessarily the whole file;
    the runtime reads the same marker (runtime/recovery, evolution/proposals).
    """
    for match in reversed(list(re.finditer(r"RESULT ", text))):
        tail = text[match.end():].strip()
        if not tail:
            continue
        try:
            obj, _ = json.JSONDecoder().raw_decode(tail)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def read_json_object(path: Path):
    text = read_text(path)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        obj = extract_result(text)
    return obj if isinstance(obj, dict) else None


def read_jsonl(path: Path):
    """(records, tolerated_partial_line, bad_line_count) for one jsonl file."""
    records = []
    lines = [line for line in read_text(path).splitlines() if line.strip()]
    bad = 0
    for index, line in enumerate(lines):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            bad += 1
            continue
        if isinstance(record, dict):
            records.append(record)
        else:
            bad += 1
    # exactly one bad line is tolerated, and only when it is the final line
    tolerated = bad == 1 and len(lines) > 1 and _last_unparseable(lines)
    return records, tolerated, bad


def _last_unparseable(lines) -> bool:
    try:
        json.loads(lines[-1])
    except json.JSONDecodeError:
        return True
    return False


def rel(run_dir: Path, path: Path) -> str:
    return path.relative_to(run_dir).as_posix()


# ---------------------------------------------------------------------- config
def load_config(path: Path) -> dict:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise UsageError("cannot read config %s: %s" % (path, exc))
    try:
        cfg = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise UsageError("config %s is not valid JSON: %s" % (path, exc))
    problems = validate_config(cfg)
    if problems:
        raise UsageError("config %s is invalid: %s" % (path, "; ".join(problems)))
    return cfg


def validate_config(cfg) -> list:
    problems = []
    if not isinstance(cfg, dict):
        return ["the document must be a JSON object"]
    if cfg.get("schema_version") != SCHEMA_VERSION:
        problems.append("schema_version must be %d" % SCHEMA_VERSION)
    for key in ("default_out_root", "run_markers", "started_evidence",
                "crash_markers", "stage_skill_logs", "phases", "items"):
        if key not in cfg:
            problems.append("missing key %r" % key)
    if problems:
        return problems
    if not isinstance(cfg["phases"], dict) or not cfg["phases"]:
        problems.append("phases must be a non-empty object")
    for key in ("run_markers", "started_evidence", "crash_markers"):
        values = cfg[key]
        if not isinstance(values, list) or not all(
                isinstance(value, str) and value for value in values):
            problems.append("%s must be a list of non-empty strings" % key)
    stage_logs = cfg["stage_skill_logs"]
    if not isinstance(stage_logs, dict) or not all(
            isinstance(k, str) and isinstance(v, str)
            for k, v in stage_logs.items()):
        problems.append("stage_skill_logs must map stage prefix -> log file name")
    items = cfg["items"]
    if not isinstance(items, list) or not items:
        problems.append("items must be a non-empty list")
        return problems
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            problems.append("every item must be an object")
            continue
        ident = item.get("id")
        if not isinstance(ident, str) or not ident:
            problems.append("every item needs a non-empty id")
            continue
        if ident in seen:
            problems.append("duplicate item id %r" % ident)
        seen.add(ident)
        kind = item.get("kind")
        if kind not in KINDS:
            problems.append("item %s has unknown kind %r (known: %s)"
                            % (ident, kind, ", ".join(KINDS)))
            continue
        phases = item.get("phases")
        if not isinstance(phases, list) or not all(
                phase in cfg["phases"] for phase in phases):
            problems.append("item %s must list phases declared in the config"
                            % ident)
        if not str(item.get("reason") or "").strip():
            problems.append("item %s needs a reason: the audit prints it" % ident)
        if kind in ("result_json", "text", "json", "jsonl", "glob_json"):
            if not isinstance(item.get("path"), str) or not item["path"]:
                problems.append("item %s needs a path" % ident)
        if kind == "jsonl_any":
            paths = item.get("paths")
            if not isinstance(paths, list) or not paths:
                problems.append("item %s needs a non-empty paths list" % ident)
        if kind == "crash_evidence":
            sources = item.get("sources")
            if not isinstance(sources, list) or not sources:
                problems.append("item %s needs a non-empty sources list" % ident)
        if kind == "glob_json":
            if item.get("validate") not in (None, "episode"):
                problems.append("item %s has unknown validate %r"
                                % (ident, item.get("validate")))
    return problems


# ----------------------------------------------------------------- phase + runs
def classify(run_dir: Path, cfg: dict, result) -> str:
    """Phase of one run, derived from its own artefacts.

    success          - the run's RESULT says outcome 0 / error_code 0.
    failure          - it started (a RESULT that is not successful, or task-layer
                       evidence exists) and did not report success.
    startup_failure  - nothing shows it ever reached the task layer.

    An unknown outcome is deliberately NOT a success: a run whose result record is
    missing is classified as failure, so task_result is reported missing instead of
    the run being waved through.
    """
    if result is not None:
        try:
            outcome = int(result.get("outcome", -1))
            error_code = int(result.get("error_code") or 0)
        except (TypeError, ValueError):
            return "failure"
        return "success" if outcome == 0 and error_code == 0 else "failure"
    for pattern in cfg["started_evidence"]:
        if any(run_dir.glob(pattern)):
            return "failure"
    return "startup_failure"


def discover_runs(target: Path, cfg: dict) -> list:
    """The run directory itself, or every run directory directly below it."""
    def is_run(candidate: Path) -> bool:
        # any(generator) is truthy even when empty, so materialise the match:
        # a bare generator expression here silently made EVERY directory a run.
        return candidate.is_dir() and any(
            next(iter(candidate.glob(pattern)), None) is not None
            for pattern in cfg["run_markers"])

    if is_run(target):
        return [target]
    runs = sorted(child for child in target.iterdir() if is_run(child))
    if not runs:
        raise UsageError(
            "%s is not a run directory and contains none (a run must have at "
            "least one of: %s)"
            % (target, ", ".join(cfg["run_markers"])))
    return runs


# --------------------------------------------------------------- item checkers
def _miss(item, path, reason=None, detail=None):
    entry = {"id": item["id"], "path": path, "reason": reason or item["reason"]}
    if detail:
        entry["detail"] = detail
    return entry


def _check_result_json(item, ctx):
    path = ctx["run_dir"] / item["path"]
    if not path.is_file():
        return [_miss(item, item["path"], detail="file is absent")]
    if extract_result(read_text(path)) is None:
        return [_miss(item, item["path"], detail="no parseable RESULT object")]
    return []


def _check_text(item, ctx):
    path = ctx["run_dir"] / item["path"]
    if not path.is_file():
        return [_miss(item, item["path"], detail="file is absent")]
    if not read_text(path).strip():
        return [_miss(item, item["path"], detail="file is empty")]
    return []


def _check_json(item, ctx):
    path = ctx["run_dir"] / item["path"]
    if not path.is_file():
        return [_miss(item, item["path"], detail="file is absent")]
    if read_json_object(path) is None:
        return [_miss(item, item["path"], detail="not a JSON object")]
    return []


def _check_jsonl(item, ctx):
    path = ctx["run_dir"] / item["path"]
    minimum = int(item.get("min_records", 1))
    if not path.is_file():
        return [_miss(item, item["path"], detail="file is absent")]
    records, tolerated, bad = read_jsonl(path)
    if bad and not tolerated:
        return [_miss(item, item["path"],
                      detail="%d unparseable line(s)" % bad)]
    if len(records) < minimum:
        return [_miss(item, item["path"],
                      detail="%d record(s), need %d" % (len(records), minimum))]
    return []


def _check_jsonl_any(item, ctx):
    minimum = int(item.get("min_present", 1))
    present = []
    details = []
    for name in item["paths"]:
        path = ctx["run_dir"] / name
        if not path.is_file():
            details.append("%s absent" % name)
            continue
        records, _tolerated, _bad = read_jsonl(path)
        if records:
            present.append(name)
        else:
            details.append("%s empty" % name)
    if len(present) < minimum:
        return [_miss(item, "|".join(item["paths"]),
                      detail="; ".join(details))]
    return []


def _check_glob_json(item, ctx):
    run_dir = ctx["run_dir"]
    matches = sorted(p for p in run_dir.glob(item["path"]) if p.is_file())
    minimum = int(item.get("min_matches", 1))
    if len(matches) < minimum:
        return [_miss(item, item["path"],
                      detail="%d match(es), need %d" % (len(matches), minimum))]
    missing = []
    if item.get("validate") == "episode":
        for path in matches:
            record = read_json_object(path)
            if record is None:
                missing.append(_miss(item, rel(run_dir, path),
                                     detail="not a JSON object"))
            elif "EpisodeSchemaVersion" not in record or not isinstance(
                    record.get("steps"), list):
                missing.append(_miss(
                    item, rel(run_dir, path),
                    detail="not an episode record "
                           "(no EpisodeSchemaVersion/steps)"))
    return missing


def stage_ids(ctx) -> dict:
    """skill log -> set of stage ids whose evidence shows that skill ran."""
    run_dir = ctx["run_dir"]
    ids = set()
    result = ctx["result"] or {}
    for value in result.get("completed_stage_ids") or []:
        if isinstance(value, str):
            ids.add(value)
    if isinstance(result.get("detail"), str):
        ids.update(STAGE_TOKEN.findall(result["detail"]))
    for name in ("task_fsm.jsonl", "demo_runs.jsonl"):
        path = run_dir / name
        if not path.is_file():
            continue
        records, _tolerated, _bad = read_jsonl(path)
        for record in records:
            for key in ("completed_stage_ids", "stage_ids", "stages"):
                value = record.get(key)
                if isinstance(value, list):
                    ids.update(v for v in value if isinstance(v, str))
                elif isinstance(value, str):
                    ids.add(value)
    needed = {}
    for ident in sorted(ids):
        log = ctx["cfg"]["stage_skill_logs"].get(ident.split("_", 1)[0])
        if log:
            needed.setdefault(log, set()).add(ident)
    return needed


def _check_skill_logs(item, ctx):
    run_dir = ctx["run_dir"]
    missing = []
    for log, idents in sorted(stage_ids(ctx).items()):
        if (run_dir / log).is_file():
            continue
        missing.append(_miss(item, log, reason="%s (stage %s)" % (
            item["reason"], ", ".join(sorted(idents)))))
    return missing


def _source_has_detail(run_dir: Path, source: str, markers) -> bool:
    name, _, field = source.partition(":")
    path = run_dir / name
    if not path.is_file():
        return False
    text = read_text(path)
    if field == "markers":
        return any(marker in text for marker in markers)
    if field:
        record = read_json_object(path)
        if not isinstance(record, dict):
            return False
        return bool(str(record.get(field) or "").strip())
    return bool(text.strip())


def _check_crash_evidence(item, ctx):
    markers = ctx["cfg"]["crash_markers"]
    for source in item["sources"]:
        if _source_has_detail(ctx["run_dir"], source, markers):
            return []
    return [_miss(item, "|".join(item["sources"]))]


CHECKERS = {
    "result_json": _check_result_json,
    "text": _check_text,
    "json": _check_json,
    "jsonl": _check_jsonl,
    "jsonl_any": _check_jsonl_any,
    "glob_json": _check_glob_json,
    "skill_logs": _check_skill_logs,
    "crash_evidence": _check_crash_evidence,
}


# ------------------------------------------------------------------- one audit
def pointers(run_dir: Path) -> list:
    """Path + size + sha256 for every file in the run: a pointer, not a copy."""
    out = []
    for path in sorted(p for p in run_dir.rglob("*") if p.is_file()):
        out.append({"path": rel(run_dir, path),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path)})
    return out


def audit_run(run_dir: Path, cfg: dict) -> dict:
    task_out = run_dir / "task.out"
    result = extract_result(read_text(task_out)) if task_out.is_file() else None
    phase = classify(run_dir, cfg, result)
    ctx = {"run_dir": run_dir, "cfg": cfg, "result": result, "phase": phase}
    missing = []
    required = []
    for item in cfg["items"]:
        if phase not in item["phases"]:
            continue
        required.append(item["id"])
        missing.extend(CHECKERS[item["kind"]](item, ctx))
    needed = stage_ids(ctx)
    return {
        "run_id": run_dir.name,
        "run_dir": str(run_dir),
        "phase": phase,
        "passed": not missing,
        "required_ids": required,
        "missing": missing,
        "stage_ids": sorted({i for idents in needed.values()
                             for i in idents}),
        "artifacts": pointers(run_dir),
    }


def make_out_dir(out_root: Path, explicit):
    if explicit:
        out = Path(explicit)
        if out.exists():
            raise UsageError("refusing to write into an existing output "
                             "directory: %s" % out)
        out.mkdir(parents=True, exist_ok=False)
        return out
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = "run_log_audit_%s" % stamp
    for index in range(1, 1000):
        candidate = out_root / (base if index == 1 else "%s-%d" % (base, index))
        try:
            candidate.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            continue
        return candidate
    raise UsageError("cannot allocate a fresh output directory under %s"
                     % out_root)


def build_report(cfg, cfg_path: Path, runs, out_dir: Path) -> dict:
    total_missing = sum(len(run["missing"]) for run in runs)
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": "scripts/run_log_audit.py",
        "generated_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "out_dir": str(out_dir),
        "config": {"path": str(cfg_path), "sha256": sha256_file(cfg_path)},
        "phases": cfg["phases"],
        "runs": runs,
        "totals": {
            "runs": len(runs),
            "passed": sum(1 for run in runs if run["passed"]),
            "failed": sum(1 for run in runs if not run["passed"]),
            "missing_items": total_missing,
            "files_pointed_at": sum(len(run["artifacts"]) for run in runs),
        },
        "passed": total_missing == 0,
    }


def print_report(report: dict) -> None:
    for run in report["runs"]:
        print("run %s phase=%s required=%d missing=%d"
              % (run["run_id"], run["phase"], len(run["required_ids"]),
                 len(run["missing"])))
        for item in run["missing"]:
            print("MISSING: %s/%s (%s)" % (run["run_id"], item["path"],
                                          item["reason"]))
    totals = report["totals"]
    print("audit summary: %d run(s), %d passed, %d failed, %d missing item(s)"
          % (totals["runs"], totals["passed"], totals["failed"],
             totals["missing_items"]))
    print("pointers: %d file(s) recorded with sha256, 0 bytes copied"
          % totals["files_pointed_at"])
    print("out: %s" % report["out_dir"])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit run directories for required logs.")
    parser.add_argument("target",
                        help="a run directory, or a parent directory of runs")
    parser.add_argument("--config", default=DEFAULT_CONFIG,
                        help="required-log inventory (default: %(default)s)")
    parser.add_argument("--out-root",
                        help="parent for the new output directory "
                             "(default: the config default_out_root)")
    parser.add_argument("--out",
                        help="exact new output directory; must not exist")
    args = parser.parse_args(argv)

    try:
        # relative paths resolve against the current directory, except the two
        # defaults, which belong to the repository so the tool works from anywhere
        cfg_path = Path(args.config)
        if not cfg_path.is_absolute() and not cfg_path.is_file():
            cfg_path = REPO_ROOT / cfg_path
        cfg = load_config(cfg_path)
        target = Path(args.target)
        if not target.is_dir():
            raise UsageError("run directory not found: %s" % target)
        runs = discover_runs(target, cfg)
        if args.out_root:
            out_root = Path(args.out_root)
        else:
            out_root = REPO_ROOT / cfg["default_out_root"]
        out_dir = make_out_dir(out_root, args.out)
    except UsageError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2

    audited = [audit_run(run, cfg) for run in runs]
    report = build_report(cfg, cfg_path, audited, out_dir)
    (out_dir / "audit.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print_report(report)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
