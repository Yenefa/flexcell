# EvoBot Baseline A — 第一次真实任务执行（独立验收）

**日期：** 2026-11-11 00:20 (+08:00)
**任务：** `T01-train-seed1000` — "Put the red block in the right bin and the blue block in the left bin."
**臂：** Baseline A（确定性 composite 执行器，**无 Agent 规划**）

## 结果

| 项 | 值 |
| --- | --- |
| composite 结果 | `outcome=0`, `error_code=0` |
| 完成阶段 | `target_box_a-0`, `target_box_b-1` |
| 独立验收 | **PASS** |
| `target_box_a` 落点误差 | **9.26 mm**（阈值 60 mm，zone_1） |
| `target_box_b` 落点误差 | **4.39 mm**（阈值 60 mm，zone_2） |
| 静置检查 | 两个物体均 `resting=true` |
| `false_success` | **false** |

## 这次运行证明了什么

1. **EvoBot 的任务闭环打通了**：TaskSpec → 机械计划 → `RunComposite` → Gazebo 执行
   → 技能日志 → 观测桥 → **独立验收器**。
2. **验收是独立的**：判定来自 `benchmark/evaluators/evaluate.py`，读的是技能日志里
   `verify.measured` 的**实测物体位置**，不是机器人自报的结果。
3. **Baseline A 可用**：现有机器人栈在"别人告诉它做什么"时能完成任务。

## 这次运行**没有**证明什么

- **没有证明 Agent 能自主完成**。计划是 `plan_from_spec` **机械推导**出来的，
  不是 Agent 决策的。这一臂存在的意义正是测量"栈本身能做什么"。
- **没有证明泛化**。只跑了 1 个 train 实例。
- 因此能力等级仍记为 **LEVEL 1（Execute），且仅限 Baseline A**。

## 途中修掉的两个真实缺陷（都不是机器人问题）

### 1. `error_code=41` "another task owns the arm"
第一次尝试用 `sim_smoke.py` 启动，但它启动后会**自己跑 demo**，占住机械臂。
改为手动 `trusted_sim.launch.py` 起栈、不派发内置任务。**属 Runtime/工具问题。**

### 2. `error_code=64` "plan must declare every observed object"
生成器假设场景有 3 个方块（a/b/c），但**默认世界只有 a 和 b**，
`target_box_c` 只在 `three_boxes` 场景存在。

修正方式：把**场景组成**记录为世界属性（`SCENES`），生成器从场景取物体，
而不是从"所有已知物体"取。新增回归测试断言"声明的物体必须等于世界里的物体"。

**这是我在本轮犯的第 2 类错误**：把"资产存在"当成"场景里存在"。

## 复现

```bash
bash ci-public-window/scripts/evobot_run_b.sh \
  wt-comp/benchmark/tasks/train/T01-train-seed1000.json /tmp/evobot-t01c
bash ci-public-window/scripts/evobot_verify.sh
```
