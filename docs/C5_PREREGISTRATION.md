# C5 预注册 — recovery_once 场景下 FSM vs MTC（冻结草案）

> C3/C4 已覆盖 normal 与 dual_object；C5 把 substrate 对比扩展到**故障恢复**场景。
> 本文件在运行前提交；指标与判读不得事后修改。

## 1. 两臂
| 臂 | 命令 |
| --- | --- |
| FSM | `sim_smoke --case recovery_once --backend velocity_servo --skill-backend legacy --decision-policy fsm` |
| MTC | 同上，`--skill-backend mtc` |

`recovery_once` 由既有 injection 机制注入一次故障；两臂同预算（recovery_budget=1）。

## 2. 运行设计
- 每臂 3 次，交替：FSM, MTC, MTC, FSM, FSM, MTC；
- 每次独立 `GZ_PARTITION` / `ROS_DOMAIN_ID`；运行前清理；单次超时 600 s；
- 失败保留，不重跑。

## 3. 指标（预注册）
| 指标 | 定义 |
| --- | --- |
| 主指标 | `status=PASS` 且 `outcome=OUTCOME_SUCCEEDED`（恢复后完成） |
| wall | `task.wall_seconds` |
| 恢复行为 | `fsm_trace` 中 `RECOVERY` 次数与结果 |
| 失败 | `status`/`error_code`/`detail` |
| 证据 | episode、fingerprint、`initial_world_state` |

## 4. 判读规则（冻结）
- 一臂 3/3、另一臂 <3/3 → 记录方向，不宣称显著（n=3）；
- 若两臂都失败：记录为"该场景下两套 orchestration 都未通过"，不作为任何优劣证据；
- 不修改验收器/阈值/世界；不宣称"MTC 更好/更差"。

## 5. 边界
- 仿真（M3-S）；
- `recovery_once` 的故障注入是**场景声明**，不是硬件故障；
- 结果写入 `setup/acceptance/c5_recovery_fsm_vs_mtc_20261109/`。
