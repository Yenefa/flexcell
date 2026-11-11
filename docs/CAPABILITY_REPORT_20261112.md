# EvoBot 能力报告（2026-11-12）

**按 mission §11.1：明确区分 已有 / 新增 / 失败 / 未验证 / 需人类批准。**

等级阶梯 **不越级**：Designed → Implemented → Unit Tested → Simulation Tested → Independently Verified → Generalization Tested。

> **本报告的一句话结论**：本轮把「一次推动是否真的发生」从不可判定变成可判定，
> 并证明了 T08 推动技能**还不是一个可用能力**。L4 Develop 未跨过。

| 项 | 值 |
| --- | --- |
| HEAD | `bc53352d`（`autonomous/flexcell-remediation`） |
| 终态评测器 | `evaluate.py` **v0.5.0** |
| 证据验证器 | `benchmark/evidence/verify.py` **v1.0.0** |
| 证据 schema | **t08-evidence/1.0** |
| 30 mm 阈值 | **未改**（`test_the_30mm_threshold_is_untouched` 钉死） |
| 离线测试（`benchmark/evidence/`） | **75 passed**（实测，非引用） |

---

## 1. 已有能力（本轮之前存在，本轮复核）

| 能力 | 等级 | 证据 | 复核 |
| --- | --- | --- | --- |
| T01–T06 TaskSpec + 生成器 + 执行器 + 独立验收 | **Simulation Tested** | `benchmark/tasks/train/`（72）+ `val/`（36） | CONFIRMED |
| 确定性执行 Baseline A-v2 | **Simulation Tested** | `setup/acceptance/evobot_a_v2_final_20261111/` | CONFIRMED |
| held-out OS 级隔离 | **Independently Verified（仅机制）** | `evobot_heldout_isolation_20261111/` | CONFIRMED |
| held-out 泛化测量（n=6，5 类模板） | **Generalization Tested（有界）** | `evobot_heldout_n6_20261111/` | CONFIRMED，见 §6 边界 |
| Baseline B v1（agent 自主规划 + 真实 Gazebo） | **Simulation Tested（n=1，已被取代）** | `evobot_t01_baseline_b_20261111/` | CONFIRMED，见 §4 |

### 1.1 A-v2 的数字与它的边界

```
72 实例全部评分，71 通过，98.6%，False Success = 0
唯一失败：T05-train-seed1001
```

**A-v0 的 44/72 = 61.1% 不是能力，是进程泄漏。** 泄漏的 `parameter_bridge` +
`robot_state_publisher` 每实例各留一个，累积到 136 个、`load_after` 从 2.48 爬到 19.89。
中途 reap 后剩余实例在干净机器上跑完（2.28/3.63/4.45/2.30）。**A-v2 不需重跑。**

**一个必须说清的结构性事实**：`false_failure = 71` **不是缺陷**。
`evaluate.py` 定义 `false_failure = passed and not claimed`，而 Baseline A 是机械执行器、
**从不自称成功**。它每通过一个实例都带 `false_failure: true`。
**该字段只对 agent 基线（B/C）有意义**（`evobot_baseline_a_v0_20261111/README.md:42-44`）。

---

## 2. 新增能力（本轮产生）

| 能力 | 等级 | 证据 | 缺口 |
| --- | --- | --- | --- |
| **T08 证据验证器**（9 门，fail-closed） | **Unit Tested** | `benchmark/evidence/`，**75 passed** | 见下 |
| **证据 schema**（完整性/单调/丢弃计数/SHA-256） | **Unit Tested** | 同上 | |
| **轨迹记录器**（插件 step log → 6-DOF bundle） | **Unit Tested + Simulation Tested** | 真实 3210 步 × 2 物体 | |
| **v0.5.0 集成**（push 任务强制证据） | **Unit Tested** | `test_evaluator_integration.py`（10 测试） | |

### 2.1 验证器的四层状态（不可合并）

| 层 | 含义 | 状态 |
| --- | --- | --- |
| **L1 合成验证器验证** | 合成 fixture 证明 9 门各自可独立拒绝 | ✅ **完成** |
| **L2 物理遥测集成** | 真实插件日志 → 合法证据包 | ✅ **完成**（3210 步/物体，0 丢弃） |
| **L3 Gazebo 实推验证** | 一次真实推跑完 9 门 | ✅ **完成，8/9 门通过** |
| **L4 独立任务验收** | T08 `passed=true` | ❌ **未达成**（23.26 mm < 30 mm） |

**L3 通过而 L4 不通过是正确结果，不是缺陷。**
物理证据层说「这是一次真实的、有接触的、没抬起的推」；
终态判据说「但它只走了 23.26 mm」。**两句话同时为真。**

**不得由 L1/L2/L3 推出 L4。** 也不得由 L3 推出「技能能用」。

---

## 3. 失败能力：T08 推动技能**不是**可用能力

**这是本报告最重要的一节。T08 技能本身不可用。**

### 3.1 接触高度效应（实测，n=1/点）

| 接触高度 | 相对方块中心 | 位移 | 接触建立 |
| --- | --- | --- | --- |
| 0.0175 | 0（面心） | 151.14 mm | ✅（**超 150 mm 上限**） |
| 0.0200 | +2.5 mm | 69.92 mm | ✅ |
| 0.0225 | +5.0 mm | 6.32 mm | ✅ |
| 0.0250 | +7.5 mm | 3.55 mm | ❌ |
| **0.0300（原默认）** | **+12.5 mm** | **0.59 mm** | ❌ |

**单调关系**：接触点越高推得越少；到 0.030 **连接触都建立不了**。

### 3.2 重复性：n=5，40%，极差 135.2 mm

| 试次 | 位移 | 余弦 | 终态 |
| --- | --- | --- | --- |
| 1 | 32.13 mm | 0.9849 | FAIL（未进区） |
| 2 | 137.81 mm | 0.9998 | PASS |
| 3 | 57.70 mm | 0.9999 | PASS |
| 4 | 4.19 mm | 0.8290 | FAIL |
| 5 | **−1.74 mm** | **−0.6633** | FAIL（反向） |

```
min 4.2  median 32.1  max 137.8  spread 135.2 mm   terminal 2/5 = 40%
```

### 3.3 固定步进对照：假设被部分推翻

| 配置 | min | median | max | spread | terminal |
| --- | --- | --- | --- | --- | --- |
| RTF=1（基线） | 4.2 | 32.1 | 137.8 | 135.2 mm | 2/5 |
| RTF=0（对照） | 1.8 | 65.2 | 156.8 | **154.9 mm** | 3/5 |

**方差没有消失，反而更大。** 「墙钟调度是唯一原因」被推翻。

### 3.4 根因状态：**UNKNOWN**

| 类别 | 状态 |
| --- | --- |
| Control（接触高度选择） | ✅ 实测效应，**只解释均值，不解释方差** |
| Control（丢失后 `break` 不重试） | ✅ 代码事实，真实但次要 |
| Tooling（控制目标 `end_effector_link` 无碰撞几何） | ✅ 实测到，**未证实为方差主因** |
| Runtime（相同输入 135–155 mm 方差） | ✅ 实测到，**机制 UNKNOWN** |
| Grasp / 接触建立（`contact_made` 有时 False） | ⚠️ 新分叉点，**原因 UNKNOWN** |
| Environment（摩擦/质量） | ⚠️ **UNKNOWN**（未测） |
| Perception / Planning / Kinematics / State Management / Model Reasoning | ❌ 各有证据排除 |

**不得把 2/5 或 3/5 写成「改善」。** n=5 对 n=5，差异在噪声内，且对照里出现新的失败模式
（156.77 mm 超上限）。`FIXEDSTEP_CONTROL_RESULT.md` 明确写：**不得写成「固定步进提高成功率」**。

### 3.5 一个必须记住的诊断教训

第一份诊断（`README.md` 原始部分）把主因判为 **Control（丢失后不重试）**。
接触高度扫描推翻了这个判断。**当时接触高度一直被固定在一个糟糕的值上，
却声称排除了它。** 原文保留未删改，更正写在文末。

---

## 4. 严格分离：计划正确 / 实际执行 / 独立验收 / agent 自述

| 项 | 计划正确 | 实际执行 | 独立验收 | agent 自述 |
| --- | --- | --- | --- | --- |
| **A′ 规则规划器（T01–T06）** | **72/72**，零模型调用 | 不适用 | 不适用 | 不适用 |
| **Baseline A-v2** | 机械推导 | 72/72 执行 | **71/72 PASS** | **从不自称** |
| **Baseline B v1** | n=1 正确 | ✅ 真实 Gazebo | **PASS**（10.34/5.55 mm） | 有 claim |
| **Baseline B v2** | 17/18 planned，17/17 正确 | ❌ **无 Gazebo** | ❌ **未评分** | — |
| **T08 推动** | 方向正确 | ✅ 真实 Gazebo | **未通过**（23.26 mm） | 技能报 FAILED |

**A′ 的 72/72 是 PLAN 级结果，不是成功率。**
规则是**看完模板之后**写的，所以不证明泛化。它证明的是另一件事：
**在这六个模板上，一个确定性正则与 LLM 表现相同**（`evobot_rule_saturation_t01_t06_20261111/`）。

**推论（对本项目的硬约束）**：T01–T06 上的任何「agent 智能优势」都不成立。
agent 的增量必须展示在**规则失败**的任务上——这正是 T08 存在的理由。

---

## 5. 未验证能力（代码/文档存在，无执行证据）

| 项 | 状态 | 依据 |
| --- | --- | --- |
| **Baseline B v2 的真实执行** | **NOT_RUN** | 只有 plan 级；`README` 自述 "Simulation Tested: **NO**" |
| **A′/B 的配对比较** | **NOT_RUN** | B v1 有 n=1 的 A/B 同实例对照，但仅 T01 |
| **Baseline C 自演进闭环** | **NOT_RUN（骨架）** | 75 离线测试，**从未在 Gazebo 运行** |
| **Baseline D** | **UNKNOWN（未定义）** | 全仓无定义 |
| **T08 unseen（seed 3000–3002）** | **NOT_RUN** | 3 个 spec 存在；`HEIGHT_SWEEP_RESULT.md` 明示「未跑，符合协议」 |
| **T08 在未见实例上的表现** | **NOT_RUN** | 同上 |
| **T07 / T09 / T10** | **NOT_RUN（无 spec）** | `benchmark/tasks/` 只有 `train/ val/ t08_dev/ t08_unseen/` |
| **真机（M0）** | **BLOCKED** | 无硬件 |

### 5.1 A/B/C/D 四组对照的真实状态

| 组 | 状态 |
| --- | --- |
| **A**（确定性执行） | ✅ 存在，A-v2 = 71/72 |
| **A′**（规则规划器） | ✅ 存在，72/72 plan-level |
| **B**（agent 规划） | ⚠️ **v1 有 n=1 真实执行**；v2 仅 plan 级；**无成体系的真实执行** |
| **B 的配对 A′/B 比较** | ❌ **NOT_RUN**（除 T01 n=1） |
| **C**（自演进） | ⚠️ **骨架 only** |
| **D** | ❌ **未定义** |

---

## 6. 需要人类批准的改动

| 改动 | 为什么需要批准 | 现状态 |
| --- | --- | --- |
| **夹爪释放状态误报修复**（`carry_release_confirmed=True` / `released=False` / `GRASP_STALLED`） | 技能层是机器人执行代码 | **PROPOSED - awaiting human approval, not implemented**；`approved: false` |
| **改 `contracts/push.py` 从物体几何推导接触高度** | 真正的技能改进，需完整 before/after 证据链 | **本轮刻意未做**；`push.py` 与 HEAD 逐字节相同 |
| 修改 `period`/`clearance` 等冻结契约参数 | 会改变已有成功阈值 | 未动 |

### 6.1 释放状态提案的细节

```
place.released                  = False
place.carry_release_confirmed   = True   <- 物体其实已释放
place.gripper_open.reached_goal = False  <- 夹爪没张到位
place.gripper_open.classification = GRASP_STALLED
```

9/9 次释放失败签名完全一致（跨两批）。技能层**只看夹爪**，于是把成功的释放判成失败。
**已预注册、未实施。** 现有缓解在**决策层**（`goal_check`），误报不再触发无用重试。
**技能层的病还在。**

### 6.2 接触高度几何推导（为什么没做）

`contracts/push.py:58` 的 `contact_height_m` 默认 `NaN`，由调用方给。
调用方一直给 **0.030**——一个与物体几何无关的硬编码常量。
正确做法是从 `spec.objects[].size` 推导（桌面 z=0，35 mm 方块中心在 0.0175）。

| 做法 | 边界 |
| --- | --- |
| 驱动脚本传 `contact_height_m=0.0200` | ✅ 调用方参数，允许 |
| 改 `contracts/push.py` 让技能自己推导 | ❌ **本轮明确禁止**，需人工批准 |

---

## 7. Level 判定

| Level | 状态 | 依据 |
| --- | --- | --- |
| L1 Designed | ✅ 达成 | |
| L2 Implemented | ✅ 达成 | |
| L3 Unit Tested | ✅ 达成 | 75 离线测试 |
| **L4 Simulation Tested（T08 新技能）** | ⚠️ **部分**（2/5 或 3/5，机制 UNKNOWN） | 不构成可用能力 |
| **L5 Independently Verified（T08）** | ❌ **未达成** | 23.26 mm < 30 mm |
| **L6 Generalization Tested（T08）** | ❌ **未达成** | unseen 3000–3002 未跑 |
| **L4 Develop（mission 的 Level 4）** | ❌ **未达成** | 无 agent 自建新技能 |

### 7.1 不得宣称

- ❌ **Level 4 Develop**
- ❌ T08 **SINGLE-INSTANCE SUCCESS**（同一实例 5 次只 2 次通过）
- ❌ T08 **Independently Verified** / **Generalization Tested**
- ❌ **双臂**或**跨本体**能力
- ❌ 把 **LIBERO** 结果并入 OpenMANIMULATOR-X（LIBERO 要 7 自由度 Panda，
  用 OpenMANIPULATOR-X 复现「**不可行**」——`docs/AGENT_HANDOFF.md:256`）
- ❌ 把「代码存在、测试通过」当成「机器人完成了任务」

---

## 8. 本轮最重要的三条负面结论

1. **T08 推动不是可用能力。** 40%（n=5），极差 135 mm，根因 UNKNOWN。
   接触高度 0.030 时**连接触都建立不了**（0.59 mm）。
2. **T01–T06 不能证明 agent 优势。** 72/72 plan-correct 由一个 6 条规则的正则完成，
   零模型调用。
3. **「证据完整」不等于「任务成功」。** 本轮的验证器让前者可判定，
   但它**不能**、也**不应**让后者变容易。

---

## 9. 复现

| 项 | 位置 |
| --- | --- |
| 证据验证器测试 | `python3 -m pytest benchmark/evidence/ -q` → **75 passed** |
| 验证器验收报告 | `setup/acceptance/evobot_t08_trajectory_verifier_20261112/ACCEPTANCE_REPORT.md` |
| 集成流程 | 同目录 `INTEGRATION_PROCEDURE.md` |
| T08 饱和诊断 | `setup/acceptance/evobot_t08_saturation_diagnosis_20261112/` |
| A-v2 最终 | `setup/acceptance/evobot_a_v2_final_20261111/README.md` |
| 规则饱和 | `setup/acceptance/evobot_rule_saturation_t01_t06_20261111/` |
| 释放状态提案 | `setup/acceptance/evobot_release_mechanism_20261111/README.md` |

---

## 10. 与本报告 2026-11-11 版的差异

| 项 | 11-11 版 | 本版 |
| --- | --- | --- |
| A-v2 | 「重测中」 | **71/72，98.6%，False Success 0** |
| T08 技能 | 「从未在仿真推过」 | **推过了**：23.02 / 28.55 / 23.26 mm，均 < 30 mm；n=5 为 2/5 |
| T08 验收判据 | v0.3.0 单子句 | **v0.5.0 + 9 门证据验证器** |
| 验证器 | 不存在 | **v1.0.0，75 测试** |
| held-out 泛化 | NOT_RUN | **n=6，5/6 干净通过（有界）** |
| Baseline B | 「从未真实执行」 | **v1 有 n=1 真实 Gazebo PASS**（已被取代）；v2 plan-level only |
| T07/T09/T10 | 有具体不可行结论 | **无 spec，NOT_RUN** |

> 上一版把 T07/T09/T10 写成具体结论；本轮核对 `benchmark/tasks/` 后确认
> **它们没有 spec 文件**，因此改为 NOT_RUN。旧结论不作为现有能力引用。
