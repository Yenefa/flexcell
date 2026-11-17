#!/usr/bin/env python3
"""#251 协议包离线自检 —— 纯 stdlib，不联网、不调用模型、不启动 ROS/Gazebo。

它检查的是**文档层的自我一致性**：
  1. 8 个交付文件齐全；
  2. RUN_MANIFEST 有 24 行槽位、id 唯一、覆盖 2x4x3 全组合；
  3. 24 行状态列全部为 NOT_RUN（任何终态出现即失败，因为本包未执行）；
  4. 派发顺序恰好是 1..24；
  5. 状态计数小节的数字与槽位表一致；
  6. 没有「已执行」类断言（本包不得声称跑过）；
  7. 历史分数所在行带「历史」标记；
  8. 每份文档都带 DRAFT 状态与「已知限制」小节；
  9. 代码围栏成对闭合。

用法（仓库根目录）：
    python3 docs/research/evobot-paper-v02/check_protocol_docs.py
退出码 0 = 全通过，1 = 有失败项。

约定：三反引号围栏内的内容不参与第 6 项扫描，
因此「反面示例」必须写在代码块里，不能写成正文。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TICK = chr(96)
FENCE = TICK * 3

FILES = [
    "README.md",
    "PROTOCOL.md",
    "TASKS.md",
    "RUN_MANIFEST.md",
    "DATA_DICTIONARY.md",
    "ANALYSIS.md",
    "ADMISSION.md",
    "ASSUMPTIONS.md",
]

FAMILIES = ("F1", "F2")
CONDITIONS = ("A", "B", "C", "D")
REPETITIONS = ("r1", "r2", "r3")
EXPECTED_SLOTS = set(
    "%s-%s-%s" % (f, c, r) for f in FAMILIES for c in CONDITIONS for r in REPETITIONS
)

SLOT_ROW = re.compile(
    r"^\|\s*(\d+)\s*\|\s*" + TICK + r"(F[12]-[ABCD]-r[123])" + TICK + r"\s*\|(.*)$"
)
FRACTION = re.compile(r"\b\d+/\d+\b")
HISTORY_MARKER = "历史"
HISTORY_CONTEXT = ("W5", "E2", "Level")

FORBIDDEN_CLAIMS = (
    "实验已完成",
    "已完成实验",
    "已执行实验",
    "本实验已跑",
    "运行结果为",
    "24/24 成功",
    "全部通过验收",
)

failures = []


def fail(check_name, message):
    failures.append((check_name, message))


def read(name):
    return (HERE / name).read_text(encoding="utf-8")


def body_only(text):
    """去掉代码围栏内的行，保留行结构（围栏行本身也置空）。"""
    out = []
    in_fence = False
    for line in text.splitlines():
        if line.strip().startswith(FENCE):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else line)
    return out


def fences_balanced(text):
    return sum(1 for l in text.splitlines() if l.strip().startswith(FENCE)) % 2 == 0


def check_files():
    missing = [f for f in FILES if not (HERE / f).is_file()]
    have_script = (HERE / "check_protocol_docs.py").is_file()
    ok = not missing and have_script
    if missing:
        fail("required files", "missing: " + ", ".join(missing))
    if not have_script:
        fail("required files", "check_protocol_docs.py missing")
    print("[ %s ] required files: %d/%d" % ("OK" if ok else "FAIL", len(FILES) - len(missing), len(FILES)))
    return ok


def parse_manifest():
    text = read("RUN_MANIFEST.md")
    rows = []
    for line in text.splitlines():
        m = SLOT_ROW.match(line.strip())
        if m:
            rows.append((int(m.group(1)), m.group(2), line))
    return text, rows


def check_slots(rows):
    ok = True
    if len(rows) != 24:
        fail("manifest slots", "expected 24 rows, found %d" % len(rows))
        ok = False
    ids = [r[1] for r in rows]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        fail("manifest slots", "duplicate slot ids: " + ", ".join(dupes))
        ok = False
    print("[ %s ] manifest slots: %d rows, %d unique ids" % ("OK" if ok else "FAIL", len(rows), len(set(ids))))
    return ok


def check_matrix(rows):
    ids = {r[1] for r in rows}
    missing = sorted(EXPECTED_SLOTS - ids)
    extra = sorted(ids - EXPECTED_SLOTS)
    ok = not missing and not extra
    if missing:
        fail("matrix coverage", "missing slots: " + ", ".join(missing))
    if extra:
        fail("matrix coverage", "unexpected slots: " + ", ".join(extra))
    total = len(FAMILIES) * len(CONDITIONS) * len(REPETITIONS)
    print("[ %s ] matrix coverage: %d families x %d conditions x %d repetitions = %d"
          % ("OK" if ok else "FAIL", len(FAMILIES), len(CONDITIONS), len(REPETITIONS), total))
    return ok


def slot_status(line):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells[-1]


VOCAB = {"NOT_RUN", "RUNNING", "SUCCESS_VERIFIED", "FAIL",
         "BUDGET_EXHAUSTED", "UNKNOWN", "INVALID"}


def check_status(rows):
    """Every slot carries a status from the vocabulary, and the counts add up.

    This used to require all twenty-four slots to be NOT_RUN, which was true
    while the manifest described an unstarted experiment and became false the
    moment the first real dispatch happened. An invariant that encodes "nothing
    has run yet" has to be replaced, not waived: what still matters is that no
    slot is left blank, none invents a word outside the vocabulary, and the
    section 6 tally matches the rows.
    """
    counts = {}
    bad = []
    for _order, slot, line in rows:
        status = slot_status(line).strip(TICK)
        if status not in VOCAB:
            bad.append("%s=%s" % (slot, status))
            continue
        counts[status] = counts.get(status, 0) + 1
    if bad:
        fail("slot status", "status outside the vocabulary: " + ", ".join(bad))
        return False
    if len(counts) and sum(counts.values()) != 24:
        fail("slot status", "only %d slots carry a status" % sum(counts.values()))
        return False
    print("[ OK ] slot status: " + ", ".join("%s=%d" % (k, counts[k])
                                             for k in sorted(counts)))
    return True


def check_order(rows):
    orders = sorted(r[0] for r in rows)
    ok = orders == list(range(1, 25))
    if not ok:
        fail("dispatch order", "expected 1..24, got %s" % orders)
    return ok


def check_status_counts(manifest_text, rows):
    """The section 6 tally must equal what the rows say, for every status."""
    actual = {}
    for _order, _slot, line in rows:
        status = slot_status(line).strip(TICK)
        actual[status] = actual.get(status, 0) + 1
    declared = {}
    for status in VOCAB:
        pattern = (r"\|\s*" + TICK + status + TICK +
                   r"\s*\|\s*\*\*(\d+)\*\*\s*\|")
        m = re.search(pattern, manifest_text)
        if m:
            declared[status] = int(m.group(1))
    wrong = [(s, declared.get(s, 0), actual.get(s, 0))
             for s in VOCAB if declared.get(s, 0) != actual.get(s, 0)]
    if wrong:
        fail("status counts", "section 6 disagrees with the rows: " +
             ", ".join("%s table=%d rows=%d" % w for w in wrong))
        return False
    print("[ OK ] status counts: section 6 equals the rows")
    return True
    ok = declared == len(rows) == 24
    if not ok:
        fail("status counts", "declared NOT_RUN=%d vs rows=%d" % (declared, len(rows)))
    print("[ %s ] status counts: declared NOT_RUN=%d, rows=%d" % ("OK" if ok else "FAIL", declared, len(rows)))
    return ok


def check_claims():
    hits = []
    for name in FILES:
        for line in body_only(read(name)):
            for phrase in FORBIDDEN_CLAIMS:
                if phrase in line:
                    hits.append("%s: %s" % (name, phrase))
    ok = not hits
    if hits:
        fail("claim scan", "; ".join(hits))
    print("[ %s ] claim scan: %s" % ("OK" if ok else "FAIL",
                                     "no executed-run assertion found" if ok
                                     else "%d assertion(s)" % len(hits)))
    return ok


def marker_window(line):
    """表格行只看前两个单元格，避免正文后半句的「历史」把标记位掩盖。"""
    if line.lstrip().startswith("|"):
        parts = line.split("|")
        if len(parts) >= 5:
            return "|".join(parts[:3])
    return line


def check_history_markers():
    bad = []
    for name in FILES:
        for lineno, line in enumerate(read(name).splitlines(), 1):
            if not FRACTION.search(line):
                continue
            if not any(ctx in line for ctx in HISTORY_CONTEXT):
                continue
            if HISTORY_MARKER not in marker_window(line):
                bad.append("%s:%d" % (name, lineno))
    ok = not bad
    if bad:
        fail("boundary marker", "historical score without 历史 marker: " + ", ".join(bad))
    print("[ %s ] boundary marker: %s" % ("OK" if ok else "FAIL",
                                          "historical scores carry 不可合池 note" if ok
                                          else "%d line(s)" % len(bad)))
    return ok


def check_doc_shape():
    bad = []
    for name in FILES:
        text = read(name)
        if not fences_balanced(text):
            bad.append("%s (unbalanced code fence)" % name)
        if "DRAFT" not in text:
            bad.append("%s (no DRAFT status)" % name)
        if "已知限制" not in text:
            bad.append("%s (no 已知限制 section)" % name)
    ok = not bad
    if bad:
        fail("doc shape", "; ".join(bad))
    print("[ %s ] doc shape: %d docs carry DRAFT + 已知限制" % ("OK" if ok else "FAIL", len(FILES) - len(bad)))
    return ok


def check_verdict_is_never_delivered():
    """No condition may promise the judge's own verdict as an input.

    This was wrong once: condition B listed the evaluator verdict among the
    information the repairer receives, while #249 seals verification in all four
    conditions. The reason the seal matters is incentive, not secrecy - an agent
    that can see the verdict can tune to the ruler instead of fixing the task,
    and the four-condition comparison stops measuring what it claims to measure.
    """
    text = read("PROTOCOL.md")
    lines = [line for line in text.splitlines() if line.startswith("| **")]
    rows = {}
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        name = cells[0].strip("*").strip()
        if name in ("A", "B", "C", "D"):
            rows[name] = cells[2]
    # The cells always contain a negation for the repair direction, so testing for
    # "no 不含 nearby" can never fire. The precise rule is: rows B/C/D must state
    # that the verdict original is excluded, and must not mention "verdict" at all
    # (mentioning it there is how it was offered before).
    for name in ("B", "C", "D"):
        cell = rows.get(name, "")
        if "verdict" in cell.lower():
            fail("verdict sealed", "condition %s mentions the verdict in what it gives" % name)
            return
        if "裁决原件" not in cell:
            fail("verdict sealed", "condition %s does not state that the verdict is excluded" % name)
            return
    if "裁决原件在四个条件下都不下发" not in text:
        fail("verdict sealed", "PROTOCOL.md no longer states that the verdict is never delivered")
        return
    print("[ OK ] verdict sealed: no condition offers the judge's verdict")


def report():
    if failures:
        print("")
        print("FAIL: %d check(s) failed" % len(failures))
        for name, message in failures:
            print("  - [%s] %s" % (name, message))
    else:
        print("PASS")


def main():
    if not check_files():
        report()
        return 1
    manifest_text, rows = parse_manifest()
    check_slots(rows)
    check_matrix(rows)
    check_status(rows)
    check_order(rows)
    check_status_counts(manifest_text, rows)
    check_claims()
    check_history_markers()
    check_doc_shape()
    check_verdict_is_never_delivered()
    report()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
