# MISSION UPDATE — goal round 14 (2026-11-12)

**Branch** autonomous/flexcell-remediation · **Master Goal** docs/EVOBOT_MASTER_GOAL_20261112.md
**North Star** §8–§14 still **BLOCKED_MISSION_TEXT_MISSING** — never invented.

---

## §19.1 本轮：修好的播种器能不能接受？能。两条。

第 13 轮结束时，通道是**诚实但空的**：来源校验收掉了全部四条旧种子，而库再也无法重建。
所以真正悬着的问题是：**修好之后的播种器，能不能接受一条真的记录？**
如果不能，这个通道不是「严格」，而是**死的**。

## §19.2 去哪里找真证据

在全部 `*.jsonl` 里搜 planner 类错误码（60/61/63/64）且带 `detail` 字符串的失败：

```
planner-code failures with a machine-readable detail string: 2 distinct, 5 total

  ec=61  n=3  'state drift or occupied destination before target_box_b-1'
  ec=60  n=2  'declared destination occupied at target_box_b-1'
```

都在 `evobot_recover_n6_20261111/runs/HO-90899d657e68/sim/skills/composites/` 下——**真日志，不是散文。**

**顺带更正一件事：旧记录 R4 声称的那个失败是真实的。**
它引错了来源、引错了上下文，但**事件真的发生过**，现在有了机器可读的引用。
「一条引错来源的记录，讲了一件真事」——这个区别值得写下来。

## §19.3 两条真种子，都被接受

```
$ python3 evolution/experience/seed_from_evidence.py --append --seeds evolution/experience/seed_evidence_verified.json
ACCEPT T05-recover-occupied-stage     provenance + actionability ok
ACCEPT T05-recover-declared-occupied  provenance + actionability ok
accepted: 2   rejected: 0
chain intact (6 records)
```

写完之后**再去核对**证据文件（不是假设）：

```
T05-recover-occupied-stage     file_exists=True  evidence_present=True
T05-recover-declared-occupied  file_exists=True  evidence_present=True
```

## §19.4 我弄坏了一个下游过滤器，并修好了

`audit_actionability.py` 按 `validated` 过滤。第 13 轮之后，那个字段的意思是**「旧播种器跑过」**，
不再代表可信——于是它**在悄悄地报告四条最不可信的记录，而无视两条已验证的**。
**一个含义在脚下变掉的过滤器。**

现在按 `provenance_verified` 分成两组分别报告，因为一个混合数字会**隐藏结论适用于哪一半**。

## §19.5 这个结果改变了 P4 能说什么

```
=== VERIFIED cohort ===
  ACTIONABLE FRACTION (verified): 2/2

=== UNVERIFIED cohort ===
  ACTIONABLE FRACTION (unverified): 1/4

=== combined ===  3/6
```

**已验证的每一条都是 planner 可行动的；未验证的大多不是。**
所以**缺陷在播种，不在概念**——这是本轮最有用的结论。

| P4 的陈述 | 第 12 轮 | 现在 |
| --- | --- | --- |
| 能作用于计划的 lesson | 1/4 | **总计 2/6，已验证组 2/2** |
| 它对应的失败在机器可读处出现 | **没有**（ec=64 无处可寻） | **有——ec 60/61，真实日志里 5 次** |
| 证据可从引用来源重新推导 | 0/4 | **总计 2/6；已验证组 2/2** |
| 因此 | 「D 臂没有东西可复用」 | **「D 臂现在有两条关于真实发生过的失败的可行动 lesson；它们在冻结未见集上是否改变行为仍未测量，D 仍未定义」** |

**我不声称 P4 更接近通过。**
两条关于「目的地被占用」的 lesson，可能**根本不会在冻结未见任务集上出现**。
改变的是：**通道不再因为结构性原因而空了**——后续 P4 工作测试的是一个**存在的**机制，而不是一个不可能存在的。

## §19.6 仍然错的，写清楚

1. **四条旧记录的 `validated` 仍是 `True`**，仍然不代表被审核过。新记录是 `validated: False` +
   `provenance_verified: True`，旧记录正好相反。**两种约定并存，字段名仍在误导。**
2. **没有任何审核者签过这两条新记录。** `reviewed_by` / `review_verdict` / `review_ref` 存在且为 `None`。
   **来源验证不是审核**，我不让这个词兼职——这正是第 12 轮的发现。
3. `source_run` 仍指向 run **目录**，不是单个产物。审核五条修复里的第 2 条仍未做。

## §19.7 回归检查

改完 `evolution/` 后再跑差分门（109 个 verifier）：**4 条已知失败不变，0 新失败。**

## §19.8 花费与资源

| 项 | 数量 |
| --- | --- |
| LLM 付费调用 | **0** |
| Gazebo 运行 | **0** |
| 孤儿进程 | **0** |
| 钉定文件改动 | **0** |
| `records.jsonl` | **+2 条，−0 条**（append-only，链完好） |
| 删除证据 | **0** |
