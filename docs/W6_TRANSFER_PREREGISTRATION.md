# W6 预注册 — 失败归因知识的跨任务迁移（Cold vs Warm）

> 目的：测量"把先前任务的**失败归因知识**带到新任务"是否能降低适应成本。
> 本文件在正式 3+3 运行前提交；指标与判读不得事后修改。

## 1. 迁移的是什么
- 源任务：T-G1（normal，place pose 不可达 → 修 `place_pose`）；
- 目标任务：T-G3T（regrasp，**同样的不可达失败**，但 agent 需自行诊断）；
- **知识内容**（人工从源任务证据中归纳，不是模型自学）：
  "PLACE 失败且 `ERR_MOTION_FAILED` ⇒ 目标点不可达；`0.20 <= hypot(x,y) < 0.30` 可用"。

## 2. 两臂
| 臂 | task.md |
| --- | --- |
| Cold | 只给失败事实："任务失败，请从 telemetry 诊断并修 plan.json" |
| Warm | Cold + 上述迁移知识（明确的 prior experience 段） |

其余一致：同一 initial plan `{case: regrasp, place_pose: [0.45,0,0.0175]}`、同模型 deepseek-chat、同预算、同验收。

## 3. 运行设计（正式）
- 每臂 3 次，交替 C,W,W,C,C,W；
- 单次超时 600 s；失败保留，不重跑；
- 先跑 1 次 Warm 试点验证注入机制（记录为 pilot，不进入 3+3 统计）。

## 4. 指标（预注册）
| 指标 | 定义 |
| --- | --- |
| 主指标：适应成本 | **达到成功的迭代次数**（越少越好） |
| 次指标 | token 数、agent wall clock、执行次数 |
| 失败 | 是否成功、最终 error_code |
| 证据 | 每次独立验收 PASS 与否 |

## 5. 判读规则（冻结）
- Warm 迭代数 < Cold 且 3/3 成功 → 记"**迁移降低适应成本（探索性）**"；
- 无差异 → 记"未观察到迁移收益"；
- Cold 更少 → 如实记录，不解释为知识有害（n=3）；
- 任何 false success 作废该次并单列；
- 不宣称统计显著。

## 6. 边界
- 迁移知识是**人工归纳**并写入 task.md 的，模拟"经验传递"，不是 agent 自学；
- 只测一个目标任务（regrasp）；
- 仿真（M3-S）；
- 结果写入 `experiments/pilot-001/runs/p1.5-w6-transfer-20261109/`。
