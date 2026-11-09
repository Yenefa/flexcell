# W5-E2e 预注册 — 第二种故障类型（对象注册缺失）

> P0 要求：把 W5-E2d 做扎实，证明不是"某个提示词巧合成"。
> E2e 引入**第二种、机制不同的缺陷**：工作区配置不再注册第二个对象（`tracked_objects` 只有 A）。

## 1. 缺陷与预期失败
- 覆盖 `observe_server.ros__parameters.tracked_objects = ["target_box_a"]`；
- 双对象任务的 B 对象不再被感知/校验 → 预期在 `OBSERVE`/`PICK_B` 阶段失败；
- normal 只用 A → 应仍 PASS（回归门可用）。

## 2. 探测（先做，不进入统计）
- 1 次 `dual_object`、无 agent、带覆盖配置；
- 若失败且机制为对象缺失 → 进入正式试点；
- 若仍 PASS（缺陷无效）→ 改用备选：`object_target_box_b_size` 错误，**重新预注册**。

## 3. 正式设计（探测通过后）
| 项 | 值 |
| --- | --- |
| 任务 | 与 E2d 相同三门（目标 dual_object + normal + regrasp） |
| 缺陷 | `tracked_objects` 缺 B（第二种类型） |
| 提示 | 与 E2d 相同的显式行动指令 |
| 重复 | 先用 deepseek-chat 2 次；若成功再考虑第二模型 |
| 预算 | 6 轮 |

## 4. 判读
- 2/2 成功且三门 PASS → 记"同一行动指令在第二种故障类型上仍有效（n=2）"；
- 失败 → 记录并停止该线，不调参硬凑；
- 不修改验收器/阈值/世界。

## 5. 记录
- `experiments/pilot-001/runs/p1.5-w5e2e-20261109/`。

## 6. 结果附录（运行后追加）
- 探测：`ERR_SAFETY_REJECTED` / `target_not_available`（`runs/p1.5-w5e2e-20261109/probe.json`）；
- 正式：**2/2 成功**，轮数 4/4，tokens 4063/4060，三门全 PASS；
- 结论：同一显式行动指令在**第二种、机制不同**的缺陷上仍有效（n=2，单模型）。
