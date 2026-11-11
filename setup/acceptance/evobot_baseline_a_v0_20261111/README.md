# Baseline A v0 — 冻结

**冻结时间：** 2026-11-11 17:20 (+08:00)
**分支：** `autonomous/flexcell-remediation`
**这是什么：** 一个**确定性**基线（机械计划 + 现有技能 + 独立验收），**没有任何 agent 规划**。
它存在的意义是测量「机器人栈本身能做什么」，好让后续 agent 的增量可以被归因。

## 定义（冻结，不得为了让数字好看而改）

| 环节 | 实现 |
| --- | --- |
| 计划 | `experiments/baselines/build_composite_plan.py` —— 纯机械，stage 顺序与目标点直接来自 TaskSpec |
| 净空策略 | `CLEARANCE_FACTOR = 1.3 × 物体边长`，并 clamp 进 RunComposite 合约窗口 `[0.05, 0.25]`；35mm 方块 → **0.05** |
| 执行 | `composite_client.py` → `RunComposite` action server |
| 验收 | `benchmark/evaluators/evaluate.py` v0.2.0 —— `(spec, final_state)` 的纯函数，不读 agent 任何自述 |

**没有为了产生本目录里的任何数字而修改过断言、容差或验收器。** 组件哈希见 `config.json`。

## 结果

| 批次 | 实例 | 结果 | 说明 |
| --- | --- | --- | --- |
| 首轮 `baseline_a_batch_20261111` | 6 | **无效测量** | DDS participant 耗尽，被误判为机器人失败，见该目录 `INVALID_MEASUREMENT.md` |
| 域隔离轮 `baseline_a_batch_20261111_r2` | 6 | **6/6 通过**，Wilson 95% CI **[0.6097, 1.0]**，false_success **0** | 每个实例独立 ROS domain |
| 全量 `baseline_a_v0_full_20261111` | 72（T01–T06 × 12 种子） | 进行中 | 同一配置，仅增加样本 |

## 两个被自己的数据推翻的假设（留档，避免重犯）

1. **「`clearance_m=0.05` 是失败根因」——错。** T01 与 T02 的 clearance **完全相同**（都是 0.05），一个过一个不过。
   源码：`vacant()` 判的是中心距严格大于 clearance（`contracts/composite.py:116-117`），
   而 0.06 会让 box_a(0.22,0)→zone_2(0.25,0.05) 的 0.0583 m 中心距**在规划阶段就被拒**（error 60）。
   所以「改成 0.06」是把执行失败换成规划拒绝，不是修复。
   已实测的另一面：净空 0.00 精确复现失败，0.02/0.04/0.06 通过（见交接文档 §2.4）。
   **净空与哪种失败相关，本冻结不做断言。**
2. **「Baseline A 只有 1/6」——错，是假失败。** 固定 `ROS_DOMAIN_ID=211` 跑了 6 次后
   cyclonedds participant 表耗尽，从第 4 次起 client 根本建不了节点；第 2、3 次的 native 技能
   报 `ERR_MOTION_FAILED`/`ERR_GRASP_FAILED`——看起来和真实抓取失败**一模一样**。
   域隔离后同 6 个实例 **6/6**。

## 一个必须知道的度量假象

`evaluate.py:172` 定义 `false_failure = passed and not claimed`。Baseline A 是机械执行器、
**从不自称成功**，所以它每通过一个实例都会带 `false_failure: true`。
**这不是缺陷**，是「基线不产生 claim」的结构性后果。该字段只对 agent 基线（B/C）有意义。

## 复现

```bash
# 单个实例（完整闭环：机械计划 → Gazebo → 独立验收）
bash ci-public-window/scripts/evobot_run_b.sh \
  wt-comp/benchmark/tasks/train/T01-train-seed1000.json /tmp/a-v0

# 批量（每实例独立 ROS domain，基础设施故障不计入通过率）
bash ci-public-window/scripts/evobot_baseline_a_batch.sh <outroot> <spec...>
python3 ci-public-window/scripts/evobot_batch_summary.py <outroot>
```

## 自检（可失败）

```bash
python3 verify.py          # 检查冻结哈希未漂移、r1 已标无效、计数自洽、false_success=0、每个通过都有实测数字
```

已验证它会失败：改动 `config.json` 里任一哈希 → rc=1；把某个通过实例的测量值清空 → rc=1；恢复 → rc=0。

## 这次**没有**证明什么

- 没有证明 agent 能自主完成 —— 计划是机械推导的。
- 没有证明泛化 —— 只覆盖 train 分割。
- 72 实例全量结果尚未出，**在此之前不引用完整通过率**。
