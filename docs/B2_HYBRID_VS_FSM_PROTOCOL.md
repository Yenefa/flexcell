# B2 协议 — Hybrid vs FSM（同条件，冻结草案）

> 依三 Track 修正案：Hybrid Router 研究不得因 Development Agent 进展而停止。
> 本协议在任何 B2 运行前写入；指标与判读不得事后放宽。

## 0. 前置依赖（必须先检查）
B2 的 fast 臂需要 `FLEXCELL_JEV_ENDPOINT`（本地快速模型端点）。**当前环境没有该端点**
（`FLEXCELL_JEV_BACKEND: null`，历史 fast 模型 `clef-flash-q8_0` 权重不可得）。

因此本协议区分两种情形：
- **P1（fast 可用）**：可测分层决策的价值（成本/延迟/成功率）。
- **P2（fast 不可用，当前）**：只测"hybrid 在缺 fast 时的退化行为"与"FSM 对照"，**不得**
  用它宣称分层决策有效或无效。

## 1. 两臂
| 臂 | 命令 |
| --- | --- |
| 控制 F | `sim_smoke --case normal --backend velocity_servo --skill-backend legacy --decision-policy fsm` |
| 处理 H | 同上，`--decision-policy hybrid` |

其余参数（world、object、pose、预算、超时）一致；hybrid 阈值冻结为 **0.85**（与 E-021 的 τ 臂同值）。

## 2. 运行设计
- 每臂 1 次探测（P2 阶段），成功条件满足后再扩 n；
- 每次独立 `GZ_PARTITION`/`ROS_DOMAIN_ID`，运行前清理残留；
- 单次超时 480 s；失败保留日志，不自动重跑。

## 3. 指标（预注册）
| 指标 | 定义 |
| --- | --- |
| 主指标 | `status=PASS` 且 `outcome=OUTCOME_SUCCEEDED` |
| 路由行为 | episode `policy_trace`：source 分布（fsm/jev/llm）、escalated、fallback |
| 成本 | paid 调用数、token（若有）、决策延迟 |
| 失败分类 | `status`/`error_code`/`detail` |
| 证据 | episode 文件、`initial_world_state`、`runtime_fingerprint` |

## 4. 判读规则
- 若 H 臂因缺 fast 端点而**无法运行**（启动失败/策略异常）：记 **INFRA_BLOCKED**，不写"hybrid 更差"；
- 若 H 臂可运行但全部 escalate 到 slow：记 **DEGRADED_HYBRID**，只报告成本与成功率，不评价分层价值；
- 若两臂均成功且 H 有 fast 命中：进入 P1，需扩 n 后才可讨论延迟/成本收益；
- 任何 `false success`（PASS 但验证失败）作废该次并单独报告。

## 5. 边界
- 仿真（M3-S），非真实机器人；
- 不修改验收器/阈值/世界；
- 不把"缺 fast 端点"解释为"hybrid 无价值"。

## 6. 冻结声明
- 本文件在 B2 运行前提交；运行结果写入 `setup/acceptance/b2_hybrid_vs_fsm_20261109/`。
