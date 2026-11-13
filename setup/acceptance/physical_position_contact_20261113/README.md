# 冻结实现的位置与接触条件探针

执行源码：`89d7eba8c0c9413a4abc63235374d3c99fae5cc9`；冻结控制源码基于059fde5c。新探针在控制实现冻结后声明，结构使用独立 physical-probe/1 声明；冻结benchmark schema尚未覆盖push，未修改它或任何验收阈值。本实验不是正式封存盲测。

| 固定项 | 结果 | 返回后净位移 |
|---|---|---|
| ANCHOR | Runtime及独立9/9 PASS | 60.956 mm |
| OFFSET_NEG | Runtime及独立9/9 PASS | 60.972 mm |
| LONG_POS | 登记拒绝；0个执行目标 | 0.000 mm |
| YAW_POS | Runtime及独立9/9 PASS | 61.057 mm |
| YAW_NEG | Runtime及独立9/9 PASS | 60.921 mm |
| REG_NORMAL | 完整普通图 functional smoke PASS | — |

LONG_POS起点(0.235,0.025,0.0175)m、目标区中心x=0.105m，公开规划器要求3段推进。实际在第一次动作前拒绝：`ValueError: fixed-pitch target unreachable`，motion_goals_used=0，motion_terminal_known=true；物体0位移。独立验收不通过，physical_outcome标UNKNOWN；这是登记/运动学拒绝，不是已经完成了推动。

离线原始重放验证全部manifest及冻结/源码哈希，复现四个9/9和LONG_POS拒绝。返回契约中八个成功状态可消费，失败状态不能消费。完整结果和原始失败保留在ZIP、results.json和offline_verification.json。

第一次尝试43448470658因发现旧任务头与冻结schema不兼容，在机器人步骤前取消，没有物理样本。修正新声明后运行43448943203，未替换任何物理失败。

## 下一候选的依据

固定85°的IK拒绝与原始调用一致。只读真实碰撞模型表明，保留现有表面法向、离桌、关节与碰撞约束，可在约79°登记该起点。候选将优先保持85°，仅在其不可行时搜索有限角度，并继续通过原约束与执行器。该模型预测不构成物理通过；LONG_POS自本实验起作为暴露开发任务，不再用于未见集声明。

重放：使用本证据checkpoint源码，运行 verify_archive.py raw-43448943203.zip 到新的输出目录，不启动仿真。控制源码若已改变，应回到该checkpoint重放，不把新源码认证成旧证据。
