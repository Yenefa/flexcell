# P0 配对对照：A′ vs B，同实例、同执行器、同验收器

**日期** 2026-11-12 · **分支** `autonomous/flexcell-remediation`

---

## 为什么做这个

mission §2 的验收标准是：**「至少形成一批相同任务实例、相同公共观察、相同验收器的
A′/B 实际执行对照」**。在此之前这个对照不存在——

| | 之前 | 现在 |
| --- | --- | --- |
| A′ | 有 72 实例真实 Gazebo 结果 | 复用 |
| B | **只有 plan 级 JSON**（README 自写 `Simulation Tested: NO`） | **真实执行** |

拿「世界终态」比「一个 JSON 文件」不是对照。

---

## 实验条件（这是对照的全部意义）

| 项 | 设置 |
| --- | --- |
| 实例 | `T01-train-seed1000/1001/1002`、`T02-train-seed1000` |
| 世界生成 | 同一个 `sim_profile.profile` 调用 |
| 执行器 | 同一个 `RunComposite` action |
| 验收器 | `benchmark/evaluators/evaluate.py` v0.5.0 |
| 位置容差 / 间隙 | 0.02 m / 0.05 m（相同） |
| 运动档 | **计划自带的 `demo_slow`**，不替换 |
| 阈值 | 未改动 |
**唯一变量：计划的来源。**

A′ = `rule_planner_t01_t06.py` 确定性规则，只读公开观察。
B = 冻结的 LLM 计划（`baseline_b_v2 plans/`），不重新调用模型。

---

## 结果

### 1. 真实执行与独立验收

| 实例 | A′ 通过 | B 通过 | B 执行器 outcome | B False Success |
| --- | --- | --- | --- | --- |
| T01-train-seed1000 | ✅ | ✅ | 0 (SUCCEEDED) | False |
| T01-train-seed1001 | ✅ | ✅ | 0 (SUCCEEDED) | False |
| T01-train-seed1002 | ✅ | ✅ | 0 (SUCCEEDED) | False |
| T02-train-seed1000 | ✅ | ✅ | 0 (SUCCEEDED) | False |

```
A-prime: 4/4   B: 4/4   False Success: 0
```

**Baseline B 首次获得真实 Gazebo 独立验收结果。** 此前它只有计划。

### 2. 计划的实质对比

```
T01-train-seed1000
  A-prime: [('target_box_a', (0.12,-0.15,0.0175)), ('target_box_b', (0.25,0.05,0.0175))]
  B      : [('target_box_a', (0.12,-0.15,0.0175)), ('target_box_b', (0.25,0.05,0.0175))]
  IDENTICAL
```

四个实例 **全部逐字节相同**。

---

## 这个结果的含义（研究诚实性要求写清楚）

### LLM Agent 在这批任务上没有增量价值

mission §9 明确要求：「**若简单规则能达到同等表现，必须说明 Agent 的增量价值在哪，
不得制造创新叙事。**」

**答案是：在 T01–T06 上，增量是 0。**

这不是负面结果，是**基线饱和**的证据——也正是此前认定「不能靠 T01–T06 证明 Agent 优势」
的实证依据。现在它有了真实执行数据支撑，不再只是断言。

### 为什么这反而是有用的

1. **确立了公平基线**：以后任何 C/D 组声称优势，必须先超过这个 4/4。
2. **证明 B 的规划链路是通的**：从 LLM 计划到真实执行到独立验收，全程无人工干预。
3. **定位了真正的判别任务**：T01–T06 无法区分，需要 T08 这类技能缺失任务。

### 不能从这个结果推出的东西

- ❌ 不能说「B 比 A′ 强」——相同
- ❌ 不能说「B 比 A′ 弱」——相同
- ❌ 不能外推到 T08 或 held-out——只跑了 4 个 train 实例
- ❌ 不能说这是成功率——**n=4**，且都是 T01/T02 两个模板

---

## 与 A-v2 的关系

A-v2 全批是 **71/72**。本对照只取其中 4 个实例，因为 B 的冻结计划只覆盖 18 个。

**A-v2 是否读 `expected_goal`？** 已核查：`observation.json` / `plan.json` / `verdict.json`
中 `expected_goal` 出现次数均为 **0**，计划由规则从公开观察生成。故可与 B 公平比较。

（A-v0 是读 oracle 的版本，A-v2 不是。两者不可混用。）

---

## 复现

```bash
bash ci-public-window/scripts/evobot_baseline_b_realexec.sh <outdir> 4
```

前置门：`benchmark/tools/check_ros_interfaces.py`（接口不对直接退出，不浪费仿真）。

证据：`ci-public-window/evidence/b_realexec_20261112/`
（`b_results.tsv` + 每实例 `plan.json`/`composite.json`/`gt_after.json`/`verdict.json`）

---

## 边界

| 项 | 状态 |
| --- | --- |
| 真实物理执行 | ✅ 两边都是 |
| 相同验收器 | ✅ |
| 相同执行器 | ✅ |
| 相同运动档 | ✅ `demo_slow` |
| 样本量 | ⚠️ **n=4，两个模板** |
| held-out | ❌ 未涉及 |
| 模型成本 | B 的 token 数已在 `baseline_b_v2 plan_level_check.json` 记录（14,643） |

**这只是 P0 的最小闭合，不是能力结论。**
