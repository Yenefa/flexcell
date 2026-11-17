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


# --------------------------------------------- layout and RESULT dialect support
# Two recorders have written the same evidence in two layouts:
#   flat     task.out / decisions.jsonl / sim/episodes/*.json      (the older one,
#            and the only one this config used to name)
#   layered  task.stdout / skills/*.jsonl / episodes/*.json        (sim_window)
# Both are accepted: the config names the flat path, alt_paths lists the layered
# equivalent, so another layout is a config edit rather than a code edit.
def candidate_paths(item) -> list:
    """The configured path first, then every alternate, de-duplicated."""
    names = []
    primary = item.get("path")
    if isinstance(primary, str) and primary:
        names.append(primary)
    for alt in item.get("alt_paths") or []:
        if isinstance(alt, str) and alt and alt not in names:
            names.append(alt)
    return names


# RESULT dialect 1 (numeric): {"outcome": 0, "error_code": 0}
# RESULT dialect 2 (enum):    {"outcome": "OUTCOME_SUCCEEDED", "outcome_val": 0,
#                              "error_code": "ERR_NONE"}
# A field we cannot interpret must stay None: an unknown outcome is never success.
_OUTCOME_SUCCESS = ("OUTCOME_SUCCEEDED", "SUCCEEDED", "SUCCESS", "OK")
_OUTCOME_FAILURE = ("OUTCOME_FAILED", "OUTCOME_REJECTED", "OUTCOME_ABORTED",
                    "FAILED", "FAILURE", "ERROR")


def _outcome_int(value):
    if isinstance(value, bool):
        return 0 if value else 1
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        token = value.strip().upper()
        if token in _OUTCOME_SUCCESS:
            return 0
        if token in _OUTCOME_FAILURE:
            return 1
    return None


def _error_code_int(value):
    if isinstance(value, bool):
        return 0 if value else 1
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        token = value.strip().upper()
        if token in ("", "ERR_NONE", "NONE", "OK", "NO_ERROR"):
            return 0
        if token.startswith("ERR_"):
            return 1
    return None


def result_outcome(result):
    """(outcome:int|None, error_code:int|None) from either RESULT dialect."""
    if not isinstance(result, dict):
        return None, None
    outcome = _outcome_int(result.get("outcome"))
    if outcome is None:
        outcome = _outcome_int(result.get("outcome_val"))
    return outcome, _error_code_int(result.get("error_code"))


def task_outcome_label(result) -> str:
    """SUCCEEDED / FAILED / UNKNOWN for one RESULT object.

    UNKNOWN is not a failure and not a success: it means the record cannot be
    read, which is a different statement from "the robot task failed".
    """
    outcome, error_code = result_outcome(result)
    if outcome is None:
        return "UNKNOWN"
    if error_code not in (None, 0):
        return "FAILED"
    return "SUCCEEDED" if outcome == 0 else "FAILED"


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
        outcome, error_code = result_outcome(result)
        if outcome is None:
            # an unreadable outcome is not a pass (see the docstring above)
            return "failure"
        if error_code is None:
            error_code = 0
        return "success" if outcome == 0 and error_code == 0 else "failure"
    for pattern in cfg["started_evidence"]:
        if any(run_dir.glob(pattern)):
            return "failure"
    return "startup_failure"


def discover_runs(target: Path, cfg: dict) -> list:
    """The run directory itself, or the run directories below it.

    A window-level directory (one that holds window.json / declaration.json) is
    a container, never a run: treating it as a run audits the wrong thing and
    reports the whole batch as failed. Containers are searched one level down,
    then two, which covers <window>/trial-01/run-XXXX as well.
    """
    container_markers = list(cfg.get("container_markers") or [])
    run_patterns = list(cfg["run_markers"]) + list(
        cfg.get("nested_run_markers") or [])

    def is_container(candidate: Path) -> bool:
        return any((candidate / name).is_file() for name in container_markers)

    def is_run(candidate: Path) -> bool:
        # any(generator) is truthy even when empty, so materialise the match:
        # a bare generator expression here silently made EVERY directory a run.
        if not candidate.is_dir() or is_container(candidate):
            return False
        return any(
            next(iter(candidate.glob(pattern)), None) is not None
            for pattern in run_patterns)

    if is_run(target):
        return [target]
    runs = sorted(child for child in target.iterdir() if is_run(child))
    if runs:
        return runs
    # one more level: <window>/trial-01/run-XXXX
    deeper = []
    for child in sorted(target.iterdir()):
        if not child.is_dir() or is_run(child):
            continue
        deeper.extend(grand for grand in child.iterdir() if is_run(grand))
    if deeper:
        return sorted(deeper)
    raise UsageError(
        "%s is not a run directory and contains none (a run must have at "
        "least one of: %s)"
        % (target, ", ".join(run_patterns)))


# --------------------------------------------------------------- item checkers
def _miss(item, path, reason=None, detail=None):
    entry = {"id": item["id"], "path": path, "reason": reason or item["reason"]}
    if detail:
        entry["detail"] = detail
    return entry


def _check_result_json(item, ctx):
    names = candidate_paths(item)
    tried = []
    for name in names:
        path = ctx["run_dir"] / name
        if not path.is_file():
            tried.append("%s absent" % name)
            continue
        if extract_result(read_text(path)) is None:
            tried.append("%s has no parseable RESULT object" % name)
            continue
        return []
    return [_miss(item, names[0], detail="; ".join(tried))]


def _check_text(item, ctx):
    names = candidate_paths(item)
    tried = []
    for name in names:
        path = ctx["run_dir"] / name
        if not path.is_file():
            tried.append("%s absent" % name)
            continue
        if not read_text(path).strip():
            tried.append("%s is empty" % name)
            continue
        return []
    return [_miss(item, names[0], detail="; ".join(tried))]


def _check_json(item, ctx):
    names = candidate_paths(item)
    tried = []
    for name in names:
        path = ctx["run_dir"] / name
        if not path.is_file():
            tried.append("%s absent" % name)
            continue
        if read_json_object(path) is None:
            tried.append("%s is not a JSON object" % name)
            continue
        return []
    return [_miss(item, names[0], detail="; ".join(tried))]


def _check_jsonl(item, ctx):
    names = candidate_paths(item)
    minimum = int(item.get("min_records", 1))
    tried = []
    for name in names:
        path = ctx["run_dir"] / name
        if not path.is_file():
            tried.append("%s absent" % name)
            continue
        records, tolerated, bad = read_jsonl(path)
        if bad and not tolerated:
            tried.append("%s: %d unparseable line(s)" % (name, bad))
            continue
        if len(records) < minimum:
            tried.append("%s: %d record(s), need %d"
                         % (name, len(records), minimum))
            continue
        return []
    return [_miss(item, names[0], detail="; ".join(tried))]


def _search_prefixes(cfg) -> list:
    prefixes = [""] + [p for p in (cfg.get("search_prefixes") or [])
                       if isinstance(p, str)]
    seen = []
    for prefix in prefixes:
        if prefix not in seen:
            seen.append(prefix)
    return seen


def _find_under(run_dir: Path, name: str, prefixes) -> Path | None:
    """run_dir/name, then run_dir/<prefix>/name for each configured prefix."""
    for prefix in prefixes:
        path = run_dir / prefix / name if prefix else run_dir / name
        if path.is_file():
            return path
    return None


def _check_jsonl_any(item, ctx):
    minimum = int(item.get("min_present", 1))
    prefixes = _search_prefixes(ctx["cfg"])
    present = []
    details = []
    for name in item["paths"]:
        path = _find_under(ctx["run_dir"], name, prefixes)
        if path is None:
            details.append("%s absent" % name)
            continue
        records, _tolerated, _bad = read_jsonl(path)
        if records:
            present.append(rel(ctx["run_dir"], path))
        else:
            details.append("%s empty" % name)
    if len(present) < minimum:
        return [_miss(item, "|".join(item["paths"]),
                      detail="; ".join(details))]
    return []


def _check_glob_json(item, ctx):
    run_dir = ctx["run_dir"]
    names = candidate_paths(item)
    matches = []
    for name in names:
        matches = sorted(p for p in run_dir.glob(name) if p.is_file())
        if matches:
            break
    minimum = int(item.get("min_matches", 1))
    if len(matches) < minimum:
        return [_miss(item, names[0],
                      detail="%d match(es) over [%s], need %d"
                             % (len(matches), ", ".join(names), minimum))]
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
    prefixes = _search_prefixes(ctx["cfg"])
    for name in ("task_fsm.jsonl", "demo_runs.jsonl"):
        path = _find_under(run_dir, name, prefixes)
        if path is None:
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
    prefixes = _search_prefixes(ctx["cfg"])
    missing = []
    for log, idents in sorted(stage_ids(ctx).items()):
        if _find_under(run_dir, log, prefixes) is not None:
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


RESULT_SOURCES = ("task.out", "task.stdout")


def audit_run(run_dir: Path, cfg: dict) -> dict:
    result = None
    result_source = None
    for name in RESULT_SOURCES:
        path = run_dir / name
        if not path.is_file():
            continue
        found = extract_result(read_text(path))
        if found is not None:
            result, result_source = found, name
            break
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
    # task_outcome and audit_status answer two different questions and are kept
    # apart on purpose: "the robot task failed" is not what a missing log means.
    return {
        "run_id": run_dir.name,
        "run_dir": str(run_dir),
        "phase": phase,
        "task_outcome": task_outcome_label(result),
        "result_source": result_source,
        "audit_status": "complete" if not missing else "incomplete",
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
            "audit_complete": sum(1 for run in runs
                                  if run["audit_status"] == "complete"),
            "audit_incomplete": sum(1 for run in runs
                                    if run["audit_status"] != "complete"),
            "task_succeeded": sum(1 for run in runs
                                  if run["task_outcome"] == "SUCCEEDED"),
            "task_failed": sum(1 for run in runs
                               if run["task_outcome"] == "FAILED"),
            "task_unknown": sum(1 for run in runs
                                if run["task_outcome"] == "UNKNOWN"),
            "passed": sum(1 for run in runs if run["passed"]),
            "failed": sum(1 for run in runs if not run["passed"]),
            "missing_items": total_missing,
            "files_pointed_at": sum(len(run["artifacts"]) for run in runs),
        },
        "passed": total_missing == 0,
    }


def print_report(report: dict) -> None:
    for run in report["runs"]:
        print("run %s phase=%s task=%s audit=%s required=%d missing=%d"
              % (run["run_id"], run["phase"], run["task_outcome"],
                 run["audit_status"], len(run["required_ids"]),
                 len(run["missing"])))
        for item in run["missing"]:
            print("MISSING: %s/%s (%s)" % (run["run_id"], item["path"],
                                          item["reason"]))
    totals = report["totals"]
    # "passed" is kept as the audit-completeness word it always was (it is the
    # word the acceptance tests and docs quote); the run's own robot-task result
    # is reported on the next line so the two are never read as one.
    print("audit summary: %d run(s), %d passed (audit-complete), "
          "%d audit-incomplete, %d missing item(s)"
          % (totals["runs"], totals["audit_complete"],
             totals["audit_incomplete"], totals["missing_items"]))
    print("task outcomes: %d succeeded, %d failed, %d unknown"
          % (totals["task_succeeded"], totals["task_failed"],
             totals["task_unknown"]))
    print("note: task= comes from the run's own RESULT; audit= is log "
          "completeness only. An audit-incomplete run is NOT a failed "
          "robot task.")
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
