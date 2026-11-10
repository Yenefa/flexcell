# EvoBot 能力阶梯 — 由证据索引派生

**这份文档不是手写状态表。** 每一行的依据都能用一条命令重跑：

```bash
python3 experiments/baselines/evidence_index.py   # 跑全部 17 个批次验证器
python3 -m pytest benchmark/tests -q              # 116 个离线测试
```

最新一次索引结果：**17 个批次 / 0 个 verifier 失败 / 10 个有效 / 7 个已被取代（保留）**。

## 阶梯与当前证据

| 级别 | 名称 | 状态 | 依据 |
| --- | --- | --- | --- |
| 1 | Execute | **已验证** | `evobot_t02_ab` / `evobot_t04_b` / `evobot_t05_n6_clean` |
| 2 | Compose | **部分** | T05 中转 6/6；但只有一类组合任务 |
| 3 | Recover | **部分** | `evobot_recover_n6` 1/2；`evobot_spacing_fix` 显示根因修复更有效 |
| 4 | Develop | **未达成** | 没有 Agent 自行创建过新技能 |
| 5 | Improve | **未达成** | 没有 Agent 自行改动并过回归的记录 |
| 6 | Learn | **骨架** | `evobot_baseline_c_skeleton`：经验库+诊断+回归门，Unit Tested |
| 7 | Transfer | **未观察到** | `evobot_unseen_bc`：计划字节全同，经验无效果 |
| 8 | Generalize | **部分** | `evobot_unseen_n6`：未见任务类型上规划 6/6，干净完成 3/6 |

## 关键数字（全部来自归档证据）

| 指标 | 值 | 来源 |
| --- | --- | --- |
| False Success Rate | **0.0%** | 所有批次 |
| T05 中转独立验收 | **6/6** | `evobot_t05_n6_clean` |
| 首次 held-out 干净通过 | **5/6** | `evobot_heldout_n6`（已被取代） |
| 未见任务类型干净通过 | **3/6** | `evobot_unseen_n6` |
| 未见任务类型规划正确 | **6/6** | `evobot_unseen_n6` |
| 经验是否改变计划 | **0/6** | `evobot_unseen_bc`（计划字节相同） |
| Level 3 恢复率 | **1/2** | `evobot_recover_n6`（分母仅 2） |
| 间距修复后同箱任务 | **8/8** | `evobot_spacing_fix` |
| v0.1 回归 | **6/6 → 6/6** | `evobot_regression_v01` |

## 三臂状态

| 臂 | 说明 | 代码 | 机器人上跑过 |
| --- | --- | --- | --- |
| **A′** 确定性规则 | 无 LLM，正则+几何 | 是 | 是 |
| **B** Runtime Agent | 从指令+感知规划 | 是 | 是 |
| **C** Self-Evolving | B + 经验检索 + 提案门禁 | 是 | 是 |

**C 与 B 的差异未被观察到。** 两轮对照（v0.1 天花板、v0.2 未见类型）
都是 6/6 计划字节完全相同。

## 这十八轮里最重要的负面结果

| # | 我原本以为 | 证据显示 |
| --- | --- | --- |
| 1 | 建恢复能提升完成率 | 恢复救回 0/4；**根因修复让 4/4 不再需要救** |
| 2 | 经验能改进行为 | 计划 **0/6** 改变 |
| 3 | 未见任务会难住规划 | 规划 **6/6 正确**，瓶颈在执行层 |
| 4 | T04 能区分两臂 | A′ 用一次 `hypot` 就解了 |
| 5 | Baseline A 是公平基线 | A 直接读 `expected_goal`，**是开卷预言机** |

## 已知未解决

- 执行层稳定性：单批次内仍会出现 `err 60/61/62`；
- 恢复率分母太小，无法给出比率；
- `err 60`（目标点被已放置物体占用）需要动态选点，未实现；
- C 的「应用提案到源码并重建」故意未实现（需人工批准写作用域）；
- 未在真实硬件上运行，**M0，禁止上真机**。
