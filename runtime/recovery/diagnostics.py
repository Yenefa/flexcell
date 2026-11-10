#!/usr/bin/env python3
"""Extract per-stage native diagnostics from a composite journal.

WHY: the composite reports a generic "native terminal/verification unconfirmed"
(err 62) when a stage fails, which is enough to know SOMETHING failed and not enough to
know WHAT. The journal it already writes contains the native component result for each
stage - error code, detail, and the FSM trace such as ["PICK_A:OK", "PLACE_A:FAIL"].

Without this the classifier correctly answers UNKNOWN and the runner declines to act,
which is safe but useless. With it, a place failure can be attributed to the place
skill instead of a shrug. This module only READS archived logs; it changes no grading.
"""
import json
from pathlib import Path


def _read(path):
    p = Path(path)
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def latest_journal(run_dir):
    d = Path(run_dir) / "sim" / "skills" / "composites"
    if not d.is_dir():
        return None
    files = sorted(d.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def stage_failures(run_dir):
    """Return a list of native stage results that did not succeed."""
    journal = latest_journal(run_dir)
    if journal is None:
        return []
    out = []
    for row in _read(journal):
        if row.get("event") != "NATIVE_TERMINAL":
            continue
        comp = row.get("component") or {}
        final = comp.get("final_state") or {}
        out.append({
            "stage_id": row.get("stage_id") or comp.get("stage_id"),
            "outcome": comp.get("outcome"),
            "error_code": comp.get("error_code"),
            "detail": (comp.get("detail") or "")[:300],
            "fsm_trace": final.get("fsm_trace") or [],
            "object_at_place": final.get("object_at_place"),
            "final_position_error_m": final.get("final_position_error_m"),
        })
    return out


def failure_trace(run_dir):
    """First failing stage trace, or None."""
    for st in stage_failures(run_dir):
        if st.get("outcome") in (1, "1") or st.get("fsm_trace"):
            trace = st.get("fsm_trace") or []
            if any("FAIL" in step for step in trace):
                return st
    return None


def enrich(evidence, run_dir):
    """Add native diagnostics to a composite-level evidence dict. Never mutates input."""
    out = dict(evidence)
    st = failure_trace(run_dir)
    if st is None:
        return out
    out["native_detail"] = st.get("detail")
    out["native_fsm_trace"] = st.get("fsm_trace")
    out["native_error_code"] = st.get("error_code")
    out["failed_stage"] = st.get("stage_id")
    return out
