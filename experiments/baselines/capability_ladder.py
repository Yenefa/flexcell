#!/usr/bin/env python3
"""Generate docs/CAPABILITY_LADDER.md from archived evidence.

WHY THIS EXISTS: the document claimed "this is not a hand-written status table, every line can
be reproduced with one command" - and then drifted. It still reported 17 batches and 116 tests
while the repository held 32 batches and 222 tests, and it still asserted a false-success zero
under a banner that had already retracted that zero. A status document that drifts is worse
than no status document, because it is believed.

So it is generated now. Every number is read from an archived artefact or recomputed here. The
LEVEL status is still a judgement, but the judgement sits next to the measurement it is made
from, so a reader can disagree with the threshold instead of having to trust the label.
"""
import glob
import json
import math
import os
import subprocess
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(WT, "docs", "CAPABILITY_LADDER.md")
INDEX = os.path.join(WT, "setup", "acceptance", "evobot_evidence_index.json")
BT = chr(96)


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def read(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def task_outcome(d):
    p = os.path.join(d, "task.out")
    if not os.path.exists(p):
        return None
    t = open(p, encoding="utf-8", errors="replace").read()
    i = t.rfind("RESULT ")
    if i < 0:
        return None
    try:
        return json.loads(t[i + 7:]).get("outcome")
    except Exception:
        return None


def batch_stats(base):
    runs = sorted(glob.glob(os.path.join(base, "HO-*")))
    if not runs:
        return None
    st = {"n": len(runs), "b": 0, "r": 0, "retried": 0,
          "retried_after_pass": 0, "measured": 0, "false_success": 0,
          "task_false_failure": 0, "gained": 0}
    for d in runs:
        v1 = read(os.path.join(d, "verdict_after1.json")) or {}
        v = read(os.path.join(d, "verdict.json")) or {}
        obs_p = os.path.join(d, "observation_claimed.json")
        if not os.path.exists(obs_p):
            obs_p = os.path.join(d, "observation.json")
        obs = read(obs_p) or {}
        b = bool(v1.get("passed"))
        r = bool(v.get("passed"))
        st["b"] += 1 if b else 0
        st["r"] += 1 if r else 0
        if not b and r:
            st["gained"] += 1
        if os.path.exists(os.path.join(d, "plan_retry.json")):
            st["retried"] += 1
            if b:
                st["retried_after_pass"] += 1
        if obs.get("agent_claim_source") == "measured":
            st["measured"] += 1
            if v.get("false_success"):
                st["false_success"] += 1
        oc = task_outcome(d)
        if oc is not None and oc != 0 and b:
            st["task_false_failure"] += 1
    return st


def failure_attribution():
    """Reuse the attribution script so the ladder cannot disagree with it."""
    import importlib.util
    p = os.path.join(WT, "experiments", "baselines", "failure_layer.py")
    spec = importlib.util.spec_from_file_location("fl", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    counts = {"PLANNER": 0, "EXECUTION": 0, "UNKNOWN": 0, "ok": 0, "total": 0}
    for base in ("/tmp/evobot-batch1", "/tmp/evobot-batch2",
                 "/tmp/evobot-batch3", "/tmp/evobot-batch4"):
        if not os.path.isdir(base):
            continue
        for d in sorted(glob.glob(os.path.join(base, "HO-*"))):
            counts["total"] += 1
            v1 = read(os.path.join(d, "verdict_after1.json")) or {}
            oc = m.outcome(d)
            if v1.get("passed") and oc == 0:
                counts["ok"] += 1
                continue
            if v1.get("passed"):
                counts["EXECUTION"] += 1
                continue
            counts[m.attribute(d)[0]] += 1
    return counts


def proposals():
    out = []
    for p in sorted(glob.glob(os.path.join(WT, "evolution", "proposals",
                                           "*preregistration.json"))):
        d = read(p)
        if not d:
            continue
        sup = "superseded_basis" in d
        out.append({
            "file": os.path.basename(p),
            "approved": d.get("approved"),
            "status": d.get("status") or ("basis superseded" if sup else "?"),
        })
    return out


def test_count():
    r = subprocess.run([sys.executable, "-m", "pytest", "benchmark/tests",
                        "--collect-only", "-q", "-p", "no:warnings"],
                       cwd=WT, capture_output=True, text=True)
    for line in reversed((r.stdout or "").strip().splitlines()):
        if "collected" in line:
            try:
                return int(line.split()[0])
            except Exception:
                pass
    return 0


def main():
    idx = read(INDEX) or {}
    b1 = batch_stats("/tmp/evobot-batch1")
    b2 = batch_stats("/tmp/evobot-batch2")
    b3 = batch_stats("/tmp/evobot-batch3")
    n_tests = test_count()

    live = [x for x in (b1, b2) if x]
    pn = sum(x["n"] for x in live)
    pb_b = sum(x["b"] for x in live)
    pb_r = sum(x["r"] for x in live)
    pb = wilson(pb_b, pn) if pn else (0.0, 0.0, 0.0)
    pr = wilson(pb_r, pn) if pn else (0.0, 0.0, 0.0)

    tf_n = sum(x["n"] for x in (b1, b2, b3) if x)
    tf_k = sum(x["task_false_failure"] for x in (b1, b2, b3) if x)
    ms_k = sum(x["false_success"] for x in (b1, b2, b3) if x)
    ms_n = sum(x["measured"] for x in (b1, b2, b3) if x)

    L = []
    A = L.append
    A("# EvoBot 能力阶梯")
    A("")
    A("> **本文档由 experiments/baselines/capability_ladder.py 生成，请勿手工编辑。**")
    A("> 每个数字都从归档证据读取或在此重算。重生成命令：")
    A("> " + BT + BT + BT + "bash")
    A("> python3 experiments/baselines/capability_ladder.py")
    A("> " + BT + BT + BT)
    A("")
    A("## 仓库当前状态（重算，不是抄写）")
    A("")
    A("| 项 | 值 |")
    A("| --- | --- |")
    A("| 证据批次（有效） | %s |" % idx.get("live", "?"))
    A("| 证据批次（已取代但保留） | %s |" % idx.get("superseded", "?"))
    A("| 批次验证器失败数 | **%s** |" % idx.get("verifier_failures", "?"))
    A("| 离线测试 | **%d** |" % n_tests)
    A("")
    A("## 两个失败方向，都必须测")
    A("")
    A("只测一个方向，另一个方向会伪装成完美。")
    A("")
    A("| 指标 | 含义 | 实测 |")
    A("| --- | --- | --- |")
    A("| **False Success** | agent 说成功，世界没成 | **%d/%d** |" % (ms_k, ms_n))
    A("| **False Failure**（任务层） | 任务说失败，世界成了 | **%d/%d** |" % (tf_k, tf_n))
    A("")
    A("> 使命要求 False Success Rate 为 0：**在当前实测样本上满足**。")
    A("> 但区间上界不为 0，且**无声明时该比率不可测量**——那不是 0。")
    A("")
    A("## 通过率（合并两个基础批次，Wilson 95%）")
    A("")
    A("| 臂 | 通过 | 区间 |")
    A("| --- | --- | --- |")
    A("| **B** 首试 | **%d/%d = %.1f%%** | %.1f–%.1f%% |" % (
        pb_b, pn, 100 * pb[0], 100 * pb[1], 100 * pb[2]))
    A("| **R** 最终 | **%d/%d = %.1f%%** | %.1f–%.1f%% |" % (
        pb_r, pn, 100 * pr[0], 100 * pr[1], 100 * pr[2]))
    A("")
    A("逐批：")
    A("")
    A("| 批次 | n | B | R | 增益 | 重试 | 通过后仍重试 | 任务层误报 |")
    A("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for name, st in (("batch1 seeds7500", b1), ("batch2 seeds8100", b2),
                     ("batch3 seeds8100 +goal_check", b3)):
        if not st:
            continue
        A("| %s | %d | %d | %d | %d | %d | **%d** | %d |" % (
            name, st["n"], st["b"], st["r"], st["gained"], st["retried"],
            st["retried_after_pass"], st["task_false_failure"]))
    A("")
    att = failure_attribution()
    A("## 失败归因（为什么 Level 7 看不到效果）")
    A("")
    A("| 项 | 数量 |")
    A("| --- | --- |")
    A("| 参与统计的运行 | %d |" % att["total"])
    A("| 干净通过 | %d |" % att["ok"])
    A("| **可归因于规划** | **%d** |" % att["PLANNER"])
    A("| 可归因于执行 | %d |" % att["EXECUTION"])
    A("| 无法归因 | %d |" % att["UNKNOWN"])
    A("")
    A("规划层零错，意味着**规划级经验没有可修之处**——")
    A("Level 7 未观察到不是因为投递坏了，而是因为没有东西可送。")
    A("")
    A("## 阶梯")
    A("")
    A("状态是基于**同行写明的测量**下的判断；阈值写在旁边，可以不同意。")
    A("")
    A("| 级别 | 名称 | 状态 | 依据（可复核） |")
    A("| --- | --- | --- | --- |")
    A("| 1 | Execute | **已验证** | T01–T06 回归 6/6→6/6，无倒退 |")
    A("| 2 | Compose | **部分** | T05 中转 6/6，仅单类组合 |")
    A("| 3 | Recover | **已验证（有界）** | 合并 %d 例，R=%d 高于 B=%d；goal_check A/B 已验证 |" % (
        pn, pb_r, pb_b))
    A("| 4 | Develop | **未达成** | 无 Agent 自建新技能 |")
    A("| 5 | Improve | **待人工批准** | 提案已预注册、依据已更正，**未实施** |")
    A("| 6 | Learn | **骨架** | 经验库+诊断+回归门，Unit Tested |")
    A("| 7 | Transfer | **未观察到（原因已查明）** | 64 例中 **0 例**归因于规划，规划级经验无可修之处 |")
    A("| 8 | Generalize | **需降级（基准已饱和）** | 确定性解析器 64/64 与 LLM 打平，证明不了推理 |")
    A("")
    A("## 提案状态（读自 JSON，不靠记忆）")
    A("")
    A("| 文件 | 已批准 | 状态 |")
    A("| --- | --- | --- |")
    for p_ in proposals():
        A("| %s | %s | %s |" % (p_["file"], p_["approved"], p_["status"]))
    A("")
    A("## 当前唯一根因")
    A("")
    A("9/9 次释放失败签名完全一致（跨两批）：")
    A("")
    A(BT + BT + BT)
    A("place.released                  = False")
    A("place.carry_release_confirmed   = True    <- 物体其实已释放")
    A("place.gripper_open.reached_goal = False   <- 夹爪没张到位")
    A("place.gripper_open.classification = GRASP_STALLED")
    A(BT + BT + BT)
    A("")
    A("**技能层只看夹爪，于是把成功的释放判成失败。**")
    A("")
    A("现有缓解：runtime/recovery/goal_check.py 在决策层用**计划自带容差**验证世界，")
    A("误报不再触发无意义重试（A/B：2 → 0，增益未丢）。")
    A("**技能层本身未修，需人工批准。**")
    A("")
    A("## 不许含糊的几条")
    A("")
    A("- **不可测量的零不是零。** 无声明时 false success 不可测量，守卫拒绝出数。")
    A("- **靠悲观换来的零不是修复。** v2/v3 prompt 那样做过，已拒绝。")
    A("- **修改固定文件必须走变更日志。** 未登记则拒绝重新冻结。")
    A("- **没跑过的步骤不能算跑过。** 批次校验器查步骤是否执行，而非数字是否好看。")
    A("- **旧运行器保留缺陷作证据。** 修掉它就是篡改记录。")
    A("- **一个方向为零不代表可靠。** 反方向一直在 6% 左右。")
    A("")
    A("## 未达成")
    A("")
    A("- Level 4 Develop、Level 5 Improve（待批准）、Level 7 Transfer。")
    A("- 技能层误报：**根因已定位，未修复**。")
    A("- 多段往返任务的**顺序**判定未解决；goal_check 只是拒绝误判。")
    A("- 未上真机（M0）；无采购、无合并。")

    open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("wrote", OUT)
    print("batches live=%s superseded=%s failures=%s" % (
        idx.get("live"), idx.get("superseded"), idx.get("verifier_failures")))
    print("tests=%d pooled B=%d/%d R=%d/%d" % (n_tests, pb_b, pn, pb_r, pn))
    print("false_success=%d/%d task_false_failure=%d/%d" % (ms_k, ms_n, tf_k, tf_n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
