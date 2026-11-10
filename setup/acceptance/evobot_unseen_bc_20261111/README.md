# B/C 在未见任务上的配对 — 第二次干净负面结果

## 为什么再跑一次

上轮 v0.1 held-out 上 C 无效果，理由是「B 已 6/6，天花板测不出差异」。
本轮换成 **B 会失败的未见任务类型**（上轮 B 只有 3/6 干净通过），
给经验真正留出空间。这是最有利于 C 的实验条件。

## 结果

| 指标 | B | C |
| --- | --- | --- |
| 独立验收 PASS | 5/6 | 6/6 |
| **干净 PASS** | **5/6** | **5/6** |
| 平均 tokens | 942 | 1144 (+21%) |
| **计划与 B 相同** | — | **6/6 字节完全相同** |
| False Success Rate | **0/12 = 0.0%** | |

## 不把 6/6 vs 5/6 读成「C 更强」

1. **6 对 `plan.json` 字节完全相同**，经验没有改变任何计划；
2. 唯一差异 `HO-42109d30fa00`：B `err 62`、C `err 0`，同一计划的执行波动；
3. **B 在两个独立批次上分别是 4/6 和 5/6**——波动幅度本身就 ≥ 任何 C 优势；
4. C 还多花 21% token（prompt 更长）；
5. `HO-96e57334764a_C` 是 `outcome=1` 却 `graded=True` 的**分歧通过**，
   所以干净通过两边都是 5/6。

**结论：即使给了最有利条件，经验通道仍没有产生可测量的改进。**

## 两轮负面结果合起来说明什么

| 条件 | C 是否改进 |
| --- | --- |
| v0.1 天花板（B 6/6） | 否 |
| **v0.2 未见类型（B 会失败）** | **否** |

排除「天花板」解释后，剩下的解释更根本：**当前经验通道只影响 prompt，
而影响成败的是执行层**。上轮已诊断：未见任务上 Agent 规划 6/6 正确，
所有失败都是 `err 61/62` 的执行问题。给 prompt 加 lesson 无法修复机械臂交接。

## 因此本轮同时建了 Level 3 Recover

`runtime/recovery/recover.py`，针对**真正瓶颈**而不是 prompt：

- **动作表预先登记**：失败类别 → 有界动作（respread / redispatch / reobserve /
  no_recovery），**不在看到结果后发明策略**；
- **预算有界**：最多 1 次重试；
- **失败证据保留**：`record()` 把原始失败原样带在记录里；
- **不改验收**：respread 只加大同箱阶段之间的落点间距，
  越出箱半径直接 `ValueError` 拒绝；clearance / tolerance 原样不动；
- 决策与执行分离，便于独立审计。

新增 9 个单测（总计 **97 个离线测试**）。

## 状态

| 能力 | 阶段 |
| --- | --- |
| Baseline C 经验检索 | Simulation Tested / Independently Verified / Generalization Tested；**效果未观察到** |
| **Level 3 Recover** | **Designed + Implemented + Unit Tested** |
| Recovery 实际执行 | **未开始** |

**不宣称**：C 优于 B、经验迁移有效、Level 3 达成、Level 6/7/8 达成。

## 途中修掉的缺陷（都是我自己写的）

- 测试里 `json` 未导入（`NameError`）；
- `FAILURE_CLASSES` 定义在 `store.py`，我误从 `classify.py` 导入；
- `ACTION_TABLE` 漏了几类，单测断言「必须覆盖全部 10 类」把它抓出来。

## 下一步

把 Recovery 真正接到运行器上：失败 → 分类 → 有界重试 → **独立验收** → 回归；
测量「恢复成功率」而不是再测 prompt。
