"""Paper counts, source identities and historical recomputation must fail loudly."""
import importlib.util
import json
from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "docs/research/evobot-paper-v02/tools"


def module(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_current_paper_claims_match_raw_records():
    assert not module("check_paper_evidence").check()


@pytest.mark.parametrize("old,new", [
    ("35/48", "31/48"), ("28 UNKNOWN", "48 UNKNOWN"),
    ("31541278f2a3abea2d89b69eb48f7e84859e2ae2", "11c056c5"),
])
def test_claim_count_or_source_mutation_is_detected(tmp_path, old, new):
    checker = module("check_paper_evidence")
    path = tmp_path / "claims.md"
    path.write_text(checker.CLAIMS.read_text().replace(old, new))
    assert checker.check(path)


def history(tmp_path, name):
    source = ROOT / "experiments/pilot-001/runs" / name
    destination = tmp_path / name
    shutil.copytree(source, destination)
    return destination


def test_historical_arm_results_are_not_copied_from_aggregate(tmp_path):
    tool = module("recompute_w5_archive")
    root = history(tmp_path, "p1.5-w5-20261109")
    path = root / "w5a/result.json"
    raw = json.loads(path.read_text())
    raw["success"] = False
    path.write_text(json.dumps(raw))
    report = tool.recompute(root, "arm_dirs", 2, "test")
    assert report["computed"]["success"] == 0
    assert report["disagreements"]


@pytest.mark.parametrize("mutation", ("missing_aggregate", "changed_cost"))
def test_missing_summary_or_changed_profiles_are_not_silent_success(tmp_path, mutation):
    tool = module("recompute_w5_archive")
    root = history(tmp_path, "p1.5-w5e2b-20261109")
    if mutation == "missing_aggregate":
        (root / "aggregate.json").unlink()
    else:
        path = root / "rep1/result.json"
        raw = json.loads(path.read_text())
        raw["iterations"], raw["cost"]["tokens"] = 999, 999999
        path.write_text(json.dumps(raw))
    assert tool.recompute(root, "rep_dirs", 3, "test")["disagreements"]
