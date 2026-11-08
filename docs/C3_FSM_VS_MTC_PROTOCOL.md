# C3 协议 — FSM（控制臂）vs MTC（treatment）同条件对照

> **冻结**：本协议在任何 C3 运行之前写入；运行顺序、指标、判据不得事后修改。
> 依 ADR-003：MTC 是同一 skill seam 之下的 orchestration 实现，**不是**第二个 DecisionPolicy。

## 1. 目的
在同世界、同任务、同后端、同预算条件下，测量 FSM 与 MTC 两套 orchestration 的表现差异。
**不预设**任一方向；结果可为"无差异"、"MTC 更好"或"FSM 更好"，三者都按原文记录。

## 2. 两臂
| 臂 | 命令 | 说明 |
| --- | --- | --- |
| 控制（FSM） | `sim_smoke --case normal --backend velocity_servo --skill-backend legacy` | 冻结的参考实现 |
| 处理（MTC） | `sim_smoke --case normal --backend velocity_servo --skill-backend mtc` | treatment |

其余参数（world、object、pose、decision_policy=fsm、预算、超时）完全一致。

## 3. 运行设计
- **每个臂 3 次**，交替执行（FSM, MTC, MTC, FSM, FSM, MTC），减少时间/热漂移偏差；
- 每次独立 `GZ_PARTITION` 与 `ROS_DOMAIN_ID`，每次运行前清理残留进程；
- 单次超时 480 s；失败保留非零退出与日志，不自动重跑。

## 4. 指标（预注册）
| 指标 | 定义 |
| --- | --- |
| 主指标：任务成功 | `status=PASS` 且 `task.outcome=OUTCOME_SUCCEEDED` |
| 执行时间 | `task.wall_seconds` |
| 恢复行为 | `fsm_trace` 中出现 `RECOVERY` 的次数 |
| 失败分类 | `status` / `task.error_code` |
| 证据 | `evidence_id`、`runtime_fingerprint`、episodes 文件数 |
| 成本 | 两臂均为确定性执行，**模型 token 成本为 0**；只比较执行时间与失败代价 |

## 5. 判读规则（预注册）
- 主指标差值 < 1 次运行且两次失败可归因于已知非 MTC 因素 → 记 **无差异**；
- 若一臂 3/3、另一臂 <3/3 → 记录方向，但**不**宣称统计显著（n=3）；
- 任何手臂出现 `false success`（PASS 但验证失败）→ 该次运行作废并单独报告。

## 6. 边界
- 仿真（M3-S），非真实机器人（M3-R）；
- 不使用 LLM 决策；两臂 decision_policy 均 `fsm`；
- 不因结果修改验收器/阈值/世界。

## 7. 冻结声明
- 本文件在任何 C3 运行前提交；运行记录写入 `setup/acceptance/c3_fsm_vs_mtc_20261109/`；
- 运行结果附录将写明实际提交 sha 与时间。
