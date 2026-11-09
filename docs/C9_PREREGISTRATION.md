# C9 预注册 — C8 扩到 n=9/臂（检验成功差异是否稳定）

> C8（n=3）首次出现成功差异：FSM 3/3 vs MTC 1/3，MTC 两次在 PICK_B 运动失败后恢复耗尽。
> C9 在相同配置下补充 6 次/臂，合计 **9/臂**，检验该差异是否稳定。

## 1. 场景与配置（与 C8 完全相同）
- `--case dual_object --backend velocity_servo --decision-policy fsm`；
- `--config-override`：`task_fsm_server.demo_verify_tolerance_m = 0.02`；
- 单次超时 600 s；失败保留。

## 2. 运行设计
- 新增 12 次（每臂 6 次），与 C8 的 3+3 合并为 **9/臂**；
- 交替顺序：L,M,M,L,M,L,M,L,L,M,M,L（L=legacy/FSM，M=MTC）；
- 前后清理、独立 GZ_PARTITION/ROS_DOMAIN_ID。

## 3. 指标（预注册）
| 指标 | 定义 |
| --- | --- |
| 主指标 | 成功率（PASS/9） |
| 次指标 | wall 均值/中位数；失败机制（PICK_B / 其他） |
| 证据 | result/episode、fingerprint、`initial_world_state` |

## 4. 判读规则（冻结）
- 差异持续（如 MTC ≤6/9）→ 记"**该场景下观察到差异**"，用 Fisher 精确检验给 p 值，仍不宣称因果；
- 差异消失（两臂都 ≥8/9 或相同）→ 记"**C8 的 n=3 差异不稳定**"，不选择性引用 C8；
- 若 MTC 失败点与 C8 相同（PICK_B 运动失败），单独记录该机制；
- 不得修改容差/验收器/世界让某臂通过。

## 5. 边界
- 仿真（M3-S）；单场景；单模型（无 LLM）；
- 结果写入 `setup/acceptance/c9_strict_dual_n9_20261109/`。

## 6. 结果附录（运行后追加，不改规则）
- FSM **9/9**，MTC **6/9**；平均 wall 28.281 vs 41.194 s（中位 28.362 vs 33.317）；
- 3 次失败全为 MTC，均在 `PICK_B` 运动失败后恢复耗尽；
- Fisher 精确检验（9/9 vs 6/9）：**双侧 p≈0.0035**；
- 记录：`setup/acceptance/c9_strict_dual_n9_20261109/`；
- 结论：**该场景下差异持续**，但不宣称因果，不外推到其他场景/本体。
