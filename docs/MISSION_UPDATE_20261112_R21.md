# MISSION UPDATE — goal rounds 33–42 (2026-11-12): the T08 arc, and what it cost to get it wrong

**Branch** autonomous/flexcell-remediation · **Master Goal** docs/EVOBOT_MASTER_GOAL_20261112.md
**North Star** §8–§14 still **BLOCKED_MISSION_TEXT_MISSING** — never invented.

*Rounds 18–32 have per-round entries in `docs/FACT_STATE_20261112.md`; this report covers the ten rounds that
overturned the T08 conclusion and had no §19 report of their own.*

---

## §19.1 发生了什么

这十轮里，T08 的结论被自己的测量推翻了三次，最后落在一个我最初就该检查的地方。

| 轮次 | 当时的结论 | 后来的裁决 |
| --- | --- | --- |
| 33 | 26 次试验 0 通过；注册预测被反驳 | **作废**——harness 没给轨迹 |
| 34 | "T08 失败在缺证据，不在运动" | **降级**——从一次试验过度概括 |
| 35 | 自己撤回 34 | 正确 |
| 36 | `evaluate.py:227` 从 state 文件读 `traj`，缺失即 fail-closed | **成立** |
| 37 | 独立重评 pilot 的 5 条轨迹：**4/5** | **成立，且可复现** |
| 38 | T08 的完整 `passed: true` 存在 | **成立** |
| 40 | 作废的 run 停在 47 次，47/47 fail-closed | 与机制预测一致 |

## §19.2 真正的结论

```
evaluate.py:227   traj = (final_state.get("trajectory") or {}).get(name)
evaluate.py:221   # fails closed: 没有轨迹则 clause 为 False，绝不为 True
evaluate.py:253   terminal_passed = 所有 clause 的合取
evaluate.py:332   passed = terminal_passed AND 九门证据包通过
```

**我的 state 文件只有 `{"objects": …}`，没有 `trajectory` 键。** 所以 clause 对**每一次**试验都走 fail-closed
分支，**与机器人做了什么无关**。49 次试验、47 次试验——同一个结果，由构造决定。

**这个设计正是 Master Goal 要的**：终点几何无法证明是推而不是搬，所以没有轨迹就拒绝通过。
**它在正常工作；是我没有喂给它。**

## §19.3 被推翻的旧结论，逐条

| 我曾声称 | 现在 |
| --- | --- |
| "机械臂可重复性 ±3.44 mm，崖宽 2.5 mm，所以这个配置做不了 T08" | **测量真实，推论错误**。机器人 5 次里 4 次把箱子推进了目标区 |
| "request-field 路线被能力上限关闭" | **关闭它的从来不是运动** |
| "T08 skill 级 0/26" | **0/26 是我的 harness 的度量，不是机器人的** |
| "recovery 没带来收益" | **作废**——所有观测被构造性地压成同一个值，测不出效应 |

**站得住的两条**：T08 终点判据在 ≤3 次重试下 **4/5**（我从存档轨迹独立重评复现）；完整 `passed: true`
**可达且已达到**。

## §19.4 四轮里我撤回了三次自己的结论

第 33、34、35 轮各撤回一次。共同成因相同：**我读了一个工件，看见一个模式，然后在检查它是否在
第二个独立样本上成立之前就下了结论**。每次的纠正都来自**去看那个我没看的情况**。

最贵的一次：**连续二十轮**我报告这台机械臂做不了 T08，依据是一个由**扣着所需证据的 harness**
产生的评分数字。而解释那句话印在**每一条** verdict 里：

> *no trajectory for this object: end state alone cannot prove it was pushed rather than carried*

**我把它读成了判词，而不是关于我自己 harness 的诊断。**

## §19.5 证据等级（不夸大）

| 声明 | 等级 |
| --- | --- |
| T08 终点判据 4/5（≤3 次重试），独立重评复现 | **Simulation Tested** |
| T08 完整 `passed: true` 可达且达到 | **Simulation Tested** |
| T08 在未见实例上的规模表现 | **未确立**——没有干净的 n |
| **Generalization Tested** | **没有** |
| P1 recovery 18/24 = 75% | **Simulation Tested**（第 18 轮，来自归档） |
| P3 七字段记录 | **0/6 达到审核标准** |
| P4 | **`EVOLUTION_ADVANTAGE_NOT_DEMONSTRATED`** |
| **L4 Develop** | **未跨过** |

## §19.6 下一步（给接手的人）

1. **T08 重跑**：state 写成 `{"objects": …, "trajectory": {name: …}}`——pilot 的 `traj_t1.json` 就是形状。
   **故障在评分，不在仿真**：机器人的行为一直是对的。
2. **P3** 需要一个**审核者**，不是又一个自动检查。存活的缺陷是语义的：**这条 lesson 是否从这条证据推得出来**。
3. **P4** 仍在 `BLOCKED_MISSION_TEXT_MISSING` 后面。**不得编造。**

## §19.7 花费与资源

| 项 | 数量 |
| --- | --- |
| LLM 付费调用 | **0** |
| Gazebo 运行 | 47（作废的那次，已停止并保留证据） |
| 孤儿进程 | **0**（仿真器已释放） |
| 钉定文件改动 | **0** |
| 阈值 / 评测器 / 任务集改动 | **0** |
| 删除的证据 | **0** |
| 撤回过自己结论的次数 | **3** |
