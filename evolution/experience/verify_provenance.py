#!/usr/bin/env python3
"""Verify an experience record evidence against its cited source_run, mechanically.

WHY THIS FILE EXISTS
    seed_from_evidence.py line 26 checked only that the source DIRECTORY existed and never opened it.
    So a record whose evidence existed only in a README, or described a run that had already been fixed
    and re-archived, was accepted and marked validated. An independent review of the four stored records
    found 3 of 4 cite evidence their own cited source cannot contain - the archive holds the POST-FIX run
    while the evidence describes the PRE-FIX failure.

    This module is the check that was missing. It refuses a record unless every string in its evidence
    appears in a MACHINE-READABLE file under source_run. A README is excluded on purpose: prose that
    narrates a run is a claim about a measurement, not a measurement.

WHY IT IS FAIL-CLOSED
    A missing value, an unreadable file, or a missing source all REJECT. The whole point is that silence
    must not be read as success - that is exactly how the previous version passed three bad records.
"""
import os

# Prose is not evidence. A narration of a measurement is a claim about it.
PROSE_SUFFIXES = ('.md', '.markdown', '.rst', '.txt')
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


def evidence_strings(evidence):
    """Every string a record asserts. Numbers are skipped: '0.0175' collides across files."""
    out = []
    for key in sorted(evidence or {}):
        value = evidence[key]
        if isinstance(value, str) and len(value.strip()) >= 8:
            out.append((key, value.strip()))
    return out


def verify_provenance(source_root, evidence):
    """Return (ok, files, reason). ok requires EVERY evidence string to be found in a non-prose file."""
    if not os.path.isdir(source_root):
        return False, [], 'cited source_run does not exist: %s' % source_root
    needles = evidence_strings(evidence)
    if not needles:
        return False, [], ('evidence contains no verifiable string (only numbers, or too short); '
                           'nothing here can be checked, so it is refused')
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
    missing = [key for key, _ in needles if key not in hits]
    if missing:
        return False, sorted(hits.values()), (
            'evidence not found in any machine-readable file under source_run: %s'
            % ', '.join(missing))
    return True, sorted(set(hits.values())), 'all %d evidence string(s) located' % len(needles)


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
