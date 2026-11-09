# W5-E3 预注册 — Level B：源码级缺陷自主修复（真实 Gazebo）

> 冻结于启动前；除注明外不得修改。模型默认 `deepseek-flash`。

## 1. 缺陷（冻结）
- 位置：`src/flexcell/flexcell_skills/flexcell_skills/task_fsm_server.py`，PLACE 目标位姿选择；
- 注入：`zx, zy, zz = zones[zone_of[decision.target]]` → `zx, zy, zz = zones[zone_of[self._obj_a]]`；
- 行为：所有对象都被放到第一个对象的目标区；A 正确、B 偏移约 0.3 m；
- **config 正确**；normal / regrasp 单对象任务不受影响。

## 2. 基线（必须先验证）
- 注入后无 agent 运行：`dual_object` **FAIL**（B 校验误差 ~0.3 m，重试后预算耗尽）；
- `normal` **PASS**、`regrasp` **PASS**（回归门可用）。

## 3. Agent 任务（Level B 提示，不泄露答案）
- 提供症状：第一个对象成功，第二个对象放下后校验失败约 0.3 m；normal/regrasp 正常；
- 说明：缺陷在 `src/flexcell_skills`；可读可改；每次运行自动重新构建；`gate/` 只读；
- **不提供**：具体文件/行、参数名、补丁或正确值。

## 4. 验收（独立）
- 构建：agent 修改后重新 colcon build 成功；
- 真实 Gazebo 三门：`dual_object` PASS、`normal` PASS、`regrasp` PASS；
- 验收脚本只读，不由 agent 修改；失败即 REJECT。

## 5. 指标
读取次数、首次写操作位置（第几个 iteration）、迭代数、tokens、构建次数、修改 diff、三门状态、总耗时。

## 6. 判读
- 三门 PASS 且 diff 指向缺陷行 → **Level B 成功**；
- 若失败：保留 transcript 与 diff，归因 模型/工具/环境/任务设计；无法确定则 UNKNOWN；
- 不因失败改提示重跑；最多 3 次有新假设支撑的尝试，每次单独记录。
