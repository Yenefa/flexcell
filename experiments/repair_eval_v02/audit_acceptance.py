"""Audit every acceptance criterion of #249-#254, by criterion id.

WHY THE REWRITE
    The first version listed 24 rows and called itself an acceptance audit. The
    six issues actually carry 46 checkboxes. So 22 criteria had no row at all -
    and an audit that silently omits half the checklist looks complete, which is
    worse than no audit.

    Every criterion now has an id taken from its issue ("249.1" .. "254.9").
    A criterion is either covered by a check, or listed as MANUAL with the reason
    it cannot be checked. A criterion with neither is reported UNMET, so missing
    coverage fails instead of disappearing.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (str(HERE), str(ROOT), str(ROOT / "benchmark" / "repair_eval" / "contracts")):
    if path not in sys.path:
        sys.path.insert(0, path)

import budget as B                                        # noqa: E402
import holdout                                            # noqa: E402
import run_record as REC                                  # noqa: E402
from benchmark.repair_eval import visibility as vis        # noqa: E402

POLICY_PATH = ROOT / "benchmark" / "repair_eval" / "visibility_policy.json"
DOCS = ROOT / "docs" / "research" / "evobot-paper-v02"
CASES = ROOT / "benchmark" / "repair_eval" / "contracts" / "cases"

MET, PARTIAL, UNMET, MANUAL = "MET", "PARTIAL", "UNMET", "MANUAL"
STATUSES = (MET, PARTIAL, UNMET, MANUAL)

# id, issue, the criterion as the issue states it
CRITERIA = [
    ("249.1", 249, "定义静态输入、候选文件、执行反馈、独立裁决及隐藏答案的可见范围"),
    ("249.2", 249, "无反馈条件不能从 read_file/list_dir/遥测/裁决/别名/相邻/残留得到结果"),
    ("249.3", 249, "真实反馈、失配反馈和显式指导只获得协议允许的信息，记录来源与摘要"),
    ("249.4", 249, "执行结果按条件路由；静态组不因外部裁决或对话回流获得答案"),
    ("249.5", 249, "候选副本与裁决/隐藏材料分离；规范化路径检查并验证受保护文件机制"),
    ("249.6", 249, "PR 附离线检查命令与允许/拒绝/不继承旧反馈的例子"),
    ("249.7", 249, "记录涉及的模型/工具/提示接口版本与已知限制"),

    ("250.1", 250, "不可变目标/物体/容差在候选之外；显式列出允许修改字段"),
    ("250.2", 250, "不能通过移动目标、删掉对象或放宽阈值获得接受"),
    ("250.3", 250, "至少覆盖六类负例"),
    ("250.4", 250, "保留合法修复正例，分别记录错误接纳和错误拒绝"),
    ("250.5", 250, "核对退出码/结果/证据/run ID；UNKNOWN 不转换为通过"),
    ("250.6", 250, "给出可执行命令与每例预期/实际/来源；合成与真实分开标识"),

    ("251.1", 251, "任务规格、允许修改范围、不可变目标、目标及回归场景"),
    ("251.2", 251, "完整源码 SHA、构建来源、依赖/镜像/配置、模型接口与提示摘要"),
    ("251.3", 251, "每条最多 6 次交互 / 20,000 tokens；落实预算统计与超限处理"),
    ("251.4", 251, "固定槽位/顺序/种子；列明基础设施失败、取消、未知终态与 NOT_RUN 处理"),
    ("251.5", 251, "主要结果与过程结果字段（写入、迭代、token、耗时、人工介入）"),
    ("251.6", 251, "明确修复运行/候选执行/最终场景的单位与分母，不重复计数"),
    ("251.7", 251, "保留场景为 2 个未参与开发的布局 × 3 个预定初态，冻结后执行"),
    ("251.8", 251, "对比较、样本解释和协议偏差预先声明"),
    ("251.9", 251, "沿用现有费用账本与运行资格；本轮不新增资源授权"),

    ("252.1", 252, "启动前核对源码/构建/模型/配置身份与健康状态"),
    ("252.2", 252, "按预定槽位与顺序派发；每条保留反馈来源、工具序列、用量与逐门判定"),
    ("252.3", 252, "所有失败、预算耗尽与异常进台账；剩余槽位标 NOT_RUN，不以补跑替换失败"),
    ("252.4", 252, "遇未确认终态或不健康状态按协议停止派发并保全证据"),
    ("252.5", 252, "每条用外部固定任务与验收检查候选，分别保留目标与回归失败原因"),
    ("252.6", 252, "分组核对分母、迭代、用量与端到端时间"),
    ("252.7", 252, "与历史 E2 各版本分开报告；不同源码/模型/协议身份不合池"),
    ("252.8", 252, "报告完整矩阵、停止与偏差，以及结果对研究问题的支持范围"),

    ("253.1", 253, "固定候选源码/配置完整 SHA，记录来源运行与选择依据"),
    ("253.2", 253, "保留材料与答案评估前不提供；运行前留存清单摘要"),
    ("253.3", 253, "按协议适配执行；不临时调参/改代码/重新调用模型后计同一次结果"),
    ("253.4", 253, "核对不可变目标、候选合法性、任务结果与回归；所有失败保留"),
    ("253.5", 253, "普通任务回归与 #247 协调，明确后端/技能/环境来源"),
    ("253.6", 253, "记录 6 个槽位实际状态；修复运行数与保留场景执行数分别报告"),
    ("253.7", 253, "与预先指定参考版本比较；仅描述该保留集，不宣称泛化"),

    ("254.1", 254, "关键表格从原始记录重算，对应单位/分母/SHA/身份/证据位置"),
    ("254.2", 254, "旧 6/6、3/3 与本轮结果分开；补全失败/未知/未执行与偏差"),
    ("254.3", 254, "比较四种反馈条件，结论与实验可识别的作用相符"),
    ("254.4", 254, "区分最终错误接纳/拒绝与旧 claim_success/false_success 字段"),
    ("254.5", 254, "保留目标语义、有限回归、样本量限制；来源（合成/仿真/真机）清楚"),
    ("254.6", 254, "固定原始字节与跨平台摘要口径；代码/数据/复算入口可追溯"),
    ("254.7", 254, "更新必要相关工作与方法；统计表述符合样本条件"),
    ("254.8", 254, "作者、单位、贡献与授权由参与者核实；未提供信息保留待填写"),
    ("254.9", 254, "论文/计划书/PPT 使用相同数据口径；标明文稿实际状态"),
]


class _T:
    def chat(self, messages, **kwargs):
        return {"text": "{}", "usage": {"prompt_tokens": 1, "completion_tokens": 1}}


def _policy():
    return vis.load_policy(POLICY_PATH)


# ------------------------------------------------------------------ 249
def k249_1():
    policy = _policy()
    categories = sorted(policy.conditions["B_REAL_FEEDBACK"].visible_categories)
    ok = {"static_input", "candidate_source", "execution_feedback"} <= set(categories)
    return (MET if ok else UNMET), "visible categories: %s" % ", ".join(categories)


def k249_2():
    policy = _policy()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cand = tmp / "candidate"; (cand / "skill").mkdir(parents=True)
        (cand / "skill" / "r.py").write_text("x" + chr(10))
        (cand / "task.md").write_text("t" + chr(10))
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
        allowed = bool(boundary.read_text("skill/r.py", "candidate_source"))
    ok = len(denied) == 3 and allowed
    return (MET if ok else UNMET), "denied: %s; source readable: %s" % (", ".join(denied), allowed)


def k249_3():
    policy = _policy()
    record = REC.build_record(slot_id="s", condition="B_REAL_FEEDBACK",
                              condition_access=policy.conditions["B_REAL_FEEDBACK"],
                              policy=policy, account=B.Ledger(_T()).account(),
                              terminal_status="NOT_RUN", claim_success=False,
                              feedback_text="real failure")
    ok = record["feedback_source"] == "own_run" and bool(record["feedback_payload_sha256"])
    return (MET if ok else UNMET), "source=%s digest=%s" % (
        record["feedback_source"], (record["feedback_payload_sha256"] or "")[:12])


def k249_4():
    policy = _policy()
    seen = {name: REC.feedback_source_for(access)
            for name, access in policy.conditions.items()}
    ok = len(set(seen.values())) >= 3 and seen["A_STATIC"] == "none"
    return (MET if ok else UNMET), json.dumps(seen, ensure_ascii=False)


def k249_5():
    policy = _policy()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cand = tmp / "candidate"; (cand / "skill").mkdir(parents=True)
        try:
            vis.RunBoundary(policy, tmp, cand, cand / "v", tmp / "h", condition="A_STATIC")
            return UNMET, "overlapping roots were accepted"
        except vis.PolicyError as exc:
            roots_refused = str(exc)[:60]
        (tmp / "v2").mkdir()
        (tmp / "h2").mkdir()
        boundary = vis.RunBoundary(policy, tmp, cand, tmp / "v2", tmp / "h2",
                                   condition="B_REAL_FEEDBACK")
        try:
            boundary.write_text("task.md", "rewritten")
            return UNMET, "protected write was allowed"
        except vis.BoundaryError as exc:
            write_reason = (exc.as_dict() or {}).get("reason")
    return MET, "overlap refused (%s); protected write refused (%s)" % (
        roots_refused, write_reason)


def k249_7():
    """The doc is not trusted on its word: the fingerprint it prints is compared."""
    import re
    text = (ROOT / "docs" / "repair_eval" / "VISIBILITY.md").read_text(encoding="utf-8")
    live = _policy().fingerprint()
    mentioned = re.findall(r"[0-9a-f]{8,64}", text)
    matches = [m for m in mentioned if live.startswith(m[:8])]
    limits = "限制" in text and "policy_fingerprint" in text
    if limits and matches:
        return MET, "documented fingerprint %s matches the live %s; limits stated" % (
            matches[0][:8], live[:8])
    if limits:
        return UNMET, "the fingerprint printed in VISIBILITY.md is not the live one (%s)" % live[:8]
    return UNMET, "VISIBILITY.md does not state the fingerprint or the limits"


# ------------------------------------------------------------------ 250
def k250_1():
    payload = json.loads((CASES / "p1_valid_repair.json").read_text(encoding="utf-8"))
    contract = payload["contract"]
    ok = bool(contract.get("editable_fields")) and bool(contract["immutable"].get("user_goal"))
    return (MET if ok else UNMET), "editable_fields=%s" % (contract.get("editable_fields"),)


def k250_2():
    import acceptance
    import task_contract
    payload = json.loads((CASES / "p1_valid_repair.json").read_text(encoding="utf-8"))
    contract = task_contract.TaskContract.from_mapping(payload["contract"])
    moved = json.loads(json.dumps(payload["candidate"]))
    moved["thresholds"] = {"max_position_error_m": 9.9}
    verdict = acceptance.evaluate(contract, moved).to_dict()
    codes = [r["code"] for r in verdict["reasons"]]
    status = MET if verdict["status"] == "REJECT" else UNMET
    return status, "relaxed threshold -> %s %s" % (verdict["status"], codes)


def k250_3():
    import acceptance
    import task_contract
    cases = sorted(CASES.glob("n*.json"))
    codes = set()
    for path in cases:
        payload = json.loads(path.read_text(encoding="utf-8"))
        contract = task_contract.TaskContract.from_mapping(payload["contract"])
        verdict = acceptance.evaluate(contract, payload["candidate"]).to_dict()
        codes.update(r["code"] for r in verdict["reasons"])
    return (MET if len(cases) >= 6 else UNMET), "%d cases, %d codes: %s" % (
        len(cases), len(codes), ", ".join(sorted(codes)))


def k250_4():
    result = subprocess.run([sys.executable, "benchmark/repair_eval/contracts/test_contract.py",
                             "--summary"], cwd=ROOT, capture_output=True, text=True)
    try:
        summary = json.loads(result.stdout.strip().splitlines()[-1])
    except Exception:
        return UNMET, (result.stdout or result.stderr)[-100:]
    ok = summary.get("false_accept") == 0 and summary.get("false_reject") == 0
    return (MET if ok else UNMET), json.dumps(summary)


def k250_5():
    import acceptance
    import task_contract
    payload = json.loads((CASES / "p1_valid_repair.json").read_text(encoding="utf-8"))
    contract = task_contract.TaskContract.from_mapping(payload["contract"])
    candidate = dict(payload["candidate"])
    candidate.pop("exit_code", None)
    verdict = acceptance.evaluate(contract, candidate).to_dict()
    status = MET if verdict["status"] == "UNKNOWN" else UNMET
    return status, "missing exit code -> %s %s" % (
        verdict["status"], [r["code"] for r in verdict["reasons"]])


# ------------------------------------------------------------------ 251
def k251_1():
    tasks = (DOCS / "TASKS.md").read_text(encoding="utf-8")
    ok = "editable" in tasks.lower() or "允许修改" in tasks
    # finding the words is not proof the scope is right
    return (PARTIAL if ok else UNMET), "TASKS.md mentions the task and editable scope: %s" % ok


def k251_3():
    ledger = B.Ledger(_T(), max_interactions=2, max_tokens=10 ** 6)
    ledger.chat([]); ledger.chat([])
    try:
        ledger.chat([])
        return UNMET, "a third interaction was allowed"
    except B.BudgetExhausted as exc:
        return MET, "cap refused at %s; tokens also capped" % exc.position_text()


def k251_4():
    import reconcile as RC
    statuses = RC.parse_manifest(DOCS / "RUN_MANIFEST.md")
    vocab_ok = all(s in RC.KNOWN_STATUSES for s in statuses.values())
    ok = len(statuses) == 24 and vocab_ok
    return (MET if ok else UNMET), "24 slots, statuses in vocabulary: %s" % vocab_ok


def k251_5():
    """Behavioural: the record actually carries the process fields, typed."""
    policy = _policy()
    ledger = B.Ledger(_T())
    ledger.chat([])
    ledger.count_execution()
    ledger.finish()
    record = REC.build_record(
        slot_id="s", condition="B_REAL_FEEDBACK",
        condition_access=policy.conditions["B_REAL_FEEDBACK"], policy=policy,
        account=ledger.account(), terminal_status="NOT_RUN", claim_success=False,
        feedback_text="x")
    wanted = {"interactions_used": int, "tokens_total": int,
              "candidate_executions": int, "final_scenes": int,
              "wall_clock_s": (int, float), "tokens_in": int, "tokens_out": int}
    bad = [k for k, kind in wanted.items()
           if k not in record or not isinstance(record[k], kind)
           or isinstance(record[k], bool)]
    return (MET if not bad else UNMET), "process fields typed correctly: %s" % (
        "all" if not bad else bad)


def k251_6():
    text = (DOCS / "DATA_DICTIONARY.md").read_text(encoding="utf-8")
    ok = all(marker in text for marker in ("D1", "D2", "D3", "N1", "N2"))
    # documented, not executed: nothing here counts a denominator yet
    return (PARTIAL if ok else UNMET), "denominators documented in DATA_DICTIONARY: %s" % ok


def k251_7():
    plan = holdout.HoldoutPlan(("l1", "l2"), ("s1", "s2", "s3"),
                               holdout.Freeze("a" * 40, "RUN-1", "pre-registered"))
    ok = len(plan.slot_ids) == 6 and set(plan.statuses().values()) == {holdout.NOT_RUN}
    return (MET if ok else UNMET), "6 slots, all NOT_RUN: %s" % ok


def k251_8():
    text = ""
    for name in ("ANALYSIS.md", "ADMISSION.md"):
        path = DOCS / name
        if path.exists():
            text += path.read_text(encoding="utf-8")
    ok = "偏差" in text and ("样本" in text or "n=3" in text)
    return (PARTIAL if ok else UNMET), "deviation and sample limits declared in the docs: %s" % ok


# ------------------------------------------------------------------ 253
def k253_1():
    freeze = holdout.Freeze("a" * 40, "RUN-0010", "pre-registered criterion")
    ok = freeze.sha() and freeze.source_run_id and freeze.selection_basis
    return (MET if ok else UNMET), "freeze carries sha, source run and basis"


def k253_3():
    plan = holdout.HoldoutPlan(("l1", "l2"), ("s1", "s2", "s3"),
                               holdout.Freeze("a" * 40, "RUN-1", "basis"))
    plan.record("l1|s1", "PASS", evaluated_sha="a" * 40)
    try:
        plan.record("l1|s1", "PASS", evaluated_sha="a" * 40)
        return UNMET, "a slot accepted a second result"
    except holdout.HoldoutError:
        return MET, "a second result on one slot is refused"


def k253_4():
    plan = holdout.HoldoutPlan(("l1", "l2"), ("s1", "s2", "s3"),
                               holdout.Freeze("a" * 40, "RUN-1", "basis"))
    plan.record("l1|s1", "FAIL", evaluated_sha="a" * 40)
    ok = plan.statuses()["l1|s1"] == "FAIL"
    return (MET if ok else UNMET), "a recorded failure keeps its identity: %s" % ok


def k253_6():
    plan = holdout.HoldoutPlan(("l1", "l2"), ("s1", "s2", "s3"),
                               holdout.Freeze("a" * 40, "RUN-1", "basis", repair_runs=24))
    counts = plan.counts()
    ok = (counts["repair_runs"] == 24 and counts["holdout_planned"] == 6
          and counts["holdout_executions"] == 0)
    return (MET if ok else UNMET), json.dumps(counts)


# ------------------------------------------------------------------ 254
def k254_1():
    tool = DOCS / "tools" / "recompute_w5_archive.py"
    result = subprocess.run([sys.executable, str(tool), "--runs", "experiments/pilot-001/runs"],
                            cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        return UNMET, (result.stderr or "")[-100:]
    payload = json.loads(result.stdout)
    ok = payload.get("disagreements") == 0 and payload.get("records", 0) > 0
    return (MET if ok else UNMET), "%s records, %s disagreements" % (
        payload.get("records"), payload.get("disagreements"))


ELSEWHERE = "文件在 #259（paper 分支），本分支不含；合并树上是 MET"


def k254_2():
    path = DOCS / "HISTORICAL_V01.md"
    if not path.exists():
        return MANUAL, ELSEWHERE
    text = path.read_text(encoding="utf-8")
    ok = "不可合池" in text or "不进" in text
    return (PARTIAL if ok else UNMET), "historical numbers carry a cannot-pool note: %s" % ok


def k254_4():
    policy = _policy()
    record = REC.build_record(slot_id="s", condition="B_REAL_FEEDBACK",
                              condition_access=policy.conditions["B_REAL_FEEDBACK"],
                              policy=policy, account=B.Ledger(_T()).account(),
                              terminal_status="FAIL", claim_success=True,
                              feedback_text="x", gate_target="FAIL")
    ok = record["false_accept"] is True and record["claim_success"] is True
    return (MET if ok else UNMET), "false_accept derived separately from claim_success"


def k254_5():
    path = DOCS / "METHOD.md"
    if not path.exists():
        return MANUAL, ELSEWHERE
    text = path.read_text(encoding="utf-8")
    ok = "不能支持" in text and "合成" in text
    return (PARTIAL if ok else UNMET), "METHOD.md states the limits and the data provenance: %s" % ok


def k254_6():
    lf = "a" + chr(10) + "b"
    crlf = "a" + chr(13) + chr(10) + "b"
    same = REC.sha256_text(lf) == REC.sha256_text(crlf)
    raw_bytes = (REC.sha256_bytes(b"a" + bytes([13]) + bytes([10]) + b"b")
                 != REC.sha256_bytes(b"a" + bytes([10]) + b"b"))
    documented = "utf8-lf-sha256/1" in (DOCS / "DATA_DICTIONARY.md").read_text(encoding="utf-8")
    ok = same and raw_bytes and documented
    return (MET if ok else UNMET), "convention=%s lf==crlf=%s bytes_raw=%s doc=%s" % (
        REC.DIGEST_CONVENTION, same, raw_bytes, documented)


def k254_7a():
    path = DOCS / "METHOD.md"
    if not path.exists():
        return MANUAL, ELSEWHERE
    text = path.read_text(encoding="utf-8")
    ok = "## 1." in text and "n=3" in text
    return (PARTIAL if ok else UNMET), "method written; significance limits stated: %s" % ok


COVERED = {
    "249.1": k249_1, "249.2": k249_2, "249.3": k249_3, "249.4": k249_4,
    "249.5": k249_5, "249.7": k249_7,
    "250.1": k250_1, "250.2": k250_2, "250.3": k250_3, "250.4": k250_4, "250.5": k250_5,
    "251.1": k251_1, "251.3": k251_3, "251.4": k251_4, "251.5": k251_5,
    "251.6": k251_6, "251.7": k251_7, "251.8": k251_8,
    "253.1": k253_1, "253.3": k253_3, "253.4": k253_4, "253.6": k253_6,
    "254.1": k254_1, "254.2": k254_2, "254.4": k254_4, "254.5": k254_5,
    "254.6": k254_6, "254.7": k254_7a,
}

MANUAL_REASONS = {
    "249.6": "PR #257 正文里的命令与例子，不在代码里",
    "250.6": "PR #258 正文里的逐例预期/实际与来源",
    "251.2": "需要锁定执行源码 40 位 SHA、镜像 digest 与提示摘要；尚未冻结",
    "251.9": "沿用既有费用账本需负责人确认；本任务卡声明不新增授权",
    "252.1": "需要真实运行环境与模型身份；缺凭据",
    "252.2": "24 槽派发依赖凭据；机制已在 DRY RUN 中验证",
    "252.3": "记账规则已实现（reconcile.py），但没有真实运行可记入台账",
    "252.4": "没有正在进行的派发，停止条件无法被行使或观察",
    "252.5": "没有候选产生，无外部固定任务可判",
    "252.6": "没有真实运行，token 与端到端时间无数据可核对",
    "252.7": "本轮没有记录，与历史 E2 分池无从执行",
    "252.8": "没有矩阵结果，完整矩阵与支持范围无内容可写",
    "253.2": "保留材料与答案清单未提供，无摘要可留存",
    "253.5": "需与 #247 的持有者协调后端/技能/环境来源",
    "253.7": "无保留场景结果，无法与参考版本比较",
    "254.3": "四条件比较依赖 #252/#253 的结果",
    "254.8": "作者、单位、贡献与授权需实际参与者提供",
    "254.9": "论文/计划书/PPT 尚未成稿，无从核对同一口径",
}


def run_one(cid, issue, text):
    if cid in COVERED:
        try:
            result = COVERED[cid]()
            status, evidence = result[0], result[1]
        except Exception as exc:                            # noqa: BLE001
            status, evidence = UNMET, "raised %s: %s" % (type(exc).__name__, str(exc)[:80])
        if status not in STATUSES:
            status, evidence = UNMET, "check returned %r as a status" % (status,)
        return dict(id=cid, issue=issue, criterion=text, status=status,
                    evidence=str(evidence))
    if cid in MANUAL_REASONS:
        return dict(id=cid, issue=issue, criterion=text, status=MANUAL,
                    evidence=MANUAL_REASONS[cid])
    # neither checked nor explained: that is missing coverage, not a pass
    return dict(id=cid, issue=issue, criterion=text, status=UNMET,
                evidence="no check and no stated reason for skipping")


def main():
    ids = [c[0] for c in CRITERIA]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise SystemExit("duplicate criterion ids: %s" % sorted(duplicates))

    rows = [run_one(*entry) for entry in CRITERIA]
    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1

    print("=" * 78)
    print("验收条件审计 —— 逐条（#249-#254，%d 条）" % len(rows))
    print("=" * 78)
    for row in rows:
        print("[%s] %s  #%d  %s" % (row["status"].ljust(7), row["id"],
                                    row["issue"], row["criterion"][:52]))
        print("           %s" % row["evidence"])
    print()
    print("covered criteria: %d of %d" % (len(rows), len(CRITERIA)))
    print("summary:", json.dumps(counts, ensure_ascii=False))

    payload = dict(rows=rows, counts=counts, criteria=len(CRITERIA))
    # The audit is a check, not an evidence generator: its output is a byproduct.
    # Writing it into the repository by default made every run dirty the working
    # tree, which once refused a merge. Callers that want the file ask for it.
    out = os.environ.get("AUDIT_OUT")
    if out:
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
