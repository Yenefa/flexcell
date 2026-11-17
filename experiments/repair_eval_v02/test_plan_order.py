"""The executor must dispatch in the order the manifest registers.

MEASURED 2026-11-17 (review): the executor generated family -> condition -> rep,
so the first six slots were F1-A-r1/r2/r3, F1-B-r1/r2/r3, while the manifest
registers an interleaved order. #251 and #252 both require the registered order.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import run_matrix_real as R  # noqa: E402

BT = chr(96)
FAM = list(R.FAMILIES)
CON = ["A_STATIC", "B_REAL_FEEDBACK"]


def test_without_a_plan_the_order_is_the_natural_one():
    order = R.plan_order("", FAM, CON, [1, 2])
    assert order[0] == (FAM[0], "A_STATIC", 1)
    assert len(order) == 8


def test_a_plan_reorders_the_dispatch(tmp_path):
    manifest = tmp_path / "RUN_MANIFEST.md"
    rows = ["F1-A-r1", "F2-A-r1", "F1-B-r1", "F2-B-r1"]
    manifest.write_text(
        "".join("| %d | %s%s%s |\n" % (i + 1, BT, slot, BT)
                for i, slot in enumerate(rows)), encoding="utf-8")
    order = R.plan_order(str(manifest), FAM, CON, [1])
    assert order == [
        (FAM[0], "A_STATIC", 1),
        (FAM[1], "A_STATIC", 1),
        (FAM[0], "B_REAL_FEEDBACK", 1),
        (FAM[1], "B_REAL_FEEDBACK", 1),
    ], order


def test_the_shipped_manifest_order_differs_from_the_natural_order():
    shipped = Path("/home/ros/wt/protocol/docs/research/evobot-paper-v02/RUN_MANIFEST.md")
    if not shipped.exists():
        import pytest
        pytest.skip("manifest not present in this checkout")
    all_conditions = [c for c in R.CONDITIONS]
    planned = R.plan_order(str(shipped), FAM, all_conditions, [1, 2, 3])
    natural = R.plan_order("", FAM, all_conditions, [1, 2, 3])
    assert len(planned) == 24
    assert planned[:6] != natural[:6], (
        "the shipped manifest starts in the same order the loops produce, so the "
        "test cannot tell a plan-driven dispatch from the old one")
    assert planned[0] != planned[1], "the plan interleaves families"
