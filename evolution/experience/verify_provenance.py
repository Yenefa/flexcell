#!/usr/bin/env python3
"""Verify an experience record evidence against its cited source_run, mechanically.

WHY THIS FILE EXISTS
    seed_from_evidence.py line 26 checked only that the source DIRECTORY existed and never opened it.
    So a record whose evidence existed only in a README, or described a run that had already been fixed
    and re-archived, was accepted and marked validated. An independent review of the four stored records
    found 3 of 4 cite evidence their own cited source cannot contain - the archive holds the POST-FIX run
    while the evidence describes the PRE-FIX failure.

    This module is the check that was missing. It refuses a record unless every piece of its evidence can
    be located in a MACHINE-READABLE file under source_run. A README is excluded on purpose: prose that
    narrates a run is a claim about a measurement, not a measurement.

NUMBERS ARE CHECKED STRUCTURALLY, NOT AS SUBSTRINGS
    The first version skipped every number, so `error_code: 60` was never verified against anything. A
    reviewer demonstrated the consequence: feeding it error_code 99 instead of 60 still PASSED, and
    error_code 61 vs 60 was the only thing distinguishing two records. A substring test would not fix
    that either - '60' occurs in timestamps, coordinates and port numbers. So a numeric or boolean fact
    must appear as a TYPED FIELD VALUE in a parsed JSON object, which is exact.

WHY IT IS FAIL-CLOSED
    A missing value, an unreadable file, or a missing source all REJECT. The whole point is that silence
    must not be read as success - that is exactly how the previous version passed three bad records.
"""
import json
import os

# Prose is not evidence. A narration of a measurement is a claim about it.
PROSE_SUFFIXES = ('.md', '.markdown', '.rst', '.txt')
JSON_SUFFIXES = ('.json', '.jsonl')
MAX_FILE_BYTES = 8 * 1024 * 1024


def _iter_files(root):
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            path = os.path.join(dirpath, name)
            if path.lower().endswith(PROSE_SUFFIXES):
                continue
            try:
                if os.path.getsize(path) > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            yield path


def _json_objects(path):
    """Every dict a JSON or JSONL file contains. Yields nothing if it will not parse."""
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as fh:
            text = fh.read()
    except OSError:
        return
    if path.lower().endswith('.jsonl'):
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict):
                yield obj
        return
    try:
        obj = json.loads(text)
    except ValueError:
        return
    if isinstance(obj, dict):
        yield obj
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                yield item


def evidence_strings(evidence):
    """String facts. Numbers are NOT skipped any more - see evidence_scalars."""
    out = []
    for key in sorted(evidence or {}):
        value = evidence[key]
        if isinstance(value, str) and len(value.strip()) >= 8:
            out.append((key, value.strip()))
    return out


def evidence_scalars(evidence):
    """Numeric and boolean facts, which must match a typed JSON field value exactly."""
    out = []
    for key in sorted(evidence or {}):
        value = evidence[key]
        if isinstance(value, bool) or isinstance(value, (int, float)):
            out.append((key, value))
    return out


def verify_provenance(source_root, evidence):
    """Return (ok, files, reason). EVERY fact must be located in a non-prose file under source_root."""
    if not os.path.isdir(source_root):
        return False, [], 'cited source_run does not exist: %s' % source_root
    needles = evidence_strings(evidence)
    scalars = evidence_scalars(evidence)
    if not needles and not scalars:
        return False, [], ('evidence contains nothing checkable (no string >= 8 chars, no number); '
                           'nothing here can be verified, so it is refused')
    hits = {}
    for path in _iter_files(source_root):
        try:
            with open(path, 'rb') as fh:
                blob = fh.read()
        except OSError:
            continue
        for key, needle in needles:
            if key in hits:
                continue
            if needle.encode('utf-8') in blob:
                hits[key] = path

    # Numeric and boolean facts are checked against PARSED JSON, never as substrings: '60' occurs in
    # timestamps and coordinates, so a substring test would accept a wrong error code.
    missing_scalars = [k for k, _v in scalars]
    if missing_scalars and any(p.lower().endswith(JSON_SUFFIXES) for p in _iter_files(source_root)):
        for path in _iter_files(source_root):
            if not path.lower().endswith(JSON_SUFFIXES):
                continue
            if not missing_scalars:
                break
            for obj in _json_objects(path) or []:
                for key, value in list(scalars):
                    if key in missing_scalars and _matches(obj.get(key), value):
                        hits[key] = path
                        missing_scalars.remove(key)

    missing = [key for key, _ in needles if key not in hits] + missing_scalars
    if missing:
        return False, sorted(set(hits.values())), (
            'evidence not found in any machine-readable artifact under source_run: %s'
            % ', '.join(sorted(set(missing))))
    return True, sorted(set(hits.values())), 'all %d evidence fact(s) located' % (len(needles) + len(scalars))


def _matches(found, claimed):
    """Exact typed match. Booleans must not be mistaken for integers."""
    if isinstance(claimed, bool) or isinstance(found, bool):
        return found is claimed
    try:
        return found == claimed
    except Exception:
        return False


def check_actionability(lesson, repo_root):
    """Refuse lessons the planner cannot act on. Reuses the existing classifier, not a new one."""
    import sys
    sys.path.insert(0, os.path.join(repo_root, 'evolution', 'transfer'))
    try:
        import audit_actionability as aa
    except Exception as exc:
        return False, 'actionability classifier unavailable: %s' % exc
    label, why = aa.classify_actionability(lesson or '')
    if label != 'PLANNER_ACTIONABLE':
        return False, '%s - %s' % (label, why)
    return True, 'PLANNER_ACTIONABLE'
