# P0 收尾：冻结已验证能力（此前一直缺失）

## 审计发现的缺口

使命 P0 写着三项：审计仓库、**冻结已验证能力**、建 Benchmark v0.1。
前两项里，**「冻结」从来没有做过**——没有基线文件，也没有任何东西能检测漂移。

这有实际后果：
后来的任何一轮都可以**悄悄改验收器或 schema**，
而旧数字就变成**无法归因**——没人能分清是机器人变了，还是尺子变了。

## 冻结什么

只冻结**定义「正确」的文件**：

```
benchmark/evaluators/evaluate.py           ← 判分器
benchmark/evaluators/sealed_evaluate.py    ← 特权判分器
benchmark/evaluators/observe_from_run.py   ← 观测桥
benchmark/evaluators/capture_ground_truth.py
benchmark/schemas/taskspec.schema.json     ← 任务契约
benchmark/generators/generate.py           ← 任务生成
benchmark/generators/seal_held_out.py      ← 封存方案
benchmark/generators/unseen_tasks.py
evolution/validation/regress.py            ← 回归门
```

**9 个文件，全部 SHA-256 固定。**

## 冻结的内容摘要

| 项 | 值 |
| --- | --- |
| 有效证据批次 | **17** |
| verifier 失败 | **0** |

### 已验证结论（写进基线，不是叙述）

| 项 | 值 |
| --- | --- |
| 三臂规划（同一 16 实例） | A′ **0/16**、B **16/16**、C **16/16** |
| 合并 n=32：B 首试 | **25/32** |
| 合并 n=32：R 最终 | **29/32** |
| 配对转移 | **gained=4, lost=0** |
| **False Success Rate** | **0/32** |
| v0.1 回归 | 6/6 → 6/6，无损失 |
| 经验对计划的影响 | **0/16 改变** |

### 已知瓶颈（写进基线）

**执行器层**：全部剩余失败都是 `ACTUATOR_STALL_ON_RELEASE`。
同一坐标既成功又卡死 → 不是几何问题。
在技能层（`gripper_open` 无有界重试），**不在本作用域**。

### 未达成（写进基线）

Level 4 Develop、Level 5 Improve、Level 7 Transfer、硬件（M0 禁止）。

## 关键：漂移检测是**被测过**的

只测「完好时返回 INTACT」没有意义——那可能是个永远返回 OK 的函数。
所以测试覆盖两种**破坏**情形：

| 测试 | 期望 |
| --- | --- |
| 基线完好 | `INTACT` |
| **篡改 `evaluate.py` 的哈希** | `DRIFTED` + `CHANGED` |
| **固定文件被删除** | `DRIFTED` + `deleted` |

还有两条元测试：
- 判分器**必须**在冻结清单里（否则冻结证明不了任何事）；
- 所有固定文件必须存在。

## 使用方式

```bash
python3 evolution/validation/freeze_baseline.py          # 生成/更新基线
python3 evolution/validation/freeze_baseline.py --verify # 检测漂移
```

基线文件：`benchmark/capability_baseline.json`，随仓库提交。

## 状态

| 项 | 值 |
| --- | --- |
| 离线测试 | **147 passed** |
| 封存 | `BLOCKED_GOOD` |
| 验收器 | **未改**（只是被哈希固定） |
| 机器人运行 | 无（本轮为冻结与验证） |

## 不宣称

- 不宣称冻结等于能力完成（Level 4/5/7 仍未达成）；
- 不宣称 25/32、29/32 可外推到其他任务族；
- 不宣称执行器瓶颈已解决（未碰技能层）。

## 冻结的意义

从现在起，任何改动判分器、schema 或封存方案的行为，
`--verify` 会**立即失败**并要求重跑实验。
这把「不许改验收器制造成功」从**纪律**变成了**机制**。
