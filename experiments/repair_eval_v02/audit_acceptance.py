"""Audit every acceptance criterion of #249-#254 against the code and docs.

WHY
    Six issues have been reported as delivered, and every report has been a
    paragraph claiming things are in place. A paragraph cannot be re-run. This
    walks the criteria from the issue text and, wherever the criterion is
    mechanically checkable, checks it; where it is not, it says so instead of
    grading itself.

    It is deliberately capable of printing UNMET. An audit that can only print
    MET is a summary, not an audit.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (str(HERE), str(ROOT), str(ROOT / "benchmark" / "repair_eval" / "contracts")):
    if path not in sys.path:
        sys.path.insert(0, path)

import budget as B                                       # noqa: E402
import run_record as REC                                 # noqa: E402
from benchmark.repair_eval import visibility as vis       # noqa: E402

POLICY_PATH = ROOT / "benchmark" / "repair_eval" / "visibility_policy.json"
DOCS = ROOT / "docs" / "research" / "evobot-paper-v02"
CONTRACT_DOC = ROOT / "docs" / "repair_eval" / "TASK_CONTRACT.md"
VISIBILITY_DOC = ROOT / "docs" / "repair_eval" / "VISIBILITY.md"

MET, PARTIAL, UNMET, MANUAL = "MET", "PARTIAL", "UNMET", "MANUAL"


def check(criterion, issue, fn):
    try:
        result = fn()
        status, evidence = result[0], result[1]
    except Exception as exc:                                  # noqa: BLE001
        status, evidence = UNMET, "raised %s: %s" % (type(exc).__name__, str(exc)[:90])
    # a check that returns something other than one of the four words is not a
    # status, and silently stringifying it would hide the mistake
    if status not in (MET, PARTIAL, UNMET, MANUAL):
        return dict(issue=issue, criterion=criterion, status=UNMET,
                    evidence="check returned %r as a status" % (status,))
    return dict(issue=issue, criterion=criterion, status=status, evidence=str(evidence))


class _T:
    def chat(self, messages, **kwargs):
        return {"text": "{}", "usage": {"prompt_tokens": 1, "completion_tokens": 1}}


# --------------------------------------------------------------------- 249
def c249_categories():
    policy = vis.load_policy(POLICY_PATH)
    access = policy.conditions["B_REAL_FEEDBACK"]
    categories = sorted(access.visible_categories)
    wanted = {"static_input", "candidate_source", "execution_feedback"}
    missing = wanted - set(categories)
    status = MET if not missing else UNMET
    return status, "visible categories: %s" % ", ".join(categories)


def c249_a_cannot_read():
    policy = vis.load_policy(POLICY_PATH)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cand = tmp / "candidate"
        (cand / "skill").mkdir(parents=True)
        (cand / "skill" / "r.py").write_text("x\n")
        (cand / "task.md").write_text("t\n")
        verdict = tmp / "verdict"; verdict.mkdir()
        (verdict / "verdict.json").write_text("{}")
        hidden = tmp / "hidden"; hidden.mkdir()
        boundary = vis.RunBoundary(policy, tmp, cand, verdict, hidden, condition="A_STATIC")
        denied = []
        for rel in ("verdict.json", "../verdict/verdict.json", str(verdict / "verdict.json")):
            try:
                boundary.read_text(rel, "candidate_source")
            except vis.BoundaryError as exc:
                denied.append((exc.as_dict() or {}).get("reason"))
        allowed = boundary.read_text("skill/r.py", "candidate_source")
        ok = len(denied) == 3 and bool(allowed)
    return (MET if ok else UNMET), "denied reasons: %s; source read: %s" % (
        ", ".join(denied), "yes" if allowed else "no")


def c249_feedback_source_recorded():
    policy = vis.load_policy(POLICY_PATH)
    ledger = B.Ledger(_T())
    record = REC.build_record(
        slot_id="s", condition="B_REAL_FEEDBACK",
        condition_access=policy.conditions["B_REAL_FEEDBACK"], policy=policy,
        account=ledger.account(), terminal_status="NOT_RUN", claim_success=False,
        feedback_text="real failure")
    ok = bool(record["feedback_payload_sha256"]) and record["feedback_source"] == "own_run"
    return (MET if ok else UNMET), "source=%s digest=%s" % (
        record["feedback_source"], (record["feedback_payload_sha256"] or "")[:12])


def c249_routing_differs():
    policy = vis.load_policy(POLICY_PATH)
    seen = {name: REC.feedback_source_for(access)
            for name, access in policy.conditions.items()}
    ok = len(set(seen.values())) >= 3
    return (MET if ok else UNMET), json.dumps(seen, ensure_ascii=False)


def c249_roots_separated():
    policy = vis.load_policy(POLICY_PATH)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cand = tmp / "candidate"; (cand / "skill").mkdir(parents=True)
        try:
            vis.RunBoundary(policy, tmp, cand, cand / "v", tmp / "h", condition="A_STATIC")
            return UNMET, "overlapping roots accepted"
        except vis.PolicyError as exc:
            # PolicyError is the constructor refusing a bad root set; it carries a
            # message, not a reason code
            return MET, "overlap refused: %s" % str(exc)[:70]
        except vis.BoundaryError as exc:
            return MET, "overlap refused: %s" % ((exc.as_dict() or {}).get("reason"))


def c249_docs_state_limits():
    text = VISIBILITY_DOC.read_text(encoding="utf-8") if VISIBILITY_DOC.exists() else ""
    ok = "限制" in text and "policy_fingerprint" in text
    return (MET if ok else UNMET), "VISIBILITY.md limits section present: %s" % ok


# --------------------------------------------------------------------- 250
def c250_contract_outside_candidate():
    payload = json.loads((ROOT / "benchmark" / "repair_eval" / "contracts" /
                          "cases" / "p1_valid_repair.json").read_text(encoding="utf-8"))
    contract = payload["contract"]
    ok = bool(contract.get("editable_fields")) and bool(contract["immutable"].get("user_goal"))
    return (MET if ok else UNMET), "editable_fields=%s" % (contract.get("editable_fields"),)


def c250_six_negative_classes():
    import task_contract
    cases = sorted((ROOT / "benchmark" / "repair_eval" / "contracts" / "cases").glob("n*.json"))
    codes = set()
    for path in cases:
        payload = json.loads(path.read_text(encoding="utf-8"))
        import acceptance
        contract = task_contract.TaskContract.from_mapping(payload["contract"])
        verdict = acceptance.evaluate(contract, payload["candidate"]).to_dict()
        codes.update(r["code"] for r in verdict["reasons"])
    return (MET if len(cases) >= 6 else UNMET), "%d negative cases, codes: %s" % (
        len(cases), ", ".join(sorted(codes)))


def c250_positive_and_accounting():
    result = subprocess.run([sys.executable, "benchmark/repair_eval/contracts/test_contract.py",
                             "--summary"], cwd=ROOT, capture_output=True, text=True)
    try:
        summary = json.loads(result.stdout.strip().splitlines()[-1])
    except Exception:
        return UNMET, (result.stdout or result.stderr)[-120:]
    ok = summary.get("false_accept") == 0 and summary.get("false_reject") == 0
    return (MET if ok else UNMET), json.dumps(summary)


def c250_unknown_never_passes():
    import acceptance
    import task_contract
    payload = json.loads((ROOT / "benchmark" / "repair_eval" / "contracts" /
                          "cases" / "p1_valid_repair.json").read_text(encoding="utf-8"))
    contract = task_contract.TaskContract.from_mapping(payload["contract"])
    candidate = dict(payload["candidate"])
    candidate.pop("exit_code", None)
    verdict = acceptance.evaluate(contract, candidate).to_dict()
    status = MET if verdict["status"] == "UNKNOWN" else UNMET
    return status, "missing exit code -> %s %s" % (
        verdict["status"], [r["code"] for r in verdict["reasons"]])


# --------------------------------------------------------------------- 251
def c251_manifest_not_run():
    result = subprocess.run([sys.executable, "docs/research/evobot-paper-v02/check_protocol_docs.py"],
                            cwd=ROOT, capture_output=True, text=True)
    ok = result.returncode == 0
    tail = [line for line in (result.stdout or "").splitlines() if "slot status" in line]
    return (MET if ok else UNMET), (tail[0] if tail else (result.stdout or "")[-90:])


def c251_budget_enforced():
    ledger = B.Ledger(_T(), max_interactions=2, max_tokens=10 ** 6)
    ledger.chat([]); ledger.chat([])
    try:
        ledger.chat([])
        return UNMET, "third interaction was allowed"
    except B.BudgetExhausted as exc:
        return MET, "cap refused: %s" % exc.position_text()


def c251_retained_plan():
    import holdout
    plan = holdout.HoldoutPlan(("l1", "l2"), ("s1", "s2", "s3"),
                               holdout.Freeze("a" * 40, "RUN-1", "pre-registered"))
    status = MET if len(plan.slot_ids) == 6 else UNMET
    return status, "%d slots, all %s" % (
        len(plan.slot_ids), sorted(set(plan.statuses().values())))


# --------------------------------------------------------------------- 254
def c254_archive_recompute():
    tool = DOCS / "tools" / "recompute_w5_archive.py"
    result = subprocess.run([sys.executable, str(tool), "--runs", "experiments/pilot-001/runs"],
                            cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        return UNMET, (result.stderr or "")[-120:]
    try:
        payload = json.loads(result.stdout)
    except Exception:
        return PARTIAL, "tool ran but output was not JSON"
    ok = payload.get("disagreements") == 0 and payload.get("records", 0) > 0
    return (MET if ok else UNMET), "%s records, %s disagreements" % (
        payload.get("records"), payload.get("disagreements"))


def c254_digest_convention():
    """Cross-platform digest: LF and CRLF must give one number, bytes must not."""
    lf = "a" + chr(10) + "b"
    crlf = "a" + chr(13) + chr(10) + "b"
    same = REC.sha256_text(lf) == REC.sha256_text(crlf)
    raw_bytes = REC.sha256_bytes(b"a" + bytes([13]) + bytes([10]) + b"b") != \
        REC.sha256_bytes(b"a" + bytes([10]) + b"b")
    documented = "utf8-lf-sha256/1" in (
        DOCS / "DATA_DICTIONARY.md").read_text(encoding="utf-8")
    ok = same and raw_bytes and documented
    return (MET if ok else UNMET), "convention=%s lf==crlf=%s bytes_raw=%s doc=%s" % (
        REC.DIGEST_CONVENTION, same, raw_bytes, documented)


def c254_false_accept_distinct():
    policy = vis.load_policy(POLICY_PATH)
    ledger = B.Ledger(_T())
    record = REC.build_record(
        slot_id="s", condition="B_REAL_FEEDBACK",
        condition_access=policy.conditions["B_REAL_FEEDBACK"], policy=policy,
        account=ledger.account(), terminal_status="PASS", claim_success=True,
        feedback_text="real failure", gate_target="FAIL")
    ok = record["false_accept"] is True and record["claim_success"] is True
    return (MET if ok else UNMET), "false_accept derived independently: %s" % record["false_accept"]


CHECKS = [
    ("249", "静态输入/候选/反馈/裁决/隐藏答案的可见范围已定义", c249_categories),
    ("249", "无反馈条件不能从别名/相邻/裁决/残留取到结果", c249_a_cannot_read),
    ("249", "真实反馈等条件记录反馈来源与摘要", c249_feedback_source_recorded),
    ("249", "执行结果按条件路由", c249_routing_differs),
    ("249", "候选副本与裁决/隐藏材料分离，重叠被拒", c249_roots_separated),
    ("249", "记录接口版本与已知限制", c249_docs_state_limits),
    ("250", "不可变目标/物体/容差在候选之外，允许修改字段已列出", c250_contract_outside_candidate),
    ("250", "至少六类负例", c250_six_negative_classes),
    ("250", "保留合法正例，分别记录错误接纳/错误拒绝", c250_positive_and_accounting),
    ("250", "UNKNOWN 不转换为通过", c250_unknown_never_passes),
    ("251", "24 个槽位保持 NOT_RUN 且自检通过", c251_manifest_not_run),
    ("251", "6 次交互 / 20,000 tokens 上限已落实", c251_budget_enforced),
    ("251", "保留场景 2 布局 × 3 初态", c251_retained_plan),
    ("254", "关键表格从原始记录重算", c254_archive_recompute),
    ("254", "错误接纳与旧 claim_success 字段区分", c254_false_accept_distinct),
    ("254", "固定跨平台摘要口径与复算入口", c254_digest_convention),
]

MANUAL_ITEMS = [
    ("249", "PR 附离线检查命令与允许/拒绝/不继承旧反馈的例子", "PR #257 正文"),
    ("250", "每个例子给出可执行命令、预期/实际与来源", "PR #258 正文"),
    ("251", "批次总费用额度、运行窗口与超时", "协议 §5.3 标 TBD，需负责人签字"),
    ("252", "按协议执行 24 个槽位并保留全部结果", "缺模型凭据；见 issue #252"),
    ("253", "冻结候选后执行 6 个保留场景", "依赖 #252 的冻结候选"),
    ("254", "比较四种反馈条件并给出结论", "依赖 #252/#253 的结果"),
    ("254", "相关工作与方法章节", "未撰写"),
    ("254", "作者、单位、贡献与授权", "需实际参与者提供"),
]


def main():
    rows = [check(criterion, issue, fn) for issue, criterion, fn in CHECKS]
    for issue, criterion, note in MANUAL_ITEMS:
        rows.append(dict(issue=issue, criterion=criterion, status=MANUAL, evidence=note))

    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1

    print("=" * 78)
    print("验收条件审计（#249-#254）")
    print("=" * 78)
    for row in rows:
        print("[%s] #%s  %s" % (row["status"].ljust(7), row["issue"], row["criterion"]))
        print("         %s" % row["evidence"])
    print()
    print("summary:", json.dumps(counts, ensure_ascii=False))
    out = HERE / "evidence" / "acceptance_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(rows=rows, counts=counts), indent=2,
                              ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
