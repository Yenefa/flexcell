# EvoBot 能力报告（2026-11-11）

**按 mission §11.1 要求，明确区分：已有能力 / 新增能力 / 失败能力 / 未验证能力 / 需人类批准。**

能力分级：Designed → Implemented → Unit Tested → Simulation Tested → Independently Verified → Generalization Tested。**不越级。**

---

## 1. 已有能力（本轮之前就存在，本轮复核）

| 能力 | 等级 | 证据 |
| --- | --- | --- |
| T01–T06 TaskSpec + 生成器 + 执行器 + 独立验收 | **Simulation Tested** | `benchmark/`，72 实例批次 |
| 确定性执行（Baseline A） | **Simulation Tested** | A-v0 冻结；A-v2 重测中 |
| held-out 物理隔离 | **Independently Verified（仅机制）** | `root:ros 0750`，uid 1001 被拒，变异 exit 1 |
| Baseline B 规划（LLM） | **Unit Tested + plan-level** | 17/18 规划成功，**从未真实执行** |

---

## 2. 新增能力（本轮产生）

| 能力 | 等级 | 证据 | 缺口 |
| --- | --- | --- | --- |
| **Push 技能**（`PushObject` action + `push_server`） | **Implemented + Unit Tested** | 64 测试通过；6 变异全红 | **从未在仿真里推过任何东西** |
| **Push 验收判据**（`evaluate.py` v0.3.0 `push` 子句） | **Implemented + Unit Tested** | 9 检查 + 4 变异全红；纯增量已验证 | 未经独立复核 |
| **T08 任务实例**（3 dev + 3 unseen） | **Designed** | `benchmark/tasks/t08_*`，`instance_sha256` 冻结 | 从未运行 |
| **A′ 规则规划器（T01–T06）** | **Unit Tested** | 72/72 规划正确，零模型调用 | plan-layer only |

---

## 3. 失败能力（尝试过，未成功）

| 尝试 | 结果 | 根因 | 分类 |
| --- | --- | --- | --- |
| T08 Step 0：推 30 mm | **NOT_FEASIBLE** | 位移在 **23.02 mm 处饱和**，末端再走 16 mm 方块不动 = 接触丢失 | Control / Grasp 边界 |
| T07 堆叠 | **算术上不可行** | `composite.py:45` 要求 `clearance_m ≥ 0.05`，堆叠节距 0.035 | Planning（契约） |
| T09 杂乱场景 | **不作为独立能力** | 观测是 oracle 真值，「识别干扰物」根本没被考 | — |
| T10 受约束放置 | **现契约下不可行** | 验收器是终态纯函数，受约束与自由放置终态字节相同 | — |

---

## 4. 未验证能力（代码存在，但没有执行证据）

| 项 | 状态 |
| --- | --- |
| Baseline B 的真实机器人成功率 | **NOT_RUN** — 只有规划层结果。执行通路已建（`evobot_run_b_with_plan.sh`）但未跑 |
| Baseline C 的自演进闭环 | **NOT_RUN** — 骨架存在，无一次完整「失败→改进→验收」事件链 |
| A/B/C/D 四组对照 | **NOT_RUN** — D 未定义 |
| 任何泛化结论 | **NOT_RUN** — 全部是 train 分割；held-out 隔离已强制但未用于评测 |
| T08 Push 与 OpenMANIPULATOR-X 的真实交互 | **NOT_RUN** — 脚本就绪，等仿真通道 |

---

## 5. 需要人类批准的改动

| 改动 | 为什么需要批准 | 现状态 |
| --- | --- | --- |
| 技能层释放状态误报（`carry_release_confirmed=True` 但 `released=False`） | 属核心运行时安全契约 | 已有预注册提案，**未实施** |
| 修改 `period`/`clearance` 等冻结契约参数 | 会改变已有成功阈值 | 未动 |

---

## 6. 本轮最重要的负面结论

### T01–T06 不能用来证明 Agent 优势

**72/72 规划正确，零 LLM 调用，由一个 6 条规则的确定性正则解析器完成。**

结合项目自己的记录：旧 A′ 看模板前编写 → 0/16（诚实拒绝）；A′-new 看模板后编写 → 64/64。

**结论：一旦知道任务类型，正则就够了。** 任何在 T01–T06 上宣称的 agent 智能优势都站不住。

### A-v0 的 61.1% 是进程泄漏的产物，不是能力

`evobot_run_b.sh` 的清理列表漏了 6 个 skill 节点，每实例泄漏 6 个孤儿，累积后饿死下一实例的 carry servo。
修复后：负载从爬到 31.4 变为平稳 3-6，通过率从 44/72 变为 **54/55**。

### 容差假设已证伪

T05 两个实例在空闲机器上 `position_tolerance_m=0.02` 即通过，0.06 结果完全一致。
**A-v1 不采用**——不是有害，是**无效**。

---

## 7. Level 判定

| Level | 状态 | 依据 |
| --- | --- | --- |
| L1 Designed | ✅ 达成 | |
| L2 Implemented | ✅ 达成 | |
| L3 Unit Tested | ✅ 达成 | 64 push 测试 + 9 判据检查 + 变异证明 |
| **L4 Simulation Tested（新技能）** | ❌ **未达成** | push 技能从未在仿真中执行 |
| L5 Independently Verified | ❌ 未达成 | |
| L6–L7 经验迁移 | ❌ 未达成 | |

**本轮未跨过 Level 4。** 技能代码存在、测试通过，但「代码存在、测试通过」不等于「机器人完成了任务」——
这正是 mission §9.F 明令禁止的那类混淆。

---

## 8. 复现

| 项 | 位置 |
| --- | --- |
| Git | `autonomous/flexcell-remediation` @ 本文件同 commit |
| 验收器 | `benchmark/evaluators/evaluate.py` v0.3.0 |
| A-v2 批次 | `ci-public-window/evidence/baseline_a_v2_gated_20261111/`（含顺序与负载记录） |
| T08 首次实推脚本 | `setup/acceptance/evobot_t08_first_run_20261111/` |
| 规则饱和度 | `setup/acceptance/evobot_rule_saturation_t01_t06_20261111/` |
