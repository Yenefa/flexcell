# 恢复前先测量世界：不再盲信「任务失败」

## 上轮发现的问题

32 例中 **2 例（6.2%）** 是 false failure：任务报告失败，但箱子已释放、已在目标区内，
技能自己的 `verify.jsonl` 也说 `verified=True`。

**恢复驱动读的是 `task.out`，于是它重试了一个已经完成的放置。**

## 修复：`runtime/recovery/goal_check.py`

在决定重试之前，用**实测位置 + 计划自己声明的容差**检查目标是否已达成。

```python
if satisfied:
    recovery_decision.json = {"action": "no_recovery",
        "reason": "goal already satisfied by measurement"}
    return 0   # 不生成 plan_retry.json
```

### 容差来自哪里（关键）

`plan.json` 自带 `position_tolerance_m` = **20 mm**，是 agent 事先声明的精度标准。
验收器的目标区半径是 **60 mm**。

用 20 mm 判断，比 60 mm **严格 3 倍**——所以这个检查**偏保守**，
它会在验收器抱怨之前就先拒绝跳过。

**它不读封存答案，不读验收器容差，因此不可能制造通过。**
如果它判断错了，运行提前结束，独立验收器照样会判失败——这是诚实的结果。

## 我引入又抓到的两个 bug

### bug 1：把每一段的目标都当成最终目标

第一版对**所有 stage** 比对 `place_pose`。

但 T12 三重往返任务里，**同一个物体有 3 段**：
```
target_box_a-0  [0.12, -0.195]
target_box_a-1  [0.25,  0.05]
target_box_a-2  [0.12, -0.105]   ← 这才是目标
```

物体停在**第一段目标**时，第一版就报告「已完成」。

**而 `HO-5a96f3eb4fae` 正是这种任务，且它的恢复是真实增益。**
这个 bug 会**直接删掉本项目唯一测到的能力提升**。

### bug 2：最终位置不足以证明顺序

修完 bug 1 后我查了另一例 `HO-47afdffad81a`：
箱_b 实测 `[0.1666, -0.1636]`，最终目标 `[0.165, -0.15]`，**相差 13.6 mm**——
在 20 mm 容差内。

但三重往返任务的判定**还要求访问顺序**。**位置对 ≠ 任务完成。**

### 最终规则：不能确定就拒绝

```python
if 任何物体出现在多段中:
    return False, {"why": "goal includes an ordering this check cannot verify"}
```

**只在每个物体恰好一段时才下结论，否则交给原有恢复逻辑。**

## 决策表（真实归档数据）

| run | 批次 | 已达成 | 期望 |
| --- | --- | --- | --- |
| HO-a69ec651037a | batch2 | **True** | false failure，恢复本无意义 |
| HO-f9431f8ef925 | batch2 | **True** | false failure，恢复本无意义 |
| HO-5a96f3eb4fae | batch1 | **False（拒绝）** | 真实失败，**恢复产生过增益** |
| HO-47afdffad81a | batch1 | **False（拒绝）** | 真实失败，**恢复产生过增益** |

两个方向都对：**该跳过的跳过，该恢复的恢复。**

## 一个我拒绝使用的「证据」

我也做了完整驱动的重放。`HO-5a96f3eb4fae` 重放得到 `no_recovery/UNKNOWN`，
与原始 `resume` 不符。

查下去是**我的重放副本不够忠实**：`diagnostics.enrich` 在副本里读不到复合日志，
所以 `native_detail` 缺失、失效分类退化成 UNKNOWN。

**这不是 goal_check 的问题，但这份重放不能当证据。**
因此改用**直接针对 goal_check 的真实归档 plan + ground truth** 验证（上表）。

## 状态

| 项 | 值 |
| --- | --- |
| 离线测试 | **211 passed** |
| 封存 | `BLOCKED_GOOD` |
| 验收器 | **未改** |
| 技能层 | **未改** |
| 改动范围 | `runtime/recovery/`（2 个文件） |

## 不宣称

- **尚未在新机器人批次上端到端验证**——本轮只有归档数据回放与单元测试；
- 不宣称 2/32 是真实误报率（CI 1.7–20.1%）；
- 不宣称修好了技能层——**误报本身仍在**，本修复只是不让它浪费恢复；
- 不宣称三重往返任务的顺序问题已解决（只是**拒绝误判**）；
- **未上真机，M0**。

## 下一步

跑一个新批次，确认两件事：
1. false failure 不再触发重试（`retried_after_pass` 应为 0）；
2. **真实失败的恢复增益不丢失**（gained 应仍 ≥ 2）。
