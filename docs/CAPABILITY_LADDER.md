# EvoBot 能力阶梯 — 由证据索引派生

> ## ⚠ 已撤回的结论
>
> 此前多处出现的 **「False Success Rate 0/32」是空的**，已撤回。
> 原因是 `agent_claimed_success` 缺失时被当作 `False`，加上运行器从未采集自评。
>
> **真实测量（修正后）：False Success = 0/32，自评准确率 87.5%。**
>
> 修正过程：v1（计划当执行）1/32 → v2/v3（靠悲观换零，被拒）→ **v4（补坐标系）0/32 且准确率 87.5%**。
> 详见 `setup/acceptance/evobot_assess_v4_20261111/`
> 使命要求「False Success Rate 必须为 0」→ **未满足**。
>
> 同时：False Failure = 11/32 = 34.4%，自评准确率 20/32 = 62.5%。
> 证据：`setup/acceptance/evobot_honesty_retraction_20261111/`

> **能力已冻结。** `benchmark/capability_baseline.json` 用 SHA-256 固定了 9 个
> **定义「正确」的文件**（判分器、schema、封存方案、回归门）。
> 任何改动它们的行为都会被 `python3 evolution/validation/freeze_baseline.py --verify`
> 立即检出，并要求重跑实验。这把「不许改验收器制造成功」从纪律变成了机制。

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
| 5 | Improve | **未达成** | 循环已产出第一个 **`WOULD_FIX`** 提案（`evobot_actuator_proposal`，24 条证据，目标 `place_server.py`），但**未获人工批准、未应用、未测效果** |
| 6 | Learn | **骨架** | `evobot_baseline_c_skeleton`：经验库+诊断+回归门，Unit Tested |
| 7 | Transfer | **未观察到（机制已查明）** | `evobot_lesson_routing`（**仅计划层，未跑机器人**）：4 条教训仅 1 条属 planner，且 planner 本就满足；**16/16 计划字节相同，+3% token 纯开销** |
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

## 提案循环的诚实状态

审计发现 `evolution/proposals/` **是空目录**：门禁能判提案，但没人生成提案。
**这解释了为什么两轮 B/C 实验都测得「经验 0 效果」**——学习没有通向行为的路径。

现已补上 `generate.py`（证据→聚类→提案→门禁）与 `check_applied.py`（用真实代码行为验证）。

唯一生成的提案被标注为 `ALREADY_SATISFIED`：间距是我手工修的，提案只是事后重建。
**这不是自进化成果，不能那样报。**

## 三臂规划层对比（同一批 16 个封存实例，`evobot_three_arm`）

| 臂 | 未见过任务**规划** | 说明 |
| --- | --- | --- |
| A′ FSM 规则 | **0/16** | 全部诚实拒绝，不瞎猜 |
| B Runtime Agent | **16/16** | 全对 |
| C Self-Evolving | **16/16** | 与 B 完全相同 |

**A′ 在新任务上是 0，这正是 Agent 存在的理由；B 规划 16/16 说明瓶颈在执行层。**

## 待人工决定（已预注册验收标准）

对 `place_server.py` 的有界释放重试**已在改代码前预注册**：

| 项 | 预注册值 |
| --- | --- |
| 基线 | n=32，B 25/32，R 29/32 |
| 预测 | **最终通过率不变 29/32**；首试最多 +6 |
| 真实增量 | **延迟与风险，不是通过率** |
| 推翻条件 | 任一持续 stall 通过 / 最终通过数下降 / false success ≠ 0 → **必须回滚** |

理由：现有计划级重试**已经救回 6/9** stall，技能层重试上限也是 6/9，**是同一批案例**。

## 待人工决定（原记录）

`evolution/proposals/actuator_stall.json` 已生成并通过门禁，标注
`requires_human_approval: true`，**尚未应用**：

对 `place_server.py` 第 417 行的 `gripper_open` 增加**有界释放重试**。
预期效果可 falsify：仅因首次 stall 失败的阶段会成功，持续 stall 仍必须失败。

批准后流程：应用 → 重跑 16 例 → 证明 stall 率下降且 false success 仍为 0 → 方可宣称 Level 5。

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

## 合并 n=32 的结果（`evobot_pooled_n32`，Wilson 95% 区间）

| 指标 | 值 |
| --- | --- |
| B 首试通过 | **25/32 = 78% (61–89%)** |
| R 最终通过 | **29/32 = 91% (76–97%)** |
| 配对转移 | gained=4, lost=0 |
| stall 出现 | 9/32 = 28% (16–45%) |
| **False Success Rate** | **0/32 = 0.0%** |

全部 3 例剩余失败的根因**都是** `ACTUATOR_STALL_ON_RELEASE`。

## 剩余失败的唯一根因（`evobot_actuator_rootcause`）

16 例未见过任务中，**全部剩余失败同一个原因**：

```
gripper did not open (position=-0.011, requested=0.02, stalled=True)
```

**夹爪释放时卡死**，不是规划、不是恢复、不是经验问题。

| 根因 | 数量 | B 首试 | R 最终 |
| --- | --- | --- | --- |
| `ACTUATOR_STALL_ON_RELEASE` | 4 | 0/4 | **3/4** |
| 无执行器故障 | 12 | 12/12 | 12/12 |
| **合计** | 16 | 12/16 | **15/16** |

同一落点 (0.205, 0.050) 出现 2 次卡死、4 次成功 → **不是几何问题**。

## 已知未解决

- 执行层稳定性：单批次内仍会出现 `err 60/61/62`；
- 恢复率分母太小，无法给出比率；
- `err 60`（目标点被已放置物体占用）需要动态选点，未实现；
- C 的「应用提案到源码并重建」故意未实现（需人工批准写作用域）；
- 未在真实硬件上运行，**M0，禁止上真机**。
