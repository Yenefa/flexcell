# C4 预注册 — Dual-object 场景下的 FSM vs MTC（冻结草案）

> 目的：把 C3 的 substrate 对比扩展到一个**两个对象**的场景，检验此前单对象结论是否一直成立。
> 本文件在运行前提交；指标与判读不得事后修改。

## 1. 两臂
| 臂 | 命令 |
| --- | --- |
| FSM（控制） | `sim_smoke --case dual_object --backend velocity_servo --skill-backend legacy --decision-policy fsm` |
| MTC（treatment） | 同上，`--skill-backend mtc` |

其余参数一致（`dual_object` 场景、默认位姿、预算、超时）。

## 2. 运行设计
- 每臂 **3 次**，交替：FSM, MTC, MTC, FSM, FSM, MTC；
- 每次独立 `GZ_PARTITION` / `ROS_DOMAIN_ID`；运行前清理；单次超时 600 s；
- 失败保留日志，不自动重跑。

## 3. 指标（预注册）
| 指标 | 定义 |
| --- | --- |
| 主指标 | `status=PASS` 且 `outcome=OUTCOME_SUCCEEDED`（**两个对象都完成**） |
| wall | `task.wall_seconds` |
| trace | `fsm_trace` 长度与阶段顺序 |
| 失败 | `status`/`error_code`/`detail` |
| 证据 | `episode`（含 `initial_world_state`）、fingerprint |

## 4. 判读规则（冻结）
- 若一臂 3/3、另一臂 <3/3 → 记录方向，但不宣称显著（n=3）；
- 若差异来自已知非 substrate 因素（如场景抖动），单独说明；
- 不修改验收器/阈值/世界；不作"MTC 更好/更差"的最终结论。

## 5. 边界
- 仿真（M3-S），非真机；
- 与 C3 单对象结论分开报告；
- 若 `dual_object` 本身不稳定，先记录失败，不重试刷成功率。

## 6. 冻结声明
- 运行结果写入 `setup/acceptance/c4_dual_fsm_vs_mtc_20261109/`。
