#!/usr/bin/env python3
# A path inside an entry body must not depend on the OS that wrote it.
# WHY: os.path.relpath returns backslashes on Windows and forward slashes on POSIX. Those
# strings land in source_run / evidence_files, and entry_id is a digest of the body — so the
# SAME archive produced DIFFERENT entry ids on Windows and Linux. The committed artifacts
# matched a local run and failed CI's freshness check with 17 churned ids, for weeks, because
# the local check could never reproduce it.
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import postmortem  # noqa: E402


def test_rel_never_emits_a_backslash():
    got = postmortem._rel(os.path.join(WT, "setup", "acceptance", "x.json"), WT)
    assert chr(92) not in got, got
    assert got == "setup/acceptance/x.json"


def test_the_old_relpath_would_differ_on_windows():
    """The defect, pinned: this is what the entry body used to carry."""
    old = os.path.relpath(os.path.join(WT, "setup", "acceptance", "x.json"), WT)
    if os.sep == chr(92):
        assert chr(92) in old, "on Windows relpath must show the backslash we replaced"


def test_no_committed_entry_carries_a_backslash_path():
    import json
    path = os.path.join(WT, "setup", "acceptance",
                        "evobot_continual_chain_20261118", "02_entries.json")
    with open(path, encoding="utf-8") as fh:
        entries = json.load(fh)["entries"]
    for entry in entries:
        for key in ("source_run", "evidence_files"):
            value = entry.get(key)
            texts = value if isinstance(value, list) else [value]
            for text in texts:
                if isinstance(text, str):
                    assert chr(92) not in text, (entry.get("version", {}).get("label"), text)
