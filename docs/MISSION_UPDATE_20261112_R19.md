# MISSION UPDATE — goal round 18 (2026-11-12)

**Branch** autonomous/flexcell-remediation · **Master Goal** docs/EVOBOT_MASTER_GOAL_20261112.md
**North Star** §8–§14 still **BLOCKED_MISSION_TEXT_MISSING** — never invented.

---

## §19.1 本轮：第一次量到 P1 的 recover 能力——18/24 = 75%

P1 要求 observe / plan / execute / **diagnose** / **recover**。后两项我一直没有测量。

归档里我先看到的是：

- **110 条运行时 `recovery_decision.json`，全是 `no_recovery`**（104 条「第一次就成功」，6 条「按测量目标已满足」）
  ——**这些运行根本不需要恢复**。
- **26 条更丰富的记录**里恢复真的触发了：**24 条选 `resume`**，2 条 `no_recovery`。
- **这 26 条没有一条最终通过**——全部 `outcome=1`。

看起来结论很干脆：**恢复被声明了，但没用。**

**这个结论是错的**，而我抓到自己错在哪，值得写下来。

## §19.2 我犯的错

我先用「有没有 `-a2` 这类兄弟目录」来判断重试是否执行过——**一个都没有**，差点写下
「24 个重试计划被构建，0 个被执行」。

然后我去 grep **谁写**`plan_retry.json`、**谁读**它。`runtime/` 里没有任何地方读——**这支持了错误结论**。
但 `setup/acceptance/evobot_unified_runner_20261111/run_batch.sh:113` 读了：

```bash
if [ -f "$D/plan_retry.json" ]; then
    python3 "$CLIENT" --plan "$D/plan_retry.json" --timeout 400 > "$D/task_retry.out" 2>&1
```

**重试就在同一个目录里跑，写 `task_retry.out`。** 有 **24 个 `task_retry.out`**。
**错的是我的目录启发式，不是代码。**

## §19.3 测量结果

| 重试结果 | 数量 |
| --- | --- |
| `outcome=0` — **恢复了** | **18** |
| `outcome=1, ec=62` | 4 |
| `outcome=1, ec=60` | 2 |

**重试成功率 18/24 = 75%。**
24 个首轮失败的 episode 里，**18 个在唯一允许的那次重试上完成**。失败的 6 个按设计没有第三次机会。

## §19.4 为什么这是能力，不是刷分

这一点决定 75% 是能力还是把戏，所以我去查了**设计**，不是接受这个数字：

| 性质 | 证据 |
| --- | --- |
| 恢复**只**依据执行证据，绝不依据评分结论 | `recovery_driver.py:2-7` 明说，代码只读 `task.out` 的 `RESULT` |
| 评测器只在**所有尝试之后**、对最终世界状态评分 | 同上 docstring |
| **原始失败被保留** | 26 条记录全部 `original_failure_preserved: True` |
| 有防止「假失败也重试」的守卫 | `recovery_driver.py:57-63`：按测量目标已满足就记 `no_recovery`，不浪费一次循环，*「更糟的是，会让『臂 R』看起来被用过了，其实没有」* |
| 重试**有界** | `budget: 1` |

**对真正失败的 episode 重试是恢复，不是刷分**：机器人观测到失败、从执行证据诊断、重建或重排计划、再试一次。
这正是 P1 要的东西。

## §19.5 一个我提出又自己否掉的怀疑

我怀疑基线可能只记原始失败、从而**低估**项目自身的能力。

**查了：没有。** `summarize_recovery.py:63-72` 有一个独立的 **`RECOVERED`** 类别，
与 FIRST_TRY / STILL_FAIL 并列。**记账是对的，我的怀疑不成立。**

## §19.6 这不改变什么，我不会让它改变

- **这不是 T08。** 这些是 pick/carry/place，不是 push。**T08 skill 级仍是 0/6**，第 17 轮那个
  ±3.44 mm 可重复性 vs 2.5 mm 崖的问题**一点没动**。
- **这不是 Generalization Tested。** 重试发生在「恢复行为还在开发时」用过的 held-out 实例上，
  我不声称 75% 会迁移到未见种子。
- **它不自动提高已报告的通过率**——记账问题是分开的，而我已经查过，记账是对的。

## §19.7 这是本项目第一个正面且可从已提交产物独立核验的机器人能力结果

它**不需要新的仿真运行**，而且**一直躺在归档里**。

## §19.8 花费与资源

| 项 | 数量 |
| --- | --- |
| **Gazebo 运行** | **0** |
| LLM 付费调用 | **0** |
| 孤儿进程 | **0** |
| 钉定文件改动 | **0** |
| 阈值 / 评测器 / 任务集改动 | **0** |
| 删除证据 | **0** |
