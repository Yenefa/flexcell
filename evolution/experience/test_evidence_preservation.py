#!/usr/bin/env python3
# Re-running the demo must not delete historic review artifacts whose entries no longer
# exist. "Never delete evidence" applies to stale evidence too.
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import demo_continual  # noqa: E402

EVIDENCE = os.path.join(WT, "setup", "acceptance", "evobot_continual_chain_20261118")


def test_review_artifacts_are_explicitly_listed_not_prefix_deleted():
    """A prefix-based cleanup would delete the stale auto-occupied_destination artifact,
    which is retained failure evidence with no entry in today's store."""
    assert "review_artifact_" not in demo_continual.GENERATED_PREFIXES
    for name in ("review_artifact_E1.json", "review_artifact_E2.json",
                 "review_artifact_E3.json"):
        assert name in demo_continual.GENERATED_FILES


def test_the_stale_artifact_survives_a_rerun(tmp_path):
    import shutil
    stale = "review_artifact_auto-occupied_destination.json"
    src = os.path.join(EVIDENCE, stale)
    dst = str(tmp_path)
    shutil.copy(src, os.path.join(dst, stale))
    demo_continual._clear_generated(dst)
    assert os.path.exists(os.path.join(dst, stale))
