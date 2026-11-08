# B2c 协议 — FSM vs Calibrated Hybrid（同条件 3+3，冻结）

> 前置：B2b 已证明 fast 臂可被真实路由（n=1）。B2c 是第一次**同条件对照**。
> 本协议在运行前提交；指标与判读不得事后放宽。

## 1. 两臂
| 臂 | 命令 |
| --- | --- |
| F（FSM 对照） | `sim_smoke --case normal --backend velocity_servo --skill-backend legacy --decision-policy fsm` |
| H（校准 hybrid） | 同上 `--decision-policy hybrid --hybrid-threshold 0.85`，并设 `FLEXCELL_JEV_*` + 校准产物 |

其余参数（world、pose、预算、超时、`skill_backend`）一致。

## 2. 共同配置（避免混杂）
- 两臂都把 `jev_backend` 设为 `local`（实验配置；运行结束恢复原文件）；
- H 臂额外设置：`FLEXCELL_JEV_API_KEY_FILE`、`FLEXCELL_JEV_MODEL=deepseek-flash`、`MODEL_SHA256` 取自校准产物、`FLEXCELL_JEV_MAX_TOKENS=512`、`FLEXCELL_JEV_TIMEOUT_S=60`。

## 3. 运行设计
- 每臂 3 次，交替：F, H, H, F, F, H；
- 每次独立 `GZ_PARTITION` / `ROS_DOMAIN_ID`，运行前清理残留；
- 单次超时 600 s；失败保留日志，不自动重跑。

## 4. 指标（预注册）
| 指标 | 定义 |
| --- | --- |
| 主指标：任务成功 | `status=PASS` 且 `task.outcome=OUTCOME_SUCCEEDED` |
| 任务 wall | `task.wall_seconds` |
| 路由 | episode trace：source 分布、escalated 次数、fallback 次数 |
| fast 成本 | fast 决策数、token 合计、decide 延迟（ms） |
| 失败 | `status`/`error_code`/`detail` |

## 5. 判读规则（冻结）
- 主指标 3/3 vs 3/3 → 记 **无成功差异**；
- wall 差异需 > 2 s 才写"更慢/更快"，但 n=3 **不宣称显著**；
- fast 命中率 = jev 决策数 / 路由决策数，逐次报告；
- 任何 false success → 作废该次并单列；
- 不因结果修改验收器/阈值/世界。

## 6. 边界
- 仿真（M3-S）；fast 臂是远端 API（延迟与本地模型不可比）；
- 校准标签为 FSM 一致率，不是物理成功率；
- n=3 为探索性，不作统计显著性结论。

## 7. 冻结声明
- 本文件在运行前提交；结果写入 `setup/acceptance/b2c_fsm_vs_hybrid_20261109/`。

## 8. 结果附录（运行后追加，不改判读规则）
- 6/6 运行 PASS；FSM 平均 14.218 s，Hybrid 平均 17.652 s（**+3.434 s ≈ +24%**）；
- Hybrid 每 run 3/3 路由决策走 fast，escalation 0，fast 延迟 813–1506 ms；
- 记录：`setup/acceptance/b2c_fsm_vs_hybrid_20261109/`；
- 结论按 §5：**无成功差异**，wall 更慢（探索性，n=3）。
