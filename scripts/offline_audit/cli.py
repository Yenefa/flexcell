#!/usr/bin/env python3
"""Unified, read-only offline execution-evidence audit entry (issue #246).

Three EXISTING tools are invoked, each with its own new output directory:

  retention : scripts/run_log_audit.py
  progress  : scripts/push_progress_audit.py
  timeline  : scripts/pose_stage_timeline.py

This module implements no measurement and no acceptance rule. It only runs those
tools, keeps their reports and writes one aggregate report.json. The three exit
codes of this CLI are about the DIAGNOSTIC RUN (0 ok, 1 incomplete data, 2 tool or
I/O error) and are never a robot task verdict.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE = ROOT / "config" / "offline_audit_profiles" / "native.json"
SCHEMA = "offline-run-audit/1"

# Each check runs only when at least one of its input patterns is present.
# A missing stream is disclosed as UNKNOWN; nothing is filled in for it.
PROFILE_DEFAULTS = {
    "schema_version": 1,
    "requires": {
        "retention": [],
        "progress": ["push_attempts.jsonl", "attempts.jsonl",
                     "contact_push.jsonl", "skills/push.jsonl",
                     "skills/push_object.jsonl"],
        "timeline": [["observations.jsonl", "world_state.jsonl", "poses.jsonl",
                      "data/observations.jsonl"],
                     ["phases.jsonl", "stages.jsonl", "action_phases.jsonl",
                      "data/phases.jsonl"]],
    },
}

OK_STATUSES = {"OK", "MEASURED", "COMPLETE", "ALIGNED", "SUCCESS"}


class UsageError(Exception):
    """Bad arguments or an unsafe output path: CLI exit 2."""


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_profile(path):
    if path is None:
        profile = json.loads(json.dumps(PROFILE_DEFAULTS))
        profile["path"] = str(DEFAULT_PROFILE) if DEFAULT_PROFILE.is_file() else "UNKNOWN"
        return profile
    path = Path(path)
    if not path.is_file():
        raise UsageError("profile not found: %s" % path)
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UsageError("cannot read profile %s: %s" % (path, exc)) from exc
    if not isinstance(profile, dict):
        raise UsageError("profile must be a JSON object: %s" % path)
    merged = json.loads(json.dumps(PROFILE_DEFAULTS))
    merged.update(profile)
    requires = merged.get("requires") or {}
    if not isinstance(requires, dict):
        raise UsageError("profile.requires must be an object: %s" % path)
    for name in ("retention", "progress", "timeline"):
        merged["requires"].setdefault(name, PROFILE_DEFAULTS["requires"][name])
    merged["path"] = str(path)
    return merged


def validate_paths(run, out):
    """Resolve symlinks BEFORE deciding that an output is outside the input."""
    run = Path(run)
    out = Path(out)
    if not run.is_dir():
        raise UsageError("run directory not found: %s" % run)
    if out.exists():
        raise UsageError("output directory already exists: %s" % out)
    run_r, out_r = run.resolve(), out.resolve()
    if out_r == run_r or run_r in out_r.parents:
        raise UsageError("output must be outside the run directory: %s" % out)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise UsageError("cannot create output parent: %s" % exc) from exc
    if out.exists():
        raise UsageError("output directory already exists: %s" % out)
    return run_r, out_r


def input_digests(run):
    rows = []
    for path in sorted(p for p in run.rglob("*") if p.is_file()):
        try:
            rows.append(dict(path=path.relative_to(run).as_posix(),
                             sha256=sha256_file(path), bytes=path.stat().st_size))
        except OSError as exc:
            rows.append(dict(path=path.relative_to(run).as_posix(),
                             sha256="UNKNOWN", bytes=None, error=str(exc)))
    return rows


def has_input(run, patterns):
    """patterns: a flat list (any one) or a list of AND groups."""
    if not patterns:
        return True
    if patterns and isinstance(patterns[0], list):
        return all(any(any(run.glob(name)) for name in group)
                   for group in patterns)
    return any(any(run.glob(name)) for name in patterns)


def retention_cmd(run, out):
    return [sys.executable, str(ROOT / "scripts" / "run_log_audit.py"),
            str(run), "--out", str(out)]


def progress_cmd(run, out):
    return [sys.executable, str(ROOT / "scripts" / "push_progress_audit.py"),
            str(run), "--out", str(out)]


def timeline_cmd(run, out):
    return [sys.executable, str(ROOT / "scripts" / "pose_stage_timeline.py"),
            str(run), "--out", str(out)]


SUBTOOLS = {"retention": retention_cmd, "progress": progress_cmd,
            "timeline": timeline_cmd}
SUBTOOL_REPORT = {"retention": "audit.json", "progress": "summary.json",
                  "timeline": "summary.json"}


def _issue(check, code, detail, **extra):
    item = dict(code=code, check=check, detail=detail)
    item.update(extra)
    return item


def _summary_status(summary):
    status = summary.get("status") or summary.get("code") or "UNKNOWN"
    status = str(status)
    if status.upper() in OK_STATUSES:
        return "COMPLETE"
    return status


def _reason_codes(check, summary):
    codes = summary.get("reason_codes") or []
    if isinstance(codes, str):
        codes = [codes]
    code = summary.get("code")
    if code and code not in codes:
        codes = list(codes) + [code]
    if check == "retention":
        totals = summary.get("totals") or {}
        if totals.get("missing_items"):
            codes = list(codes) + ["RETENTION_ITEMS_MISSING"]
    return codes


def run_check(name, run, out, profile, build_cmd):
    """Run one existing tool. Never raise on a child failure: report it."""
    check_dir = out / name
    check = dict(name=name, executed=False, status="NOT_APPLICABLE",
                 exit_code=None, reason_codes=[], sub_report=None,
                 stdout="", stderr="")
    issues = []
    requires = profile["requires"].get(name) or []
    if not has_input(run, requires):
        issues.append(_issue(name, "INPUT_ABSENT",
                             "no input matching %s under the run; no value was inferred"
                             % (requires,)))
        return dict(check=check, issues=issues), 1

    check_dir.mkdir(parents=True, exist_ok=True)
    command = build_cmd(run, check_dir)
    check["executed"] = True
    try:
        proc = subprocess.run(command, cwd=str(ROOT), capture_output=True,
                              text=True, timeout=900, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        check["status"], check["stderr"] = "ERROR", str(exc)
        issues.append(_issue(name, "SUBTOOL_ERROR", str(exc)))
        return dict(check=check, issues=issues), 2
    check["exit_code"] = proc.returncode
    check["stdout"] = proc.stdout[-4000:]
    check["stderr"] = proc.stderr[-4000:]

    report_file = check_dir / SUBTOOL_REPORT[name]
    if report_file.is_file():
        check["sub_report"] = "%s/%s" % (name, SUBTOOL_REPORT[name])
        try:
            summary = json.loads(report_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            check["status"] = "ERROR"
            issues.append(_issue(name, "SUBTOOL_REPORT_UNREADABLE", str(exc)))
            return dict(check=check, issues=issues), 2
        check["reason_codes"] = _reason_codes(name, summary)
        check["status"] = _summary_status(summary)
        if summary.get("inputs_unchanged") is False:
            check["status"] = "ERROR"
            issues.append(_issue(name, "INPUT_CHANGED",
                                 "an input changed while the sub-tool was reading it"))
        if name == "retention":
            for entry in summary.get("runs") or []:
                for item in entry.get("missing") or []:
                    issues.append(_issue(name, "RETENTION_MISSING",
                                         item.get("reason", "required log absent"),
                                         path="%s/%s" % (entry.get("run_id"),
                                                         item.get("path"))))
        elif check["status"] != "COMPLETE":
            issues.append(_issue(name, "NOT_FULLY_DETERMINED",
                                 "sub-tool disclosed an incomplete result: %s"
                                 % (check["reason_codes"] or check["status"])))
    else:
        check["status"] = "ERROR"
        issues.append(_issue(name, "SUBTOOL_REPORT_MISSING",
                             "no %s written by %s" % (SUBTOOL_REPORT[name], name)))

    if name == "retention" and proc.returncode == 1:
        if not any(i["code"] == "RETENTION_MISSING" for i in issues):
            issues.append(_issue(name, "RETENTION_INCOMPLETE",
                                 check["stderr"] or "required logs missing"))
        return dict(check=check, issues=issues), 1
    if proc.returncode != 0:
        check["status"] = "ERROR"
        issues.append(_issue(name, "SUBTOOL_EXIT", "exit code %d" % proc.returncode,
                             exit_code=proc.returncode))
        return dict(check=check, issues=issues), 2
    if check["status"] == "ERROR":
        return dict(check=check, issues=issues), 2
    if any(i["check"] == name and i["code"] != "INPUT_CHANGED" for i in issues):
        return dict(check=check, issues=issues), 1
    return dict(check=check, issues=issues), 0


def build_report(run, out, profile=None, source_sha=None, subtools=None):
    """Run all checks into a NEW out directory; return (report, exit_code)."""
    run, out = validate_paths(run, out)
    profile = load_profile(profile)
    builders = dict(SUBTOOLS)
    if subtools:
        builders.update(subtools)
    out.mkdir(parents=True, exist_ok=False)
    before = input_digests(run)
    report = {
        "schema_version": SCHEMA,
        "diagnostic_only": True,
        "robot_task_outcome": "NOT_EVALUATED",
        "source": dict(run_dir=str(run), run_id=run.name,
                       source_sha256=source_sha or "UNKNOWN",
                       profile=profile.get("path", "UNKNOWN"),
                       inputs=before),
        "checks": [], "issues": [], "derived_inputs": [],
        "out_dir": str(out),
    }
    exit_code = 0
    for name in ("retention", "progress", "timeline"):
        result, severity = run_check(name, run, out, profile, builders[name])
        report["checks"].append(result["check"])
        report["issues"].extend(result["issues"])
        exit_code = max(exit_code, severity)
    after = input_digests(run)
    if before != after:
        report["issues"].append(_issue("aggregate", "INPUT_CHANGED",
                                       "the run directory changed during the audit"))
        exit_code = 2
    with (out / "report.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return report, exit_code


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Read-only offline execution-evidence audit (diagnostic only).")
    parser.add_argument("--run", required=True, help="existing run directory (read-only)")
    parser.add_argument("--out", required=True, help="NEW output directory outside --run")
    parser.add_argument("--profile", help="evidence-format profile JSON")
    parser.add_argument("--source-sha", help="known execution-source SHA, else UNKNOWN")
    args = parser.parse_args(argv)
    try:
        report, exit_code = build_report(args.run, args.out, args.profile,
                                         args.source_sha)
    except UsageError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    print(json.dumps(dict(kind="offline-run-audit", schema_version=SCHEMA,
                          diagnostic_only=True, robot_task_outcome="NOT_EVALUATED",
                          issues=len(report["issues"]), exit_code=exit_code,
                          out=report["out_dir"]), allow_nan=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
