# P0 配对对照：A′ vs B（完整版）

**日期** 2026-11-12 · 取代本目录早先只含 4 个实例的版本

---

## 一、计划层对比：17 个实例，12 相同 / 5 不同

读的是**实际运行归档的计划**，不是重新规划——重跑会用到 A-v2 当时没用的规划器，
回答的是「如果重跑会怎样」而不是「实际发生了什么」。

```
A′  ci-public-window/evidence/baseline_a_v2_gated_20261111/<task>/plan.json
B   setup/acceptance/evobot_baseline_b_v2_20261111/plans/<task>/plan.json
```

| 模板 | 实例数 | 相同 | 不同 |
| --- | --- | --- | --- |
| T01 | 3 | 3 | 0 |
| T02 | 3 | 3 | 0 |
| T03 | 3 | 3 | 0 |
| **T04** | 3 | 0 | **3** |
| T05 | 3 | 3 | 0 |
| **T06** | 2 | 0 | **2** |
| 合计 | 17 | **12** | **5** |

### 这 5 个差异是什么

**T04（duplicates）—— 顺序相反，放置相同**

```
指令  把离机器人基座更远的方块放进右箱，更近的放进左箱（颜色是误导）
A′   a→zone_2, b→zone_1
B    b→zone_1, a→zone_2
```
**映射完全相同，只是先搬哪个不同。**

**T06（revisit）—— B 多一站**

```
指令  蓝块先放左箱，再移到右箱。只算最终位置。
A′   [b→zone_1]                     跳过中转，直接放到最终位置
B    [b→zone_2, b→zone_1]            照字面执行两步
```
**A′ 利用「只算最终位置」跳过中转；B 照字面做。终态相同。**

---

## 二、真实执行：9 个实例，双方全过

| 实例 | A′ | B | B 执行器 outcome | B False Success |
| --- | --- | --- | --- | --- |
| T01-train-seed1000 | PASS | PASS | 0 | False |
| T01-train-seed1001 | PASS | PASS | 0 | False |
| T01-train-seed1002 | PASS | PASS | 0 | False |
| T02-train-seed1000 | PASS | PASS | 0 | False |
| T04-train-seed1000 | PASS | PASS | **1** | False |
| T04-train-seed1001 | PASS | PASS | 0 | False |
| T04-train-seed1002 | PASS | PASS | 0 | False |
| T06-train-seed1000 | PASS | PASS | 0 | False |
| T06-train-seed1002 | PASS | PASS | 0 | False |

```
A′ 9/9    B 9/9    False Success: 0
```

**包含全部 5 个计划不同的实例**——差异没有改变任何一次判定。

---

## 三、一个新发现：执行器报失败，但任务达成

`T04-train-seed1000`：

```
composite_outcome = 1 (FAILED)      <- 执行器自称失败
独立验收 passed   = True            <- 终态完全正确
```

项目已知有「技能层释放状态误报」（`carry_release_confirmed=True` / `released=False` /
`GRASP_STALLED`）。**这是一次同类现象的新实例：执行器判定失败，但物体确实到位了。**

**未调查，标 UNKNOWN。** 需要读该实例的 `composite.json` 与 `verdict.json` 才能判断是：

- 技能层误报（与已批准待处理的问题同源），或
- 执行器在中途真的失败了、但物体靠惯性/推挤到了位（偶然成功）

**在查清之前不得把它算作 B 的能力，也不得忽略。**

---

## 四、这推翻了本目录早先的一个结论

早先版本基于 **n=4 且恰好全是 T01/T02**，写了「四个实例计划完全逐字节相同 → LLM 增量是 0」。

**扩到 17 个实例后发现 5 个不同。** 那句「逐字节相同」的适用范围被夸大了。

修正后的准确说法：

| 说法 | 状态 |
| --- | --- |
| T01/T02/T03/T05 上 A′ 与 B 计划相同 | ✅ 实测 |
| T04 上顺序不同、T06 上 B 多一站 | ✅ 实测 |
| **这些差异影响最终判定** | ❌ **不影响，9/9 都过** |
| LLM 在这 9 个实例上有可测增益 | ❌ 没有 |

**不能由此说「LLM 在所有 T01–T06 上增量是 0」**——只测了 9 次真实执行。

---

## 五、公平性核查

| 项 | 结论 |
| --- | --- |
| A-v2 是否读 `expected_goal` | **否**，observation/plan/verdict 中出现 0 次 |
| 同实例 | ✅ |
| 同世界生成 | ✅ `sim_profile.profile` 同参数 |
| 同执行器 | ✅ `RunComposite` |
| 同验收器 | ✅ `evaluate.py` v0.5.0 |
| 同容差/间隙 | ✅ 0.02 / 0.05 |
| 运动档 | ✅ 计划自带 `demo_slow`，不替换 |
| 阈值改动 | ❌ 无 |

---

## 六、边界（不得外推）

| 项 | 状态 |
| --- | --- |
| 真实物理执行 | ✅ 双方都是 |
| 样本量 | ⚠️ **n=9 执行，n=17 计划**，train split |
| held-out | ❌ 未涉及 |
| T05 relay 真实执行 | ❌ **未跑**（B 有计划但不在本次执行集内） |
| 模型成本 | 14,643 tokens（`plan_level_check.json`），**未重跑模型** |
| 执行器误报实例 | ⚠️ 1 个，根因 UNKNOWN |

**这是 P0 的最小闭合，不是能力结论。Level 4 未跨过。**

---

## 七、复现

```bash
# 计划层对比（不需要仿真）
python3 benchmark/tools/compare_plans.py

# 配对表（读归档结果）
python3 benchmark/tools/paired_table.py

# B 真实执行
bash ci-public-window/scripts/evobot_baseline_b_realexec.sh <outdir> 6
bash ci-public-window/scripts/evobot_baseline_b_realexec.sh <outdir> 0 T04-train-seed1000,T06-train-seed1000
```
